import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()
import anthropic
from flask import Flask, request, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# A Windows console still defaults to a legacy code page, which turns every
# accented word printed below into rubbish. Ask for UTF-8 and carry on if the
# stream does not support it.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day"],
)

MODEL = os.environ.get("PLANNER_MODEL", "claude-sonnet-5")

# Without a key there is nothing to call, so serve the demo rather than hanging on a
# request that cannot succeed. This is also the safe default for a public deploy:
# forgetting to set MOCK_MODE can't turn into a broken page or a surprise bill.
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
MOCK_MODE = os.environ.get("MOCK_MODE") == "1" or not HAS_API_KEY

# Each search injects the page contents into the prompt, so this is the main cost dial:
# measured ~US$0.29/itinerary at 5 searches on Sonnet 5.
SEARCHES = int(os.environ.get("PLANNER_SEARCHES", "6"))

# Sitting next to someone while they try the app is exactly when a stray extra
# click costs real money. The per-IP rate limit does not help there — it is the
# same person on the same machine — so the server also refuses to run more than
# this many real itineraries before it is restarted. The default has to be safe
# on its own: `python app.py` with nothing else typed must already be capped,
# because the day someone forgets the variable is the day it matters. Raise it
# with PLANNER_MAX_RUNS when a session genuinely needs more.
MAX_RUNS = int(os.environ.get("PLANNER_MAX_RUNS", "4"))
SPEND = {"runs": 0, "usd": 0.0}

# The 2026 web search tool only exists on Opus 4.6+/Sonnet 4.6+; older tiers need the 2025 one.
MODERN_SEARCH_MODELS = (
    "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-5", "claude-sonnet-4-6", "claude-fable-5",
)


def search_tool():
    tool_type = "web_search_20260209" if MODEL.startswith(MODERN_SEARCH_MODELS) else "web_search_20250305"
    return {"type": tool_type, "name": "web_search", "max_uses": SEARCHES}


def build_prompt(destination, start_date, days, budget, style, interests):
    end_date = ""
    try:
        d = date.fromisoformat(start_date)
        end_date = (d + timedelta(days=int(days) - 1)).isoformat()
    except (ValueError, TypeError):
        end_date = start_date

    interests_line = f"Traveller's interests: {interests}." if interests else ""

    return f"""Plan a trip to {destination}, {start_date} to {end_date} ({days} days).
Budget: ${budget} total. Style: {style}. {interests_line}

You have a small, fixed number of web searches. Spend them well, in this order:
1. Events on these exact dates that match the traveller's interests — a once-a-year event beats any permanent attraction. Search the interest, the city and the month together.
2. Opening hours and weekly closing days of the specific places you are about to recommend.
3. Only if searches remain: prices and booking requirements.

Search for the specific place or event, never broad queries like "things to do".

Then write the itinerary. Rules:
- ONE anchor activity per day, plus at most one secondary that realistically fits.
- Open with a "Heads up" section ONLY if you actually confirmed something date-specific that changes the plan. Say what it is, the date, and why it matters. If you confirmed nothing, skip the section entirely.

WHO YOU ARE WRITING FOR. Someone who travels rarely — maybe a couple of times in their life — and has never been to this city. They may be going alone. They are quietly worried about doing it wrong: getting on the wrong train, being ripped off, standing in front of a locked door. They are not stupid; they are simply new, and nobody has told them the things locals never have to think about.

So, alongside the plan itself:
- Explain the mechanics they cannot guess and would be embarrassed to ask: how you pay for transport there (card? app? ticket bought before boarding?), whether restaurants expect a reservation, whether tipping is expected and how much, what closes at lunch.
- Warn about the specific way tourists get taken advantage of in THIS city — the taxi that refuses the meter, the free bracelet, the ticket reseller outside the real ticket office. Name the actual local version, not generic advice.
- Give every outdoor anchor a rain alternative in one short line. A first-time traveller with a wet day and no plan B loses the whole day.
- Leave slack. Their day will run late, they will get lost once, they will want to sit down. A schedule that only works perfectly is a schedule that fails.
- Write warmly and never talk down. Say "o bilhete se compra antes de entrar, na máquina amarela" — not "obviously you need a ticket". Never use "é só" or "basta": nothing is obvious to someone who has never done it.

Write each day as a clock timeline they can follow without knowing anything:

**09:00 · Name of the place** (abre 09:00)
What to do there and how long it really takes, queue included.
↓ *18 min a pé* — or *25 min de metrô, linha azul, 4 paradas*
**11:30 · Next place** (abre 10:00)

Rules for the timeline:
- Every jump between two places gets its own line with the mode of transport and the minutes. Never let two stops touch without saying how you get from one to the other.
- Never schedule an arrival before the place opens or too close to when it closes. State the opening hour next to the time so the reader can see it lines up.
- Dead time is a planning failure. If the maths leaves an awkward gap, either fill it with something specific within walking distance, or move the stop to another day and say why.
- Say where lunch fits in the timeline, not as an afterthought.
- Warn about anything time-critical: last entry, last cable car, last train back, kitchen closing.
- Keep the pace human. Account for the walk from the metro, for getting lost, for a coffee. A day with three museums in it is a lie.

MONEY — the reader may plan a real trip around these numbers, so:
- Prices come in exactly two flavours and you must always say which: "confirmado" (you read it on a page this session) or "estimativa" (anything else). Never present an estimate as a fact.
- Quote prices in the destination's local currency. Convert to USD only as a rough parallel, marked "aprox.".
- NEVER state a flight price. You cannot know it — it moves by the hour and depends on the origin city. If flights matter, say what the trip costs on the ground and note that airfare is separate.
- The budget given is what the traveller has for the whole trip. Add up what you are proposing. If your plan does not fit the budget, say so plainly in one line at the top and adjust the plan down — never quietly invent lower numbers to make it fit, and never pad numbers to use up the budget.
- Round honestly. "cerca de €15-20" beats a fake-precise "€17,40" you did not read anywhere.
- If you confirmed no prices at all, give a short daily range labelled "estimativa" and say the traveller should check before booking — do not build a detailed fake budget table.

Close with "## Antes de ir" — three to five short lines of the practical basics for THIS city, the things a first-timer only learns by getting them wrong: how transport payment actually works, the local scam to watch for, whether you need to book restaurants, what shuts at lunch or on Sundays. Concrete and local, never generic travel advice.

- Do NOT write a sources list at the end — the app shows the pages you searched, with links, on its own.

Write only the itinerary. Never mention searches, tools, limits or what you could or could not do — the reader is a traveller, not a developer. No preamble, no apologies, no meta-commentary. Start directly with the "Heads up" section or "## Dia 1". Keep it tight: no filler, no restating the request.

Write in Brazilian Portuguese. Be specific and concrete, never generic."""


# The demo has to feel like the real thing without asserting invented facts about a
# real city, so days are described by shape (what the plan looks like) rather than by
# naming places and hours nobody verified. The banner marks it as an example.
# Each day is a list of stops and the legs between them, so the demo shows the same
# clock-and-transport shape the real itinerary uses.
DEMO_DAYS = [
    ("Centro histórico", 0.65, "dia barato: quase tudo é caminhada e rua.", [
        ("stop", "08:45", "A praça principal do centro", "abre sempre",
         "Começa cedo porque às 10h os ônibus de excursão chegam. Cerca de 1h caminhando sem pressa."),
        ("leg", "12 min a pé, ladeira leve"),
        ("stop", "10:00", "A catedral", "abre 10:00",
         "Chega na abertura, junto com o destrancar da porta. 45 min por dentro."),
        ("leg", "8 min a pé"),
        ("stop", "11:15", "O miradouro do bairro alto", "aberto",
         "Meia hora, e é onde dá pra entender a geografia da cidade — útil para os outros dias."),
        ("leg", "6 min a pé"),
        ("stop", "12:15", "Almoço no bairro", "cozinhas fecham 15:00",
         "Faixa de preço de restaurante de bairro, não de praça turística."),
    ]),
    ("O museu principal", 1.35, "o ingresso do museu pesa neste dia.", [
        ("stop", "10:00", "O museu principal", "abre 10:00 · fecha às segundas",
         "Encaixado num dia útil justamente porque fecha um dia da semana. 2h30 com a fila."),
        ("leg", "4 min a pé"),
        ("stop", "12:45", "Café ao lado do museu", "aberto",
         "Parada curta, porque a próxima atração só abre 14:00 — sem isso, sobrava tempo morto."),
        ("leg", "20 min de metrô, 5 paradas"),
        ("stop", "14:15", "O jardim ou parque da cidade", "abre 14:00",
         "Tarde leve depois da manhã pesada. Fica até o fim da tarde."),
    ]),
    ("Mercado e bairro local", 0.75, "sem ingresso; o gasto é comida e transporte.", [
        ("stop", "09:30", "O mercado municipal", "mais movimentado de manhã",
         "Vai cedo porque depois das 12h as bancas boas começam a fechar."),
        ("leg", "15 min a pé pelo bairro"),
        ("stop", "11:30", "A rua de comércio local", "aberto",
         "Sem hora marcada. É o trecho do dia em que dá pra se perder de propósito."),
        ("leg", "10 min de bonde ou ônibus"),
        ("stop", "13:30", "Almoço fora do circuito turístico", "aberto",
         "Metade do preço da região central, mesma comida."),
    ]),
    ("Bate e volta nos arredores", 1.5, "o trem de ida e volta é o maior custo do dia.", [
        ("stop", "07:50", "Estação central", "primeiro trem 08:00",
         "Sai cedo de propósito: o último trem de volta costuma ser antes das 20h."),
        ("leg", "50 min de trem"),
        ("stop", "09:00", "A cidade vizinha", "atrações abrem 09:30",
         "Chega antes de abrir, com café na praça enquanto isso — de novo, tempo morto evitado de propósito."),
        ("leg", "trem de volta, 50 min"),
        ("stop", "18:30", "De volta à cidade", "—",
         "Volta antes do escuro e com folga em relação ao último trem."),
    ]),
    ("Fim de tarde e pôr do sol", 0.55, "dia leve de propósito, para o orçamento respirar.", [
        ("stop", "15:00", "Bairro que ficou faltando", "aberto",
         "Dia mais leve, encaixado depois dos puxados. Nenhum roteiro aguenta cinco dias intensos seguidos."),
        ("leg", "18 min a pé subindo"),
        ("stop", "17:20", "O mirante do pôr do sol", "melhor 40 min antes",
         "No roteiro real, esse horário vem do pôr do sol calculado para a sua data exata — que muda mês a mês."),
    ]),
]


def demo_itinerary(destination, start_date, days, budget, interests):
    try:
        total_days = max(1, min(int(days), 10))
    except (ValueError, TypeError):
        total_days = 3

    try:
        per_day = int(budget) / total_days
    except (ValueError, TypeError, ZeroDivisionError):
        per_day = 0

    # Every interest counts, not just the first one — someone who writes
    # "comida local, esportes" means both.
    topics = [t.strip().lower() for t in interests.split(",") if t.strip()]
    if len(topics) > 1:
        listed = ", ".join(topics[:-1]) + " e " + topics[-1]
    else:
        listed = topics[0] if topics else ""

    interest_line = (
        f"Você marcou interesse em **{listed}** — no roteiro real, o Compass procuraria eventos "
        f"de {listed} acontecendo em {destination} exatamente nessas datas, e reorganizaria os "
        f"dias se achasse algum."
        if listed else
        f"No roteiro real, o Compass procuraria eventos acontecendo em {destination} exatamente "
        f"nessas datas e reorganizaria os dias se achasse algum que valesse a pena."
    )

    parts = [
        "## Heads up",
        "",
        f"**Este é um roteiro de demonstração para {destination}.**",
        interest_line,
        "",
        "É aqui que aparece o aviso que muda a viagem: um festival que lota a cidade, "
        "um museu fechado justamente no seu dia, uma obra que fechou a atração principal.",
        "",
        "Repare no formato dos dias abaixo: **cada pulo entre dois lugares tem o meio de transporte "
        "e os minutos**, e cada chegada bate com o horário de abertura. Ninguém deveria descobrir na "
        "porta que o lugar abre só daqui a uma hora.",
        "",
        "---",
        "",
    ]

    weekday = ""
    try:
        d0 = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        d0 = None

    for i in range(total_days):
        title, weight, cost_note, schedule = DEMO_DAYS[i % len(DEMO_DAYS)]
        if d0:
            d = d0 + timedelta(days=i)
            weekday = f" — {d.strftime('%d/%m')}"
        parts += [f"## Dia {i + 1}{weekday} · {title}", ""]

        for entry in schedule:
            if entry[0] == "leg":
                parts += [f"↓ *{entry[1]}*", ""]
            else:
                _, hour, place, opening, text = entry
                parts += [f"**{hour} · {place}** *({opening})*", "", text, ""]
        if per_day:
            # Days cost different amounts — a museum day is not a market day — so the
            # demo varies them instead of dividing the budget into equal slices.
            cost = per_day * weight
            parts += [
                f"**Custo deste dia: cerca de US$ {cost:,.0f}** — {cost_note}".replace(",", "."),
                "",
            ]
        parts += ["---", ""]

    parts += [
        "## Antes de ir",
        "",
        f"No roteiro real, esta seção traz o que só se aprende errando em {destination}:",
        "",
        "- **Como se paga o transporte** — se é cartão, aplicativo, ou bilhete comprado antes de entrar, e onde se compra.",
        "- **O golpe local** — não conselho genérico, mas a versão específica dali: o táxi que não liga o taxímetro, a pulseira \"de graça\", o revendedor de ingresso na porta da bilheteria de verdade.",
        "- **O que fecha e quando** — almoço, domingo, feriado municipal que só quem mora ali sabe.",
        "- **Se precisa reservar restaurante** e com quanta antecedência.",
        "",
        "---",
        "",
        "## Como o dinheiro aparece no roteiro real",
        "",
        "Todo preço vem com uma etiqueta, e as duas significam coisas diferentes:",
        "",
        "- **confirmado** — o Atlas leu esse valor numa página oficial nesta consulta, e o link está aqui embaixo.",
        "- **estimativa** — é uma faixa de preço, não um valor exato. Confira antes de reservar.",
        "",
        "**Passagem aérea nunca entra na conta.** O preço muda de hora em hora e depende de onde você sai — "
        "qualquer número que o Atlas desse ali seria chute. Os custos são do que você gasta no destino.",
        "",
        "> Se o plano não couber no seu orçamento, o Atlas diz isso na cara e enxuga o roteiro — "
        "em vez de inventar números menores para fingir que coube.",
    ]

    return "\n".join(parts)


MOCK_SOURCES = [
    {"title": "Exemplo — site oficial de turismo da cidade", "url": "https://exemplo-turismo.gov"},
    {"title": "Exemplo — agenda de eventos do período", "url": "https://exemplo-agenda-eventos.com"},
    {"title": "Exemplo — página de horários do museu", "url": "https://exemplo-museu.org/horarios"},
]


# USD per million tokens, so you can see what each itinerary actually cost.
PRICES = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
SEARCH_COST = 0.01  # per search


def log_cost(response):
    u = response.usage
    price_in, price_out = PRICES.get(MODEL, (2.0, 10.0))
    searches = getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0
    total = (
        u.input_tokens / 1_000_000 * price_in
        + u.output_tokens / 1_000_000 * price_out
        + searches * SEARCH_COST
    )
    SPEND["runs"] += 1
    SPEND["usd"] += total
    print(
        f"[custo] {MODEL} | entrada {u.input_tokens} | saída {u.output_tokens} "
        f"| buscas {searches} | ~US${total:.4f}",
        flush=True,
    )
    print(
        f"[total] {SPEND['runs']} de {MAX_RUNS} roteiros nesta sessão "
        f"| ~US${SPEND['usd']:.4f} gastos ao todo",
        flush=True,
    )


def extract(response):
    """Pull the itinerary text and the sources the model actually searched."""
    parts = []
    sources = {}

    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                url = getattr(citation, "url", None)
                if url:
                    sources[url] = getattr(citation, "title", None) or url
        elif block.type == "web_search_tool_result":
            # On error this is a single object instead of a list of results.
            results = block.content
            if isinstance(results, list):
                for result in results:
                    url = getattr(result, "url", None)
                    if url:
                        sources[url] = getattr(result, "title", None) or url

    return "".join(parts), [{"title": t, "url": u} for u, t in sources.items()]


MAX_DAYS = 30
MAX_BUDGET = 100_000
MIN_BUDGET = 50
MAX_YEARS_AHEAD = 2


def date_bounds():
    today = date.today()
    return today, today.replace(year=today.year + MAX_YEARS_AHEAD)


def validate(start_date, days, budget):
    """The browser checks these too, but anyone can POST straight past the form,
    so the server has to be the one that actually decides."""
    today, latest = date_bounds()

    try:
        d = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        return "Data de ida inválida."
    if d < today:
        return "A data de ida já passou. Escolha uma data de hoje em diante."
    if d > latest:
        return f"Só dá para planejar até {MAX_YEARS_AHEAD} anos à frente — nada é confiável tão longe."

    try:
        n = int(days)
    except (ValueError, TypeError):
        return "Número de dias inválido."
    if not 1 <= n <= MAX_DAYS:
        return f"A duração precisa ficar entre 1 e {MAX_DAYS} dias."

    try:
        b = float(budget)
    except (ValueError, TypeError):
        return "Orçamento inválido."
    if not MIN_BUDGET <= b <= MAX_BUDGET:
        return f"O orçamento precisa ficar entre {MIN_BUDGET} e {MAX_BUDGET:,} dólares.".replace(",", ".")

    return None


@app.route("/", methods=["GET"])
def index():
    today, latest = date_bounds()
    return render_template(
        "index.html",
        today=today.isoformat(),
        max_date=latest.isoformat(),
        demo=MOCK_MODE,
    )


@app.route("/plan", methods=["POST"])
@limiter.limit("5 per day")
def plan():
    destination = request.form.get("destination", "").strip()
    start_date = request.form.get("start_date", "").strip()
    days = request.form.get("days", "").strip()
    budget = request.form.get("budget", "").strip()
    style = request.form.get("style", "balanced").strip()
    interests = request.form.get("interests", "").strip()

    today, latest = date_bounds()
    form_values = dict(
        destination=destination, start_date=start_date, days=days,
        budget=budget, style=style, interests=interests,
        today=today.isoformat(), max_date=latest.isoformat(), demo=MOCK_MODE,
    )

    if not destination or not start_date or not days or not budget:
        return render_template("index.html", error="Preencha destino, data de ida, duração e orçamento.", **form_values)

    problem = validate(start_date, days, budget)
    if problem:
        return render_template("index.html", error=problem, **form_values)

    if MOCK_MODE:
        return render_template(
            "index.html",
            itinerary=demo_itinerary(destination, start_date, days, budget, interests),
            sources=MOCK_SOURCES,
            **form_values,
        )

    if SPEND["runs"] >= MAX_RUNS:
        return render_template("index.html", error=(
            f"Limite de segurança: {MAX_RUNS} roteiros reais já foram gerados desde que o "
            f"servidor ligou (cerca de US${SPEND['usd']:.2f}). Feche e abra o servidor para liberar mais."
        ), **form_values)

    try:
        # A hosted request that never returns just spins the browser forever, so cap it.
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=150.0,
            max_retries=1,
        )

        response = client.messages.create(
            model=MODEL,
            max_tokens=5000,
            tools=[search_tool()],
            messages=[{"role": "user", "content": build_prompt(
                destination, start_date, days, budget, style, interests
            )}],
        )

        itinerary, sources = extract(response)
        log_cost(response)
        return render_template("index.html", itinerary=itinerary, sources=sources, **form_values)

    except anthropic.APITimeoutError:
        return render_template("index.html",
            error="A busca demorou demais e foi interrompida. Tente de novo, ou reduza o número de dias.",
            **form_values)
    except anthropic.RateLimitError:
        return render_template("index.html", error="Muitos pedidos ao mesmo tempo. Tente de novo em um minuto.", **form_values)
    except anthropic.AuthenticationError:
        return render_template("index.html", error="Chave de API inválida ou sem crédito.", **form_values)
    except anthropic.APIStatusError as e:
        return render_template("index.html", error=f"O serviço de IA retornou um erro ({e.status_code}). Tente de novo.", **form_values)
    except anthropic.APIConnectionError:
        return render_template("index.html", error="Não foi possível conectar ao serviço de IA. Verifique sua internet.", **form_values)


# Prototype screens: static sample data, no account and no database behind them.
# They exist so testers can see the shape of the finished product before it is built.
@app.route("/painel")
def painel():
    return render_template("painel.html")


@app.route("/orcamento")
def orcamento():
    return render_template("orcamento.html")


@app.route("/viagem")
def viagem():
    return render_template("viagem.html")


@app.route("/lugares")
def lugares():
    return render_template("lugares.html")


@app.route("/documentos")
def documentos():
    return render_template("documentos.html")


@app.route("/viajantes")
def viajantes():
    return render_template("viajantes.html")


@app.errorhandler(429)
def rate_limit_exceeded(e):
    today, latest = date_bounds()
    return render_template("index.html",
        error="Você usou seus roteiros gratuitos de hoje. Volte amanhã.",
        today=today.isoformat(), max_date=latest.isoformat(), demo=MOCK_MODE,
    ), 429


if __name__ == "__main__":
    # Which mode is running should never be a guess: one of these costs money.
    banner = [""]
    if MOCK_MODE:
        banner.append("  MODO DEMONSTRAÇÃO — nenhuma chamada à API, custo zero.")
    else:
        banner.append("  MODO REAL — cada roteiro custa cerca de US$0,29 de verdade.")
        banner.append(f"  Teto de segurança: {MAX_RUNS} roteiros até reiniciar o servidor.")
    banner.append("")
    print("\n".join(banner), flush=True)
    # The reloader watches the source files and restarts on any edit. In demo mode
    # that is just convenient. In real mode it can tear down a request that has
    # already been paid for and hand back nothing, which is the worst outcome
    # there is: money gone, no itinerary.
    app.run(debug=MOCK_MODE, use_reloader=MOCK_MODE)

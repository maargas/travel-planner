import os
import re
import secrets
import sys
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
import anthropic
from flask import Flask, request, render_template, redirect, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import db
import contas

# A Windows console still defaults to a legacy code page, which turns every
# accented word printed below into rubbish. Ask for UTF-8 and carry on if the
# stream does not support it.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

app = Flask(__name__)

# ── Sessão ──────────────────────────────────────────────────────────────────
# O cookie de quem está logado é assinado com esta chave. Se ela vazar, qualquer
# um forja um login; se ela mudar, todo mundo é deslogado. Por isso ela vem do
# ambiente, e nunca do código.
_SEGREDO = os.environ.get("SECRET_KEY", "").strip()
SEGREDO_IMPROVISADO = not _SEGREDO and bool(os.environ.get("RENDER"))
if not _SEGREDO:
    if SEGREDO_IMPROVISADO:
        # Antes isto derrubava o site, o que é pior do que o problema que
        # resolvia: ninguém consegue nem olhar o app, e a variável que falta
        # continua faltando. Uma chave sorteada a cada arranque é segura — só não
        # dura: quem estava logado é deslogado quando o servidor reinicia. Serve
        # para ver o app funcionando enquanto a variável de verdade não chega.
        _SEGREDO = secrets.token_urlsafe(48)
        print("\n  ATENÇÃO: SECRET_KEY não está definida.\n"
              "  Uma chave temporária foi sorteada, então TODO MUNDO É DESLOGADO\n"
              "  sempre que o servidor reiniciar. Defina SECRET_KEY no Render.\n",
              flush=True)
    else:
        _SEGREDO = "chave-de-desenvolvimento-nao-use-em-producao"
app.secret_key = _SEGREDO

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,               # JavaScript da página não lê o cookie
    SESSION_COOKIE_SAMESITE="Lax",              # outro site não o envia junto
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),  # só por HTTPS, em produção
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=256 * 1024,              # ninguém precisa enviar mais que isso
)

# Render terminates TLS at its own proxy, so without this every visitor arrives
# from the same address and the per-visitor rate limit becomes a per-site one:
# one busy person locks everybody out. Only trusted behind that proxy — locally
# there is none, and honouring X-Forwarded-For from anyone would let a caller
# pick their own identity.
if os.environ.get("RENDER"):
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Two different things were being guarded with one number. Browsing between the
# screens costs nothing and had the same 100-a-day ceiling as generating an
# itinerary, so clicking around the sample screens could lock a visitor out of
# the whole site. The generous limit below is an abuse guard for pages; the real
# protection for money lives on /plan.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per hour"],
)

db.init()
# Uma linha no registro do Render que responde "onde as contas estão sendo
# guardadas?". Só o tipo do banco: o endereço tem senha e nunca é impresso.
print(f"[banco] {db.kind()}", flush=True)
# Os roteiros pesquisados à mão são carregados a cada arranque. É idempotente, e
# faz com que publicar conteúdo novo seja publicar o app — sem passo manual.
import semente
try:
    semente.carregar()
except Exception as exc:
    print(f"[semente] não carregou: {exc}", flush=True)

app.register_blueprint(contas.bp)
import viagens as viagens_mod  # noqa: E402
app.register_blueprint(viagens_mod.bp)

# Todo template precisa saber quem está logado e carregar o segredo do
# formulário, então em vez de passar os dois em cada render_template, eles ficam
# disponíveis em todos.
# Atenção: `usuario` é nome reservado nos templates. Nenhum render_template pode
# passar uma variável chamada `usuario`, ou ela apaga esta função e toda página
# que pergunta quem está logado quebra. (Já aconteceu: o texto digitado no
# formulário de login foi passado com esse nome.)
app.jinja_env.globals["usuario"] = contas.usuario_atual
app.jinja_env.globals["csrf_token"] = contas.csrf_token
# A foto e o trecho de vitrine de cada roteiro, e o registro das fotos com o
# crédito de cada uma. Ficam no semente.py, junto do catálogo.
app.jinja_env.globals["vitrine"] = semente.vitrine
app.jinja_env.globals["foto"] = semente.FOTOS.get
app.jinja_env.globals["capa_exemplos"] = semente.capa
app.jinja_env.globals["minhas_viagens"] = viagens_mod.minhas_viagens
app.jinja_env.globals["ABAS_VIAGEM"] = viagens_mod.ABAS
app.jinja_env.filters["periodo"] = lambda v: viagens_mod.periodo(v["ida"], v["volta"])
app.jinja_env.globals["faltam"] = viagens_mod.faltam

# Tentar senha atrás de senha é o ataque óbvio contra uma tela de login, e o
# limite por endereço é a defesa mais simples que existe contra ele.
limiter.limit("10 per hour")(app.view_functions["contas.entrar"])
limiter.limit("5 per hour")(app.view_functions["contas.criar_conta"])
# Trocar a senha pede a atual, então é outro lugar onde dá para ficar testando
# senha atrás de senha — mesmo limite do login.
limiter.limit("10 per hour")(app.view_functions["contas.trocar_senha"])

MODEL = os.environ.get("PLANNER_MODEL", "claude-sonnet-5")

# Without a key there is nothing to call, so serve the demo rather than hanging on a
# request that cannot succeed. This is also the safe default for a public deploy:
# forgetting to set MOCK_MODE can't turn into a broken page or a surprise bill.
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
MOCK_MODE = os.environ.get("MOCK_MODE") == "1" or not HAS_API_KEY

# Each search dumps whole web pages into the prompt, so this is THE cost dial.
# Measured split on a 6-search run: the pages the searches brought back were 64%
# of the bill, the searches themselves 24%, the written itinerary only 13%.
# Three searches is about US$0.14 an itinerary against US$0.25 at six, and a
# shorter searching turn is also less likely to be paused by the API. Two is
# cheaper still (~US$0.11) if you only care about the headline facts.
SEARCHES = int(os.environ.get("PLANNER_SEARCHES", "2"))

# Sitting next to someone while they try the app is exactly when a stray extra
# click costs real money. The per-IP rate limit does not help there — it is the
# same person on the same machine — so the server also refuses to run more than
# this many real itineraries before it is restarted. The default has to be safe
# on its own: `python app.py` with nothing else typed must already be capped,
# because the day someone forgets the variable is the day it matters. Raise it
# with PLANNER_MAX_RUNS when a session genuinely needs more.
MAX_RUNS = int(os.environ.get("PLANNER_MAX_RUNS", "4"))
SPEND = {"runs": 0, "usd": 0.0, "worst": 0.0}

# How many times one itinerary may be sent back to finish a paused turn. Every
# round resends the whole conversation, search results included, so a second
# round costs about as much as the first — four of them quadruple the bill.
# One retry is almost always enough.
MAX_ROUNDS = int(os.environ.get("PLANNER_MAX_ROUNDS", "2"))

# Counting itineraries is not the same as counting money: a paused turn can cost
# four calls, so four "runs" can be sixteen. This cap is in dollars, checked
# before every single call, and it is the one that actually protects a balance.
MAX_USD = float(os.environ.get("PLANNER_MAX_USD", "0.30"))


def estimated_call_cost():
    """What the next call could plausibly cost.

    A cap that only asks "have I spent too much yet?" lets the call that breaks
    it through: at US$0.25 spent against a US$0.30 cap it waves through a call
    that costs another US$0.25 and lands at US$0.50. So the cap has to reserve
    the next call before allowing it. Before anything has run there is only the
    arithmetic; once a call has been billed, the most expensive one so far is
    the better guide, and the more cautious one.
    """
    rough = 0.03 + SEARCHES * 0.037
    return max(rough, SPEND["worst"])

# The 2026 web search tool only exists on Opus 4.6+/Sonnet 4.6+; older tiers need the 2025 one.
MODERN_SEARCH_MODELS = (
    "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-5", "claude-sonnet-4-6", "claude-fable-5",
)


def search_tool():
    tool_type = "web_search_20260209" if MODEL.startswith(MODERN_SEARCH_MODELS) else "web_search_20250305"
    return {"type": tool_type, "name": "web_search", "max_uses": SEARCHES}


def build_prompt(destination, start_date, days, budget, style, interests, transporte="publico"):
    end_date = ""
    try:
        d = date.fromisoformat(start_date)
        end_date = (d + timedelta(days=int(days) - 1)).isoformat()
    except (ValueError, TypeError):
        end_date = start_date

    interests_line = f"Traveller's interests: {interests}." if interests else ""
    if transporte == "carro":
        transport_line = (
            "Transport: the traveller will have a car. Give every leg in driving minutes, say where "
            "to park and what it costs (marked estimate unless read on a page), and flag any place "
            "private cars cannot reach or where parking runs out early, with the way around it.")
    else:
        transport_line = (
            "Transport: the traveller will NOT have a car. Use walking and public transport only, "
            "and give the line or route and the minutes for every leg.")

    return f"""Plan a trip to {destination}, {start_date} to {end_date} ({days} days).
Budget: ${budget} total. Style: {style}. {interests_line}
{transport_line}

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

**09:00 · Name of the place** (abre 09:00, confirmado)
What to do there and how long it really takes, queue included.
↓ *18 min a pé* — or *25 min de metrô, linha azul, 4 paradas*
**11:30 · Next place** (horário não confirmado — confira no site antes de ir)

Rules for the timeline:
- Every jump between two places gets its own line with the mode of transport and the minutes. Never let two stops touch without saying how you get from one to the other.
- Never schedule an arrival before the place opens or too close to when it closes. State the opening hour next to the time so the reader can see it lines up.
- OPENING HOURS FOLLOW THE SAME RULE AS PRICES, and this matters more than any other rule here. Write "(abre 09:00, confirmado)" ONLY for an hour you read on a page in this session. For every other stop write "(horário não confirmado — confira no site antes de ir)". Never dress a remembered hour as a checked one: standing in front of a locked door is the exact failure this itinerary exists to prevent, and you have far fewer searches than stops, so most hours will honestly be unconfirmed. An unconfirmed hour labelled as such is useful; one presented as fact is a trap.
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


# De carro, o que muda no roteiro de demonstração: os trechos longos viram
# minutos dirigindo, e o bate e volta sai de carro em vez de trem. As
# caminhadas curtas ficam — ninguém tira o carro para andar 8 minutos.
DEMO_CARRO = {
    "20 min de metrô, 5 paradas": "15 min de carro · estacionamento pago perto do parque",
    "10 min de bonde ou ônibus": "8 min de carro",
    "50 min de trem": "45 min de carro · saia antes do trânsito",
    "trem de volta, 50 min": "volta de carro, 45 min",
    "Estação central": "Saída de carro",
    "primeiro trem 08:00": "antes do trânsito da manhã",
    "Sai cedo de propósito: o último trem de volta costuma ser antes das 20h.":
        "Sai cedo para pegar a estrada vazia e estacionar perto do centro da cidade vizinha.",
    "Volta antes do escuro e com folga em relação ao último trem.":
        "Volta antes do escuro, sem pressa na estrada.",
}


def demo_itinerary(destination, start_date, days, budget, interests, transporte="publico"):
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
        f"Você marcou interesse em **{listed}** — no roteiro real, o Farol procuraria eventos "
        f"de {listed} acontecendo em {destination} exatamente nessas datas, e reorganizaria os "
        f"dias se achasse algum."
        if listed else
        f"No roteiro real, o Farol procuraria eventos acontecendo em {destination} exatamente "
        f"nessas datas e reorganizaria os dias se achasse algum que valesse a pena."
    )

    carro = transporte == "carro"
    parts = [
        "## Heads up",
        "",
        f"**Este é um roteiro de demonstração para {destination}.**",
        interest_line,
        "",
    ]
    if carro:
        parts += [
            "Você escolheu ir **de carro**: no roteiro real, cada trecho vem em minutos dirigindo, "
            "com onde estacionar e quanto custa — e o aviso de onde carro não entra.",
            "",
        ]
    parts += [
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
            if carro:
                entry = tuple(DEMO_CARRO.get(x, x) for x in entry)
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
        "- **confirmado** — o Farol leu esse valor numa página oficial nesta consulta, e o link está aqui embaixo.",
        "- **estimativa** — é uma faixa de preço, não um valor exato. Confira antes de reservar.",
        "",
        "**Passagem aérea nunca entra na conta.** O preço muda de hora em hora e depende de onde você sai — "
        "qualquer número que o Farol desse ali seria chute. Os custos são do que você gasta no destino.",
        "",
        "> Se o plano não couber no seu orçamento, o Farol diz isso na cara e enxuga o roteiro — "
        "em vez de inventar números menores para fingir que coube.",
    ]

    return "\n".join(parts)


MOCK_SOURCES = [
    {"title": "Exemplo — site oficial de turismo da cidade", "url": "https://exemplo-turismo.gov"},
    {"title": "Exemplo — agenda de eventos do período", "url": "https://exemplo-agenda-eventos.com"},
    {"title": "Exemplo — página de horários do museu", "url": "https://exemplo-museu.org/horarios"},
]


# USD per million tokens, so you can see what each itinerary actually cost.
# Confirmado em 19/09/2026 na documentação oficial: Sonnet 5 custa US$2/US$10 por
# milhão de tokens (entrada/saída) e a busca na web, US$10 por 1.000 buscas.
PRICES = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
SEARCH_COST = 0.01  # per search

# Once the API answers, the money is already gone. From that moment the answer
# has to survive anything that happens next — a crash in the page, a restarted
# server, a closed tab, a browser that navigates away. So it goes to disk first,
# straight from the response, before it is parsed or rendered.
SAVE_DIR = os.environ.get("PLANNER_SAVE_DIR", "roteiros")


def save_path_for(destination):
    slug = re.sub(r"[^a-z0-9]+", "-", destination.lower()).strip("-")[:40] or "roteiro"
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    return os.path.join(SAVE_DIR, f"{stamp}_{slug}.md")


def save_itinerary(path, text, sources, destination, start_date, days, budget, note=""):
    """Write what has been paid for to a file. Never raises: it can only add a copy.

    Called after every round of the conversation, overwriting the same file, so a
    failure halfway through a paused turn still leaves the part already bought.
    """
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# {destination}\n\n")
            fh.write(f"{start_date} · {days} dias · orçamento US${budget}\n\n")
            if note:
                fh.write(f"> {note}\n\n")
            fh.write("---\n\n")
            fh.write(text or "_(a IA não chegou a escrever o roteiro nesta tentativa)_")
            if sources:
                fh.write("\n\n---\n\n## Fontes consultadas\n\n")
                for s in sources:
                    fh.write(f"- [{s['title']}]({s['url']})\n")
        print(f"[salvo] gravado em {path}", flush=True)
    except Exception as exc:
        print(f"[salvo] FALHOU ao gravar: {exc}", flush=True)
    return path


def log_cost(response, count_run=True):
    u = response.usage
    price_in, price_out = PRICES.get(MODEL, (2.0, 10.0))
    searches = getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0
    total = (
        u.input_tokens / 1_000_000 * price_in
        + u.output_tokens / 1_000_000 * price_out
        + searches * SEARCH_COST
    )
    # One itinerary can take several calls when the turn pauses; every call costs,
    # but only the itinerary counts against the cap.
    if count_run:
        SPEND["runs"] += 1
    SPEND["usd"] += total
    SPEND["worst"] = max(SPEND["worst"], total)
    c_in = u.input_tokens / 1_000_000 * price_in
    c_out = u.output_tokens / 1_000_000 * price_out
    print(
        f"[custo] ~US${total:.4f} = US${c_in:.4f} páginas das buscas "
        f"({u.input_tokens} tokens) + US${c_out:.4f} roteiro escrito "
        f"({u.output_tokens}) + US${searches * SEARCH_COST:.4f} de {searches} buscas "
        f"| parada: {response.stop_reason}",
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


# O roteiro que o site mostra como prova. É um roteiro publicado de verdade,
# lido do banco — o que a página de venda diz dele vem do mesmo lugar que o
# próprio roteiro, e não de um texto copiado que pode ficar para trás.
DESTAQUE = "banff-julho-2027"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


@app.route("/")
def inicio():
    """A página que apresenta o Farol: a promessa, como funciona, a prova."""
    from sqlalchemy import select as _sel, func as _func
    destaque = None
    with db.engine.connect() as cx:
        v = cx.execute(_sel(db.trips).where(db.trips.c.slug == DESTAQUE)).mappings().first()
        if v is not None:
            n_fontes = cx.execute(
                _sel(_func.count()).select_from(db.trip_sources)
                .where(db.trip_sources.c.trip_id == v["id"])
            ).scalar()
            destaque = {
                **v,
                "fontes": n_fontes,
                "quando": (f"{MESES[v['start_date'].month - 1]} de {v['start_date'].year}"
                           if v["start_date"] else ""),
                **semente.vitrine(DESTAQUE),
            }
    return render_template("inicio.html", destaque=destaque)


@app.route("/planejar", methods=["GET"])
def planejar():
    today, latest = date_bounds()
    # Vindo de dentro de uma viagem, destino, data e dias já chegam preenchidos.
    # São só sugestões no formulário: a validação de sempre continua valendo.
    pre = {k: (request.args.get(k) or "")[:120]
           for k in ("destination", "start_date", "days")}
    return render_template(
        "planejar.html",
        today=today.isoformat(),
        max_date=latest.isoformat(),
        demo=MOCK_MODE,
        **pre,
    )


@app.route("/plan", methods=["POST"])
@limiter.limit("5 per day", exempt_when=lambda: MOCK_MODE)
def plan():
    destination = request.form.get("destination", "").strip()
    start_date = request.form.get("start_date", "").strip()
    days = request.form.get("days", "").strip()
    budget = request.form.get("budget", "").strip()
    style = request.form.get("style", "balanced").strip()
    interests = request.form.get("interests", "").strip()
    transporte = "carro" if request.form.get("transporte") == "carro" else "publico"

    today, latest = date_bounds()
    form_values = dict(
        destination=destination, start_date=start_date, days=days,
        budget=budget, style=style, interests=interests, transporte=transporte,
        today=today.isoformat(), max_date=latest.isoformat(), demo=MOCK_MODE,
    )

    if not destination or not start_date or not days or not budget:
        return render_template("planejar.html", error="Preencha destino, data de ida, duração e orçamento.", **form_values)

    problem = validate(start_date, days, budget)
    if problem:
        return render_template("planejar.html", error=problem, **form_values)

    if MOCK_MODE:
        return render_template(
            "planejar.html",
            itinerary=demo_itinerary(destination, start_date, days, budget, interests, transporte),
            sources=MOCK_SOURCES,
            **form_values,
        )

    reserva = MAX_ROUNDS * estimated_call_cost()
    if SPEND["runs"] >= MAX_RUNS or SPEND["usd"] + reserva > MAX_USD:
        return render_template("planejar.html", error=(
            f"Limite de segurança atingido: {SPEND['runs']} de {MAX_RUNS} roteiros e cerca de "
            f"US${SPEND['usd']:.2f} de US${MAX_USD:.2f} gastos desde que o servidor ligou. "
            f"Este roteiro precisaria de até US${reserva:.2f} reservados e não cabe. "
            f"Feche e abra o servidor, ou aumente o teto com PLANNER_MAX_USD."
        ), **form_values)

    try:
        # A hosted request that never returns just spins the browser forever, so cap it.
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=150.0,
            max_retries=1,
        )

        messages = [{"role": "user", "content": build_prompt(
            destination, start_date, days, budget, style, interests, transporte
        )}]
        saved = save_path_for(destination)
        parts, sources, stop = [], {}, None

        # A long searching turn comes back with stop_reason "pause_turn": the
        # searches are done and billed, but the itinerary has not been written
        # yet. Treating that as the final answer is how a paid request returns
        # nothing but a list of links. Send the paused turn back so the model can
        # finish, bounded because every round is billed.
        for attempt in range(MAX_ROUNDS):
            # No money check inside the loop, deliberately. The reservation at
            # the door decided this itinerary could be afforded; stopping now
            # would strand a turn that has already been billed one round short
            # of the answer — full price, nothing delivered, which is the worst
            # outcome available. What bounds the damage here is MAX_ROUNDS. If
            # the calls cost more than the estimate, the door turns the next
            # itinerary away, because the reservation then uses what was really
            # spent.

            response = client.messages.create(
                model=MODEL,
                # 5000 was tight enough that a long itinerary could be cut off
                # mid-sentence. The docs' guidance for non-streaming is ~16000.
                max_tokens=16000,
                tools=[search_tool()],
                messages=messages,
            )
            log_cost(response, count_run=(attempt == 0))

            text, found = extract(response)
            if text:
                parts.append(text)
            for s in found:
                sources[s["url"]] = s["title"]
            stop = response.stop_reason

            # Disk first, after every round — never hold a paid answer in memory.
            save_itinerary(saved, "".join(parts),
                           [{"title": t, "url": u} for u, t in sources.items()],
                           destination, start_date, days, budget,
                           note=("resposta parcial — a IA parou por "
                                 f"'{stop}'" if stop == "pause_turn" else ""))

            if stop != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})

        itinerary = "".join(parts)
        source_list = [{"title": t, "url": u} for u, t in sources.items()]

        if not itinerary.strip():
            # Billed and nothing to show. Say exactly that, rather than rendering
            # a blank page and letting the reader guess.
            return render_template("planejar.html", error=(
                f"A IA fez as buscas mas parou antes de escrever o roteiro (motivo: {stop}). "
                f"O que veio está salvo em '{saved}'. Tente de novo com menos dias."
            ), **form_values)

        return render_template("planejar.html", itinerary=itinerary, sources=source_list,
                               saved=saved, **form_values)

    except anthropic.APITimeoutError:
        return render_template("planejar.html",
            error="A busca demorou demais e foi interrompida. Tente de novo, ou reduza o número de dias.",
            **form_values)
    except anthropic.RateLimitError:
        return render_template("planejar.html", error="Muitos pedidos ao mesmo tempo. Tente de novo em um minuto.", **form_values)
    except anthropic.AuthenticationError:
        return render_template("planejar.html", error="Chave de API inválida ou sem crédito.", **form_values)
    except anthropic.APIStatusError as e:
        return render_template("planejar.html", error=f"O serviço de IA retornou um erro ({e.status_code}). Tente de novo.", **form_values)
    except anthropic.APIConnectionError:
        return render_template("planejar.html", error="Não foi possível conectar ao serviço de IA. Verifique sua internet.", **form_values)
    except Exception as exc:
        # Anything unforeseen after the call still owes the reader an answer, and
        # the file on disk is that answer. A bare 500 would hide both.
        print(f"[erro] falha depois da resposta da API: {exc!r}", flush=True)
        return render_template("planejar.html", error=(
            "O roteiro foi gerado, mas deu erro ao montar a página. "
            f"Ele está salvo na pasta '{SAVE_DIR}' do projeto — nada foi perdido."
        ), **form_values)


# Os endereços antigos das telas de exemplo. Elas viraram as partes da viagem
# de exemplo (estrutura A); quem tinha o link, ou o app instalado com a tela
# aberta, continua chegando no lugar certo.
ANTIGOS = {"/painel": "/viagens", "/orcamento": "/exemplo/gastos",
           "/viagem": "/exemplo/roteiro", "/lugares": "/exemplo/roteiro",
           "/documentos": "/exemplo/documentos", "/viajantes": "/exemplo/pessoas"}
for _antigo, _novo in ANTIGOS.items():
    app.add_url_rule(_antigo, f"antigo{_antigo.replace('/', '_')}",
                     (lambda destino: lambda: redirect(destino, code=301))(_novo))


@app.route("/sw.js")
def service_worker():
    """Servido da raiz de propósito.

    Um service worker só controla páginas a partir da pasta em que ele mora. Em
    /static/sw.js o escopo era /static/, ou seja, ele não controlava nenhuma
    tela do app — e sem isso o Farol não instala no celular.
    """
    resposta = app.send_static_file("sw.js")
    resposta.headers["Service-Worker-Allowed"] = "/"
    resposta.headers["Cache-Control"] = "no-cache"
    return resposta


@app.route("/explorar")
def explorar():
    """Roteiros prontos, pesquisados de verdade — e o caminho para montar o seu."""
    from sqlalchemy import select as _sel
    with db.engine.connect() as cx:
        linhas = cx.execute(
            _sel(db.trips).order_by(db.trips.c.start_date)
        ).mappings().all()
    return render_template("explorar.html", viagens=linhas)


@app.route("/explorar/<slug>")
def roteiro(slug):
    from sqlalchemy import select as _sel
    with db.engine.connect() as cx:
        v = cx.execute(_sel(db.trips).where(db.trips.c.slug == slug)).mappings().first()
        if v is None:
            abort(404)
        fontes = cx.execute(
            _sel(db.trip_sources.c.title, db.trip_sources.c.url)
            .where(db.trip_sources.c.trip_id == v["id"])
        ).mappings().all()
    return render_template("roteiro.html", v=v, fontes=fontes)


@app.errorhandler(429)
def rate_limit_exceeded(e):
    # One message for "you asked for too many itineraries" and another for "you
    # loaded too many pages" — telling a visitor who was only clicking around
    # that they used up their free itineraries is simply false.
    if request.endpoint == "plan":
        message = "Você usou seus roteiros gratuitos de hoje. Volte amanhã."
    else:
        message = ("Muitos acessos em pouco tempo, então o site pausou por um "
                   "momento. Espere um minuto e recarregue.")
    today, latest = date_bounds()
    return render_template("planejar.html",
        error=message,
        today=today.isoformat(), max_date=latest.isoformat(), demo=MOCK_MODE,
    ), 429


if __name__ == "__main__":
    # Which mode is running should never be a guess: one of these costs money.
    banner = [""]
    if MOCK_MODE:
        banner.append("  MODO DEMONSTRAÇÃO — nenhuma chamada à API, custo zero.")
    else:
        banner.append(f"  MODO REAL — {SEARCHES} buscas por roteiro, cerca de "
                      f"US${0.03 + SEARCHES * 0.037:.2f} cada.")
        # Say how many actually fit, not how many the counter allows: the dollar
        # cap reserves a whole itinerary at a time, so it is usually the binding
        # one, and a banner promising four when one fits is a lie told daily.
        cabem = int(MAX_USD // (MAX_ROUNDS * estimated_call_cost()))
        banner.append(f"  Teto de segurança: US${MAX_USD:.2f} por sessão, "
                      f"o que dá {cabem} roteiro{'s' if cabem != 1 else ''}.")
        banner.append("  Reinicie o servidor, ou use PLANNER_MAX_USD, para liberar mais.")
    banner.append("")
    print("\n".join(banner), flush=True)
    # The reloader watches the source files and restarts on any edit. In demo mode
    # that is just convenient. In real mode it can tear down a request that has
    # already been paid for and hand back nothing, which is the worst outcome
    # there is: money gone, no itinerary.
    app.run(debug=MOCK_MODE, use_reloader=MOCK_MODE)

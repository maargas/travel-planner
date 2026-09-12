import os
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()
import anthropic
from flask import Flask, request, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day"],
)

MODEL = os.environ.get("PLANNER_MODEL", "claude-sonnet-5")
MOCK_MODE = os.environ.get("MOCK_MODE") == "1"

# Each search injects the page contents into the prompt, so this is the main cost dial:
# measured ~US$0.29/itinerary at 5 searches on Sonnet 5.
SEARCHES = int(os.environ.get("PLANNER_SEARCHES", "6"))

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
- Mark any unconfirmed hour, price or date with "(não verificado)" right next to it.
- Give real duration including queues and transit, best arrival time, daily cost breakdown, one nearby food option with price range.
- Do NOT write a sources list at the end — the app shows the pages you searched, with links, on its own.

Write only the itinerary. Never mention searches, tools, limits or what you could or could not do — the reader is a traveller, not a developer. No preamble, no apologies, no meta-commentary. Start directly with the "Heads up" section or "## Dia 1". Keep it tight: no filler, no restating the request.

Write in Brazilian Portuguese. Be specific and concrete, never generic."""


# The demo has to feel like the real thing without asserting invented facts about a
# real city, so days are described by shape (what the plan looks like) rather than by
# naming places and hours nobody verified. The banner marks it as an example.
DEMO_DAYS = [
    ("Centro histórico a pé",
     "A caminhada clássica do centro, começando cedo para pegar as ruas antes dos ônibus de excursão. "
     "No roteiro real, aqui entraria o nome da praça, o horário de abertura conferido e onde a fila começa a crescer.",
     "Chegar até 9h00 · cerca de 3h"),
    ("O museu principal",
     "Reservado para um dia útil, porque o roteiro real checa o dia de fechamento semanal antes de encaixar. "
     "Entraria aqui o preço atual do ingresso e se precisa comprar com antecedência.",
     "Abertura às 10h00 · cerca de 2h30"),
    ("Mercado e bairro local",
     "Meio período sem hora marcada, para equilibrar os dias de atração pesada. "
     "O roteiro real indicaria o dia de maior movimento do mercado e uma opção de almoço com faixa de preço.",
     "Melhor de manhã · cerca de 2h"),
    ("Bate e volta nos arredores",
     "Um dia fora da cidade, com o transporte já pensado na ida e na volta. "
     "O roteiro real traria o horário do trem ou ônibus e quanto tempo se perde no deslocamento.",
     "Sair até 8h00 · dia inteiro"),
    ("Mirante e fim de tarde",
     "Dia mais leve, encaixado depois dos dias puxados. "
     "O roteiro real usaria o horário real do pôr do sol na sua data.",
     "Fim de tarde · cerca de 2h"),
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

    topic = (interests.split(",")[0].strip() if interests else "").lower()
    interest_line = (
        f"Você marcou interesse em **{topic}** — no roteiro real, o Atlas procuraria eventos de {topic} "
        f"acontecendo em {destination} exatamente nessas datas, e reorganizaria os dias se achasse algum."
        if topic else
        f"No roteiro real, o Atlas procuraria eventos acontecendo em {destination} exatamente nessas datas "
        f"e reorganizaria os dias se achasse algum que valesse a pena."
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
        "---",
        "",
    ]

    weekday = ""
    try:
        d0 = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        d0 = None

    for i in range(total_days):
        title, text, timing = DEMO_DAYS[i % len(DEMO_DAYS)]
        if d0:
            d = d0 + timedelta(days=i)
            weekday = f" — {d.strftime('%d/%m')}"
        parts += [
            f"## Dia {i + 1}{weekday}",
            "",
            f"**Âncora: {title}**",
            text,
            "",
            f"*{timing}*",
            "",
        ]
        if per_day:
            parts += [f"Custo previsto do dia: cerca de **US$ {per_day:,.0f}**".replace(",", "."), ""]
        parts += ["---", ""]

    parts += [
        "> No roteiro real, cada horário e preço acima vem de uma página que o Atlas consultou "
        "na hora, e os links aparecem logo abaixo para você conferir um por um.",
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
    print(
        f"[custo] {MODEL} | entrada {u.input_tokens} | saída {u.output_tokens} "
        f"| buscas {searches} | ~US${total:.4f}",
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


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", today=date.today().isoformat(), demo=MOCK_MODE)


@app.route("/plan", methods=["POST"])
@limiter.limit("5 per day")
def plan():
    destination = request.form.get("destination", "").strip()
    start_date = request.form.get("start_date", "").strip()
    days = request.form.get("days", "").strip()
    budget = request.form.get("budget", "").strip()
    style = request.form.get("style", "balanced").strip()
    interests = request.form.get("interests", "").strip()

    form_values = dict(
        destination=destination, start_date=start_date, days=days,
        budget=budget, style=style, interests=interests,
        today=date.today().isoformat(), demo=MOCK_MODE,
    )

    if not destination or not start_date or not days or not budget:
        return render_template("index.html", error="Preencha destino, data de ida, duração e orçamento.", **form_values)

    if MOCK_MODE:
        return render_template(
            "index.html",
            itinerary=demo_itinerary(destination, start_date, days, budget, interests),
            sources=MOCK_SOURCES,
            **form_values,
        )

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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

    except anthropic.RateLimitError:
        return render_template("index.html", error="Muitos pedidos ao mesmo tempo. Tente de novo em um minuto.", **form_values)
    except anthropic.AuthenticationError:
        return render_template("index.html", error="Chave de API inválida ou sem crédito.", **form_values)
    except anthropic.APIStatusError as e:
        return render_template("index.html", error=f"O serviço de IA retornou um erro ({e.status_code}). Tente de novo.", **form_values)
    except anthropic.APIConnectionError:
        return render_template("index.html", error="Não foi possível conectar ao serviço de IA. Verifique sua internet.", **form_values)


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return render_template("index.html",
        error="Você usou seus roteiros gratuitos de hoje. Volte amanhã.",
        today=date.today().isoformat(), demo=MOCK_MODE,
    ), 429


if __name__ == "__main__":
    app.run(debug=True)

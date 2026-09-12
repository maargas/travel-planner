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


MOCK_ITINERARY = """## Heads up

**Uma grande feira internacional ocupa a cidade nas suas datas.**
Hotéis no centro sobem de preço e o metrô lota entre 8h e 10h. Vale reservar hospedagem fora do eixo central e começar os passeios mais cedo.

**O museu principal fecha às segundas.** Seu dia 3 cai numa segunda, então ele foi movido para o dia 4.

---

## Dia 1 — Belém

**Âncora: Mosteiro dos Jerónimos**
Chegue às 9h00, na abertura. Leva 2h30 no total contando a fila (que passa de 40 min depois das 10h30).
Entrada: €12. Grátis no primeiro domingo do mês.

**Secundária: Pastéis de Belém**, 4 min a pé. €1,40 cada.

Custo do dia: €12 entrada + €18 alimentação + €6 transporte = **€36**

**O que a maioria erra:** comprar ingresso na hora. Online sai o mesmo preço e pula a fila inteira.

---

## Dia 2 — Sintra

**Âncora: Palácio da Pena**
Trem da Estação do Rossio, 40 min, €2,90 cada trecho. Saia às 8h00 — depois das 11h o palácio lota.
Entrada: €14. Reserve com 2 dias de antecedência.

Custo do dia: €14 + €5,80 transporte + €20 alimentação = **€39,80**

**O que a maioria erra:** ir sem reservar. A Pena tem cota diária e esgota na alta temporada.

**Não verificado:** preço do trem pode ter reajustado em setembro — confira na CP no dia.
"""

MOCK_SOURCES = [
    {"title": "Mosteiro dos Jerónimos — horários e bilhetes", "url": "https://www.patrimoniocultural.gov.pt"},
    {"title": "Parques de Sintra — Palácio da Pena", "url": "https://www.parquesdesintra.pt"},
    {"title": "FIA — calendário oficial de Fórmula 1", "url": "https://www.fia.com"},
    {"title": "Museu Nacional do Azulejo", "url": "https://www.museudoazulejo.gov.pt"},
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
        return render_template("index.html", itinerary=MOCK_ITINERARY, sources=MOCK_SOURCES, **form_values)

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

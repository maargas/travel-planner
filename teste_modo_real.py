"""Prova que o modo real funciona, sem gastar um centavo.

Roda TODO o caminho do modo real — o teto de gasto, a pausa no meio das buscas,
a gravação em disco, a leitura das fontes, a conta do custo e a página montada —
trocando apenas a chamada à API por uma resposta de mentira. Depois disto, a
única coisa que continua sem prova é a ida à internet.

Rode antes de qualquer teste que gaste dinheiro:

    python teste_modo_real.py

Sai com código 0 se tudo passou.
"""
import os, sys, glob, shutil

PROJ = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJ)
sys.path.insert(0, PROJ)

# A key that cannot work, so a bug that bypasses the stub cannot spend money.
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-INVALIDA-PARA-TESTE"
os.environ["MOCK_MODE"] = "0"
os.environ["PLANNER_SAVE_DIR"] = "roteiros_teste"

import anthropic
import app

app.MOCK_MODE = False
app.SAVE_DIR = "roteiros_teste"

ITINERARY = """## Dia 1 — quinta

**09:00 · Torre de Belém** (abre 09:30)
Chegue antes da fila.
↓ *12 min a pé*
**11:00 · Mosteiro dos Jerónimos** (abre 10:00)
"""


def block(**kw):
    return type("Block", (), kw)()


def search_block(url, title):
    result = block(url=url, title=title)
    return block(type="web_search_tool_result", content=[result])


def text_block(text, cite=None):
    citations = [block(url=cite[0], title=cite[1])] if cite else []
    return block(type="text", text=text, citations=citations)


def usage(inp=80470, out=3200, searches=6):
    return block(input_tokens=inp, output_tokens=out,
                 server_tool_use=block(web_search_requests=searches))


def response(content, stop, **kw):
    return block(content=content, stop_reason=stop, usage=usage(**kw))


class FakeClient:
    """Returns a scripted list of responses, one per call."""
    script = []
    calls = 0

    def __init__(self, **kw):
        self.messages = self

    def create(self, **kw):
        assert kw["tools"], "a busca na web precisa estar ligada"
        assert kw["max_tokens"] >= 16000, "max_tokens baixo demais corta o roteiro"
        r = FakeClient.script[min(FakeClient.calls, len(FakeClient.script) - 1)]
        FakeClient.calls += 1
        return r


anthropic.Anthropic = FakeClient

c = app.app.test_client()
form = dict(destination="Lisboa, Portugal", start_date="2026-11-10", days="4",
            budget="900", style="balanced", interests="comida local, esportes")

checks = []


def check(label, condition):
    checks.append((label, bool(condition)))


def run(script):
    """Reset all state, run one POST, return the page."""
    shutil.rmtree("roteiros_teste", ignore_errors=True)
    app.SPEND["runs"] = 0
    app.SPEND["usd"] = 0.0
    FakeClient.script = script
    FakeClient.calls = 0
    return c.post("/plan", data=form).get_data(as_text=True)


# ── 1. The straightforward case: one call, itinerary written ──────────────
print("=" * 62)
print("\n1) resposta normal, de uma vez só\n")
html = run([response(
    [search_block("https://exemplo.pt/eventos", "Agenda de Lisboa"),
     text_block(ITINERARY, cite=("https://exemplo.pt/torre", "Torre de Belém"))],
    "end_turn")])

check("o roteiro aparece na pagina", "Torre de Bel" in html)
check("nao caiu em mensagem de erro", 'class="error"' not in html)
check("as fontes aparecem na pagina", "exemplo.pt" in html)
check("o aviso de copia salva aparece", "salva em" in html)
check("uma chamada a API foi feita", FakeClient.calls == 1)

files = glob.glob("roteiros_teste/*.md")
check("um arquivo foi gravado", len(files) == 1)
if files:
    saved = open(files[0], encoding="utf-8").read()
    check("o arquivo tem o roteiro inteiro", "Mosteiro dos Jer" in saved)
    check("o arquivo tem as fontes", "exemplo.pt/eventos" in saved)

esperado = 80470 / 1e6 * 2.0 + 3200 / 1e6 * 10.0 + 6 * 0.01
check(f"o custo bate com a conta (US${esperado:.4f})",
      abs(app.SPEND["usd"] - esperado) < 0.0001)

# ── 2. The case that actually broke: the turn pauses mid-search ───────────
# The first response carries searches and no text — exactly what came back the
# day a paid run produced a file of links and nothing else.
print("\n2) a IA pausa no meio das buscas (o defeito real)\n")
html = run([
    response([search_block("https://banff.ca/calendar", "Calendar - Banff")], "pause_turn"),
    response([search_block("https://banff.ca/events", "Events"),
              text_block(ITINERARY)], "end_turn"),
])

check("a pausa foi retomada (2 chamadas)", FakeClient.calls == 2)
check("o roteiro chegou na pagina", "Torre de Bel" in html)
check("nao mostrou pagina em branco", 'class="error"' not in html)
check("conta como 1 roteiro, nao 2, no teto", app.SPEND["runs"] == 1)
check("mas cobrou as duas chamadas", abs(app.SPEND["usd"] - esperado * 2) < 0.0001)

files = glob.glob("roteiros_teste/*.md")
if files:
    saved = open(files[0], encoding="utf-8").read()
    check("o arquivo final tem o roteiro", "Mosteiro dos Jer" in saved)
    check("e as fontes das duas rodadas", "banff.ca/calendar" in saved and "banff.ca/events" in saved)

# ── 3. It never finishes: say so, do not render a blank page ──────────────
print("\n3) a IA nunca escreve o roteiro\n")
html = run([response([search_block("https://x.pt/a", "A")], "pause_turn")])

# The dollar cap bites before the round cap does, which is the point of it.
check("parou antes de estourar o dinheiro",
      FakeClient.calls <= app.MAX_ROUNDS and app.SPEND["usd"] < app.MAX_USD + esperado)
check("avisa que nao escreveu o roteiro", "parou antes de escrever" in html)
check("e diz onde esta o arquivo", "roteiros_teste" in html)
files = glob.glob("roteiros_teste/*.md")
check("o arquivo existe mesmo assim", len(files) == 1)
if files:
    saved = open(files[0], encoding="utf-8").read()
    check("o arquivo explica que veio vazio", "não chegou a escrever" in saved)

# ── 4. The spend cap still holds ─────────────────────────────────────────
print("\n4) o teto de gasto\n")
shutil.rmtree("roteiros_teste", ignore_errors=True)
app.SPEND["runs"] = app.MAX_RUNS
FakeClient.script = [response([text_block(ITINERARY)], "end_turn")]
FakeClient.calls = 0
html = c.post("/plan", data=form).get_data(as_text=True)
check("o teto de roteiros bloqueia", "Limite de seguran" in html)
check("e nem chama a API", FakeClient.calls == 0)

app.SPEND["runs"] = 0
app.SPEND["usd"] = app.MAX_USD
FakeClient.calls = 0
html = c.post("/plan", data=form).get_data(as_text=True)
check("o teto de dinheiro bloqueia sozinho", "Limite de seguran" in html)
check("e tambem nem chama a API", FakeClient.calls == 0)

print()
for label, passed in checks:
    print(("  OK     " if passed else "  FALHOU ") + label)

falhas = [l for l, p in checks if not p]
print()
print("=" * 62)
print(f"{len(checks) - len(falhas)} de {len(checks)} verificacoes passaram"
      + ("" if not falhas else f" | FALHAS: {falhas}"))
shutil.rmtree("roteiros_teste", ignore_errors=True)
sys.exit(1 if falhas else 0)

"""Prova que o modo real funciona, sem gastar um centavo.

Roda TODO o caminho do modo real — o teto de gasto, a gravação em disco, a
leitura das fontes, a conta do custo e a página montada — trocando apenas a
chamada à API por uma resposta de mentira. Depois disto, a única coisa que
continua sem prova é a ida à internet.

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
shutil.rmtree("roteiros_teste", ignore_errors=True)

ITINERARY = """## Dia 1 — quinta

**09:00 · Torre de Belém** (abre 09:30)
Chegue antes da fila.
↓ *12 min a pé*
**11:00 · Mosteiro dos Jerónimos** (abre 10:00)
"""


class Citation:
    url = "https://exemplo.pt/torre"
    title = "Torre de Belém — horários"


class TextBlock:
    type = "text"
    text = ITINERARY
    citations = [Citation()]


class SearchResult:
    url = "https://exemplo.pt/eventos"
    title = "Agenda de Lisboa"


class SearchBlock:
    type = "web_search_tool_result"
    content = [SearchResult()]


class ToolUse:
    web_search_requests = 6


class Usage:
    input_tokens = 80470
    output_tokens = 3200
    server_tool_use = ToolUse()


class FakeResponse:
    content = [SearchBlock(), TextBlock()]
    usage = Usage()


class FakeMessages:
    def create(self, **kw):
        assert kw["model"] == app.MODEL
        assert kw["tools"], "a busca na web precisa estar ligada"
        return FakeResponse()


class FakeClient:
    def __init__(self, **kw):
        self.messages = FakeMessages()


anthropic.Anthropic = FakeClient

c = app.app.test_client()
form = dict(destination="Lisboa, Portugal", start_date="2026-11-10", days="4",
            budget="900", style="balanced", interests="comida local, esportes")

print("=" * 62)
r = c.post("/plan", data=form)
html = r.get_data(as_text=True)

checks = []


def check(label, condition):
    checks.append((label, bool(condition)))


check("a pagina respondeu 200", r.status_code == 200)
check("o roteiro aparece na pagina", "Torre de Bel" in html)
check("nao caiu em mensagem de erro", "class=\"error\"" not in html)
check("as fontes aparecem na pagina", "exemplo.pt" in html)
check("o aviso de copia salva aparece", "salva em" in html)

files = glob.glob("roteiros_teste/*.md")
check("um arquivo foi gravado no disco", len(files) == 1)

if files:
    saved = open(files[0], encoding="utf-8").read()
    check("o arquivo tem o roteiro inteiro", "Mosteiro dos Jer" in saved)
    check("o arquivo tem o cabecalho da viagem", "Lisboa, Portugal" in saved)
    check("o arquivo tem as fontes", "exemplo.pt/eventos" in saved)

check("o gasto foi contabilizado", app.SPEND["runs"] == 1)
# 80470/1e6*$2 + 3200/1e6*$10 + 6 buscas*$0.01 = $0.25294
esperado = 80470 / 1e6 * 2.0 + 3200 / 1e6 * 10.0 + 6 * 0.01
check(f"o custo calculado bate com a conta (US${esperado:.4f})",
      abs(app.SPEND["usd"] - esperado) < 0.0001)

# The cap must still hold on the real path, not just in isolation.
app.SPEND["runs"] = app.MAX_RUNS
r2 = c.post("/plan", data=form)
check("o teto bloqueia quando atingido", "Limite de seguran" in r2.get_data(as_text=True))
check("e nao gravou arquivo novo", len(glob.glob("roteiros_teste/*.md")) == 1)

print()
for label, passed in checks:
    print(("  OK   " if passed else "  FALHOU ") + label)

falhas = [l for l, p in checks if not p]
print()
print("=" * 62)
print(f"{len(checks) - len(falhas)} de {len(checks)} verificacoes passaram"
      + ("" if not falhas else f" | FALHAS: {falhas}"))
if files:
    print(f"arquivo gerado: {files[0]}")
shutil.rmtree("roteiros_teste", ignore_errors=True)
sys.exit(1 if falhas else 0)

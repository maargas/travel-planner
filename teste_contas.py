"""Prova que criar conta, entrar e sair funcionam — e que a senha não vaza.

Roda contra um banco descartável, nunca o de verdade. Não toca na API, não
gasta nada.

    python teste_contas.py
"""
import os
import sys
import tempfile

PROJ = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJ)
sys.path.insert(0, PROJ)

# Banco só deste teste, apagado no fim. Precisa vir antes de importar db.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "teste.db").replace("\\", "/")
os.environ["MOCK_MODE"] = "1"
os.environ["SECRET_KEY"] = "chave-de-teste"

import db          # noqa: E402
import app as appmod  # noqa: E402
from sqlalchemy import select  # noqa: E402

app = appmod.app
app.config["TESTING"] = True
appmod.limiter.enabled = False   # o limite tem cenário próprio; aqui atrapalharia

SENHA = "umaSenhaBoa123"
EMAIL = "amigo@exemplo.com"

checks = []


def check(label, cond):
    checks.append((label, bool(cond)))


def token(c, caminho="/entrar"):
    """Pega o segredo do formulário da própria página, como um navegador faria."""
    html = c.get(caminho).get_data(as_text=True)
    marca = 'name="csrf" value="'
    i = html.index(marca) + len(marca)
    return html[i:html.index('"', i)]


# ── Criar conta ─────────────────────────────────────────────────────────────
c = app.test_client()

r = c.post("/criar-conta", data={"csrf": token(c, "/criar-conta"), "nome": "Amigo",
                                 "email": EMAIL, "senha": "curta"})
check("senha curta e recusada", r.status_code == 400 and "8 caracteres" in r.get_data(as_text=True))

r = c.post("/criar-conta", data={"csrf": token(c, "/criar-conta"), "nome": "Amigo",
                                 "email": "nao-e-email", "senha": SENHA})
check("e-mail invalido e recusado", r.status_code == 400)

r = c.post("/criar-conta", data={"nome": "Amigo", "email": EMAIL, "senha": SENHA})
check("formulario sem o segredo e recusado", r.status_code == 400)

r = c.post("/criar-conta", data={"csrf": token(c, "/criar-conta"), "nome": "Amigo",
                                 "email": "  " + EMAIL.upper() + " ", "senha": SENHA})
check("conta criada (e-mail normalizado)", r.status_code == 302)
check("ja entra logado depois de criar",
      "Amigo" in c.get("/painel").get_data(as_text=True))

# Cliente novo: quem ja esta logado nem chega na tela de criar conta.
outro = app.test_client()
r = outro.post("/criar-conta", data={"csrf": token(outro, "/criar-conta"), "nome": "Outro",
                                     "email": EMAIL, "senha": SENHA})
check("e-mail repetido e recusado", "Já existe uma conta" in r.get_data(as_text=True))

# ── A senha não pode estar legível em lugar nenhum ──────────────────────────
with db.engine.connect() as cx:
    linha = cx.execute(select(db.users)).mappings().first()
check("a senha nao esta no banco", SENHA not in str(dict(linha)))
check("o que esta guardado e um hash scrypt", linha["password_hash"].startswith("scrypt:"))
check("o e-mail foi guardado em minusculas", linha["email"] == EMAIL)

corpo = c.get("/painel").get_data(as_text=True)
check("a senha nao aparece na pagina", SENHA not in corpo)

# ── Sair e entrar ───────────────────────────────────────────────────────────
r = c.post("/sair", data={"csrf": token(c, "/painel")})
check("sair funciona", r.status_code == 302)

r = c.post("/entrar", data={"csrf": token(c), "email": EMAIL, "senha": "senhaErrada1"})
check("senha errada e recusada", r.status_code == 400)
check("nao diz se o e-mail existe", "não conferem" in r.get_data(as_text=True))

r = c.post("/entrar", data={"csrf": token(c), "email": "ninguem@exemplo.com", "senha": SENHA})
check("e-mail inexistente da a mesma mensagem", "não conferem" in r.get_data(as_text=True))

r = c.post("/entrar", data={"csrf": token(c), "email": EMAIL, "senha": SENHA})
check("senha certa entra", r.status_code == 302)

# ── Destino externo não pode ser usado para levar a pessoa para fora ────────
c2 = app.test_client()
r = c2.post("/entrar", data={"csrf": token(c2), "email": EMAIL, "senha": SENHA,
                             "proximo": "https://site-falso.exemplo"},
            query_string={"proximo": "https://site-falso.exemplo"})
check("nao redireciona para fora do app",
      "site-falso" not in (r.headers.get("Location") or ""))

# ── A fila de pedidos ───────────────────────────────────────────────────────
anon = app.test_client()
r = anon.post("/pedir", data={"csrf": "x", "destination": "Lisboa"})
check("pedir exige estar logado", r.status_code in (302, 400))
check("e nada foi gravado", db.count(db.requests_table) == 0)

r = c.post("/pedir", data={"csrf": token(c, "/viagens"), "destination": "Lisboa, Portugal",
                           "days": "4", "interests": "comida local"})
check("logado consegue pedir um destino", r.status_code == 302)
check("o pedido foi para a fila", db.count(db.requests_table) == 1)

# ── Os roteiros reais ───────────────────────────────────────────────────────
html = c.get("/viagens").get_data(as_text=True)
check("a lista mostra o roteiro pesquisado", "Banff" in html)
check("e mostra o achado que muda a viagem", "Stampede" in html)
html = c.get("/viagens/banff-julho-2027").get_data(as_text=True)
check("o roteiro abre inteiro", "Moraine Lake" in html)
check("com as fontes anotadas", "parks.canada.ca" in html or "calgarystampede" in html)
check("endereco inventado da 404", c.get("/viagens/nao-existe").status_code == 404)

# ── Resultado ───────────────────────────────────────────────────────────────
print()
for label, ok in checks:
    print(("  OK     " if ok else "  FALHOU ") + label)
falhas = [l for l, ok in checks if not ok]
print()
print("=" * 62)
print(f"{len(checks) - len(falhas)} de {len(checks)} verificacoes passaram"
      + ("" if not falhas else f" | FALHAS: {falhas}"))

import shutil  # noqa: E402
db.engine.dispose()
shutil.rmtree(_tmp, ignore_errors=True)
sys.exit(1 if falhas else 0)

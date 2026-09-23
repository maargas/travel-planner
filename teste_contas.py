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

# Tudo o que o app escrever no terminal — registro, aviso, erro — passa também
# por esta cópia. No fim, o teste procura as senhas nela: senha em log é
# vazamento, e isso não se negocia.
import io  # noqa: E402


class _Copia(io.TextIOBase):
    def __init__(self, original):
        self.original, self.texto = original, []

    def write(self, s):
        self.texto.append(s)
        return self.original.write(s)

    def flush(self):
        self.original.flush()


for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8")
    except Exception:
        pass
sys.stdout, sys.stderr = _Copia(sys.stdout), _Copia(sys.stderr)

import db          # noqa: E402
import app as appmod  # noqa: E402
from sqlalchemy import select  # noqa: E402

app = appmod.app
app.config["TESTING"] = True
appmod.limiter.enabled = False   # o limite tem cenário próprio; aqui atrapalharia

SENHA = "umaSenhaBoa123"
USUARIO = "amigo.teste"

checks = []


def check(label, cond):
    checks.append((label, bool(cond)))


def token(c, caminho="/entrar"):
    """Pega o segredo do formulário da própria página, como um navegador faria."""
    html = c.get(caminho).get_data(as_text=True)
    marca = 'name="csrf" value="'
    i = html.index(marca) + len(marca)
    return html[i:html.index('"', i)]


def criar(c, usuario, senha=SENHA, nome="Amigo"):
    return c.post("/criar-conta", data={"csrf": token(c, "/criar-conta"), "nome": nome,
                                        "usuario": usuario, "senha": senha})


# ── Criar conta ─────────────────────────────────────────────────────────────
c = app.test_client()

r = criar(c, USUARIO, senha="curta")
check("senha curta e recusada", r.status_code == 400 and "8 caracteres" in r.get_data(as_text=True))

for ruim in ["ab", "tem espaco", "ação", "a" * 25, "nome!"]:
    r = criar(c, ruim)
    check(f"usuario invalido recusado: {ruim!r}", r.status_code == 400)

r = c.post("/criar-conta", data={"nome": "Amigo", "usuario": USUARIO, "senha": SENHA})
check("formulario sem o segredo e recusado", r.status_code == 400)

r = criar(c, "  @Amigo.Teste ")
check("conta criada (com @, maiusculas e espacos limpos)", r.status_code == 302)
check("ja entra logado depois de criar",
      "Amigo" in c.get("/conta").get_data(as_text=True))

# Cliente novo: quem ja esta logado nem chega na tela de criar conta.
outro = app.test_client()
r = criar(outro, "AMIGO.TESTE", nome="Outro")
check("usuario repetido e recusado, mesmo em maiusculas",
      "já está em uso" in r.get_data(as_text=True))

# ── Nenhum e-mail guardado, e a senha ilegível ──────────────────────────────
with db.engine.connect() as cx:
    linha = cx.execute(select(db.users)).mappings().first()
check("nao existe coluna de e-mail", "email" not in linha.keys())
check("o usuario foi guardado normalizado", linha["username"] == USUARIO)
check("a senha nao esta no banco", SENHA not in str(dict(linha)))
check("o que esta guardado e um hash scrypt", linha["password_hash"].startswith("scrypt:"))
check("so uma conta foi criada", db.count(db.users) == 1)

corpo = c.get("/conta").get_data(as_text=True)
check("a senha nao aparece na pagina", SENHA not in corpo)
check("o @usuario aparece para quem esta logado", "@" + USUARIO in corpo)

# ── Sair e entrar ───────────────────────────────────────────────────────────
r = c.post("/sair", data={"csrf": token(c, "/conta")})
check("sair funciona", r.status_code == 302)

r = c.post("/entrar", data={"csrf": token(c), "usuario": USUARIO, "senha": "senhaErrada1"})
check("senha errada e recusada", r.status_code == 400)
check("nao diz se o usuario existe", "não conferem" in r.get_data(as_text=True))

r = c.post("/entrar", data={"csrf": token(c), "usuario": "ninguem", "senha": SENHA})
check("usuario inexistente da a mesma mensagem", "não conferem" in r.get_data(as_text=True))

r = c.post("/entrar", data={"csrf": token(c), "usuario": "Amigo.Teste", "senha": SENHA})
check("entra com o usuario em maiusculas", r.status_code == 302)

# ── Destino externo não pode ser usado para levar a pessoa para fora ────────
c2 = app.test_client()
r = c2.post("/entrar", data={"csrf": token(c2), "usuario": USUARIO, "senha": SENHA,
                             "proximo": "https://site-falso.exemplo"},
            query_string={"proximo": "https://site-falso.exemplo"})
check("nao redireciona para fora do app",
      "site-falso" not in (r.headers.get("Location") or ""))

# ── Viagens: o centro do app (estrutura A) ──────────────────────────────────
anon = app.test_client()
html = anon.get("/viagens").get_data(as_text=True)
check("sem conta, a tela de viagens explica e mostra o exemplo", "Organize a sua viagem" in html and 'href="/exemplo"' in html)
check("criar viagem exige estar logado", anon.get("/viagens/nova").status_code == 302)
check("quem entrou abre o app nas viagens, nao na pagina de venda", c.get("/").status_code == 302)

r = c.post("/viagens/nova", data={"destino": "Lisboa"})
check("criar viagem sem o segredo do formulario e recusado", r.status_code == 400)
r = c.post("/viagens/nova", data={"csrf": token(c, "/viagens/nova"), "destino": "Lisboa",
                                  "ida": "2027-04-10", "volta": "2027-04-01"})
check("volta antes da ida e recusada", r.status_code == 400 and "antes da ida" in r.get_data(as_text=True))
r = c.post("/viagens/nova", data={"csrf": token(c, "/viagens/nova"), "destino": "  Lisboa,   Portugal ",
                                  "ida": "2027-04-10", "volta": "2027-04-14",
                                  "pessoas": "Maya, Diego\nmaya\n Ana ,"})
check("viagem criada", r.status_code == 302)
vid = int(r.headers["Location"].rstrip("/").split("/")[-1])
check("as pessoas foram guardadas sem repetir nem vazio", db.count(db.viagem_pessoas) == 3)

r = c.get("/viagens")
check("com uma viagem so, o app abre direto nela", r.status_code == 302 and r.headers["Location"].endswith(f"/viagens/{vid}"))
check("e 'todas' mostra a lista", "Lisboa, Portugal" in c.get("/viagens?todas=1").get_data(as_text=True))
html = c.get(f"/viagens/{vid}/pessoas").get_data(as_text=True)
check("a viagem mostra quem vai e as datas",
      all(n in html for n in ("Maya", "Diego", "Ana")) and "10 a 14 de abr de 2027" in html)
check("cada parte da viagem abre",
      all(c.get(f"/viagens/{vid}/{a}").status_code == 200
          for a in ("roteiro", "gastos", "documentos", "pessoas", "ajustes")))
check("parte que nao existe da 404", c.get(f"/viagens/{vid}/nada").status_code == 404)
html = c.get(f"/viagens/{vid}/roteiro").get_data(as_text=True)
check("montar o roteiro ja leva destino, data e dias da viagem",
      "destination=Lisboa%2C%20Portugal" in html and "start_date=2027-04-10" in html and "days=5" in html)
html = c.get("/planejar?destination=Lisboa&start_date=2027-04-10&days=5").get_data(as_text=True)
check("e o formulario chega preenchido", 'value="Lisboa"' in html and 'value="2027-04-10"' in html)

terceiro = app.test_client()
criar(terceiro, "segundo.amigo", nome="Segundo")
check("a viagem de outra pessoa nao existe para quem nao e dono",
      terceiro.get(f"/viagens/{vid}/roteiro").status_code == 404)
check("nem da para apagar a viagem dos outros",
      terceiro.post(f"/viagens/{vid}/apagar",
                    data={"csrf": token(terceiro, "/conta"), "confirmo": "sim"}).status_code == 404)
check("nem ela aparece na lista de outra pessoa",
      "Lisboa, Portugal" not in terceiro.get("/viagens?todas=1").get_data(as_text=True))

c.post(f"/viagens/{vid}/pessoas", data={"csrf": token(c, f"/viagens/{vid}/pessoas"), "nome": "Bia"})
check("da para acrescentar alguem", db.count(db.viagem_pessoas) == 4)
with db.engine.connect() as cx:
    pid = cx.execute(select(db.viagem_pessoas.c.id).where(db.viagem_pessoas.c.nome == "Bia")).scalar_one()
c.post(f"/viagens/{vid}/pessoas/{pid}/tirar", data={"csrf": token(c, f"/viagens/{vid}/pessoas")})
check("e tirar alguem", db.count(db.viagem_pessoas) == 3)

r = c.post(f"/viagens/{vid}/apagar", data={"csrf": token(c, f"/viagens/{vid}/ajustes")})
check("apagar sem marcar a confirmacao nao apaga", db.count(db.viagens) == 1 and "erro=confirmar" in r.headers["Location"])
r = c.post(f"/viagens/{vid}/apagar", data={"csrf": token(c, f"/viagens/{vid}/ajustes"), "confirmo": "sim"})
check("com a confirmacao, a viagem e quem ia nela somem",
      db.count(db.viagens) == 0 and db.count(db.viagem_pessoas) == 0)

# ── A viagem de exemplo e os endereços antigos ──────────────────────────────
check("as quatro partes da viagem de exemplo abrem",
      all("Viagem de exemplo" in anon.get(f"/exemplo/{a}").get_data(as_text=True)
          for a in ("roteiro", "gastos", "documentos", "pessoas")))
r = anon.get("/orcamento")
check("endereco antigo leva ao lugar novo", r.status_code == 301 and r.headers["Location"].endswith("/exemplo/gastos"))

# ── Os roteiros reais ───────────────────────────────────────────────────────
html = c.get("/explorar").get_data(as_text=True)
check("explorar mostra o roteiro pesquisado", "Banff" in html)
check("e mostra o achado que muda a viagem", "Stampede" in html)
html = c.get("/explorar/banff-julho-2027").get_data(as_text=True)
check("o roteiro abre inteiro", "Moraine Lake" in html)
check("com as fontes anotadas", "parks.canada.ca" in html or "calgarystampede" in html)
check("endereco inventado da 404", c.get("/explorar/nao-existe").status_code == 404)
r = c.get("/viagens/banff-julho-2027")
check("o link antigo do roteiro continua chegando",
      r.status_code == 301 and r.headers["Location"].endswith("/explorar/banff-julho-2027"))

# ── Instalar no celular ─────────────────────────────────────────────────────
html = anon.get("/viagens").get_data(as_text=True)
check("toda pagina tem o botao de instalar", 'id="instalar"' in html)
check("e as instrucoes para iPhone", "Adicionar à Tela de Início" in html)

# ── A página que apresenta o Farol ──────────────────────────────────────────
import semente  # noqa: E402

html = anon.get("/").get_data(as_text=True)
md = open(os.path.join("conteudo", "banff.md"), encoding="utf-8").read()
check("a capa mostra a promessa", "Um plano que chega na hora certa" in html)
check("e a prova: o roteiro de Banff, com o achado",
      "Stampede" in html and "/explorar/banff-julho-2027" in html)
check("o numero de fontes da capa e o do roteiro",
      f"{len(semente._fontes(md))} fontes lidas" in html)

# O trecho desenhado na capa é uma afirmação sobre o roteiro. Se alguém mudar
# o .md, este teste avisa antes que a vitrine fique dizendo outra coisa.
trecho = semente.VITRINE["banff-julho-2027"]["trecho"]
fora = [f for passo in trecho for f in passo["no_md"] if f not in md]
check("cada parada e deslocamento do trecho esta escrito no roteiro", not fora)
check("e o trecho aparece na capa",
      all((p.get("lugar") or p.get("ida")) in html for p in trecho))

creditos = open(os.path.join("static", "fotos", "CREDITOS.md"), encoding="utf-8").read()
fotos_ok = all(
    os.path.exists(os.path.join("static", "fotos", f["arquivo"] + sufixo + ".jpg"))
    for f in semente.FOTOS.values() for sufixo in ("", "-800")
)
check("toda foto existe nos dois tamanhos", fotos_ok)
check("toda foto esta na lista de creditos",
      all(f["arquivo"] in creditos for f in semente.FOTOS.values()))
check("e o fotografo aparece na capa",
      all(semente.FOTOS[k]["autor"] in html for k in ("louise", "moraine", "moraine-nublado")))

check("o formulario de roteiro mudou para /planejar",
      'action="/plan"' in anon.get("/planejar").get_data(as_text=True))
check("quem esta logado tem a conta a um toque, tambem no celular",
      'href="/conta"' in c.get("/explorar").get_data(as_text=True))
check("e a conta tem o botao de sair", 'action="/sair"' in c.get("/conta").get_data(as_text=True))

# ── Trocar a senha ──────────────────────────────────────────────────────────
NOVA = "outraSenhaBoa456"
check("trocar senha exige estar logado",
      anon.get("/conta/senha").status_code == 302)

r = c.post("/conta/senha", data={"atual": SENHA, "nova": NOVA})
check("trocar senha sem o segredo do formulario e recusado", r.status_code == 400)

r = c.post("/conta/senha", data={"csrf": token(c, "/conta/senha"), "atual": "chuteErrado1", "nova": NOVA})
check("senha atual errada e recusada",
      r.status_code == 400 and "atual não confere" in r.get_data(as_text=True))

r = c.post("/conta/senha", data={"csrf": token(c, "/conta/senha"), "atual": SENHA, "nova": "curta"})
check("senha nova curta e recusada", r.status_code == 400)

r = c.post("/conta/senha", data={"csrf": token(c, "/conta/senha"), "atual": SENHA, "nova": NOVA})
corpo = r.get_data(as_text=True)
check("senha trocada", r.status_code == 200 and "Senha trocada" in corpo)
check("e nenhuma das duas senhas aparece na pagina", SENHA not in corpo and NOVA not in corpo)

outro = app.test_client()
r = outro.post("/entrar", data={"csrf": token(outro), "usuario": USUARIO, "senha": SENHA})
check("a senha antiga deixa de funcionar", r.status_code == 400)
r = outro.post("/entrar", data={"csrf": token(outro), "usuario": USUARIO, "senha": NOVA})
check("e a nova passa a funcionar", r.status_code == 302)

# ── A conta tem um lugar ────────────────────────────────────────────────────
check("a pagina da conta exige estar logado", anon.get("/conta").status_code == 302)
html = outro.get("/conta").get_data(as_text=True)
check("a pagina da conta leva a trocar a senha", 'href="/conta/senha"' in html)
check("e a aba com o nome leva a conta, nao ao painel de exemplo", 'href="/conta"' in html)

# ── Senha não vaza ──────────────────────────────────────────────────────────
# Formulário com senha enviado por GET põe a senha no endereço — e endereço
# fica no histórico do navegador e no registro do servidor.
import glob  # noqa: E402
import re as _re  # noqa: E402
ruins = []
for arq in glob.glob(os.path.join("templates", "*.html")):
    texto = open(arq, encoding="utf-8").read()
    for form in _re.findall(r"<form.*?</form>", texto, flags=_re.S | _re.I):
        if 'type="password"' in form and 'method="POST"' not in form.split(">", 1)[0]:
            ruins.append(os.path.basename(arq))
check("todo formulario com senha envia por POST", not ruins)

escrito = "".join(sys.stdout.texto + sys.stderr.texto)
check("nenhuma senha aparece no que o servidor escreveu",
      all(x not in escrito for x in (SENHA, NOVA, "senhaErrada1", "chuteErrado1")))

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

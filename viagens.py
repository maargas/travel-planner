"""As viagens de cada pessoa — o centro do app.

Estrutura A, escolhida pelo dono em 23/09/2026: você cria uma viagem, e tudo
dela mora lá dentro. Aqui ficam a lista das suas viagens, criar uma, as partes
de dentro (Roteiro, Gastos, Documentos, Pessoas, e os Ajustes) e a viagem de
exemplo, que mostra como tudo fica quando está preenchido.

Privacidade: uma viagem só existe para quem a criou. Para qualquer outra
pessoa, o endereço responde "não existe" (404), e não "proibido" — não há por
que contar a ninguém que aquela viagem existe.
"""
from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, abort, g
from sqlalchemy import select, insert, delete

import contas
from db import engine, viagens, viagem_pessoas

bp = Blueprint("viagens", __name__)

ABAS = [("roteiro", "Roteiro"), ("gastos", "Gastos"),
        ("documentos", "Documentos"), ("pessoas", "Pessoas")]
MAX_PESSOAS = 12
MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez"]

# A viagem de exemplo. Os mesmos dados das telas de exemplo (passagem de 2 de
# outubro, quatro pessoas), para que as quatro partes contem a mesma história.
EXEMPLO = {"destino": "Lisboa, Portugal", "ida": date(2026, 10, 2),
           "volta": date(2026, 10, 9), "pessoas": 4}
TELAS_EXEMPLO = {"roteiro": "exemplo_roteiro.html", "gastos": "orcamento.html",
                 "documentos": "documentos.html", "pessoas": "viajantes.html"}


# ── Texto de datas ──────────────────────────────────────────────────────────

def periodo(ida, volta):
    """'2 a 9 de out de 2026', '28 de set a 3 de out de 2026', ou 'Sem data'."""
    if not ida:
        return "Sem data"
    if not volta or volta == ida:
        return f"{ida.day} de {MESES[ida.month - 1]} de {ida.year}"
    if (ida.year, ida.month) == (volta.year, volta.month):
        return f"{ida.day} a {volta.day} de {MESES[volta.month - 1]} de {volta.year}"
    if ida.year == volta.year:
        return (f"{ida.day} de {MESES[ida.month - 1]} a "
                f"{volta.day} de {MESES[volta.month - 1]} de {volta.year}")
    return (f"{ida.day} de {MESES[ida.month - 1]} de {ida.year} a "
            f"{volta.day} de {MESES[volta.month - 1]} de {volta.year}")


def faltam(ida):
    """Dias até a ida, ou None se não houver data ou ela já passou."""
    if not ida:
        return None
    dias = (ida - date.today()).days
    return dias if dias >= 0 else None


# ── Leitura ─────────────────────────────────────────────────────────────────

def minhas_viagens():
    """As viagens de quem está logado, as próximas primeiro. Uma vez por página."""
    if "minhas_viagens" in g:
        return g.minhas_viagens
    eu = contas.usuario_atual()
    lista = []
    if eu:
        with engine.connect() as cx:
            linhas = cx.execute(
                select(viagens.c.id, viagens.c.destino, viagens.c.ida, viagens.c.volta)
                .where(viagens.c.user_id == eu["id"])
                # Sem data vai para o fim; com data, a mais próxima primeiro.
                .order_by(viagens.c.ida.is_(None), viagens.c.ida, viagens.c.id)
            ).mappings().all()
            contagem = {}
            if linhas:
                for (vid,) in cx.execute(
                    select(viagem_pessoas.c.viagem_id)
                    .where(viagem_pessoas.c.viagem_id.in_([l["id"] for l in linhas]))
                ):
                    contagem[vid] = contagem.get(vid, 0) + 1
        lista = [{**l, "pessoas": 1 + contagem.get(l["id"], 0)} for l in linhas]
    g.minhas_viagens = lista
    return lista


def _minha(vid):
    """A viagem, se for de quem está logado; senão, 404."""
    eu = contas.usuario_atual()
    with engine.connect() as cx:
        v = cx.execute(
            select(viagens).where(viagens.c.id == vid, viagens.c.user_id == eu["id"])
        ).mappings().first()
    if v is None:
        abort(404)
    return v


def _pessoas(vid):
    with engine.connect() as cx:
        return cx.execute(
            select(viagem_pessoas.c.id, viagem_pessoas.c.nome)
            .where(viagem_pessoas.c.viagem_id == vid)
            .order_by(viagem_pessoas.c.id)
        ).mappings().all()


# ── Validação ───────────────────────────────────────────────────────────────

def _data(texto):
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def _nomes(texto):
    """'Maya, Diego\\nAna' vira ['Maya', 'Diego', 'Ana'], sem repetir nem vazio."""
    vistos, nomes = set(), []
    for pedaco in (texto or "").replace("\n", ",").split(","):
        nome = " ".join(pedaco.split())[:60]
        if nome and nome.lower() not in vistos:
            vistos.add(nome.lower())
            nomes.append(nome)
    return nomes


def _problema(destino, ida, volta, texto_ida, texto_volta, nomes):
    hoje = date.today()
    if not destino:
        return "Escreva para onde é a viagem."
    if len(destino) > 120:
        return "O destino pode ter até 120 caracteres."
    if texto_ida and not ida or texto_volta and not volta:
        return "Uma das datas não é válida."
    if volta and not ida:
        return "Com data de volta, diga também a de ida."
    if ida and volta and volta < ida:
        return "A volta não pode ser antes da ida."
    # Um ano para trás, para quem quer organizar os gastos de uma viagem que
    # acabou; dois para a frente, como no resto do app.
    if ida and not (hoje - timedelta(days=365) <= ida <= hoje + timedelta(days=730)):
        return "A data de ida precisa estar entre um ano atrás e dois anos à frente."
    if volta and volta > (ida or hoje) + timedelta(days=90):
        return "Uma viagem pode ter até 90 dias."
    if len(nomes) > MAX_PESSOAS - 1:
        return f"Cabem até {MAX_PESSOAS} pessoas numa viagem, contando você."
    return None


# ── Telas ───────────────────────────────────────────────────────────────────

@bp.route("/viagens")
def lista():
    """Suas viagens. Com uma só, abre direto nela — é o combinado da estrutura
    A. O link "Suas viagens" de dentro da viagem manda ?todas=1 para ver a lista."""
    if contas.usuario_atual():
        lista = minhas_viagens()
        if len(lista) == 1 and not request.args.get("todas"):
            return redirect(f"/viagens/{lista[0]['id']}")
    return render_template("viagens.html")


@bp.route("/viagens/nova", methods=["GET", "POST"])
@contas.precisa_login
def nova():
    if request.method == "POST":
        if not contas.csrf_ok():
            return render_template("viagem_nova.html", erro="A página expirou. Tente de novo."), 400
        destino = " ".join((request.form.get("destino") or "").split())
        t_ida, t_volta = request.form.get("ida") or "", request.form.get("volta") or ""
        ida, volta = _data(t_ida), _data(t_volta)
        nomes = _nomes(request.form.get("pessoas"))
        erro = _problema(destino, ida, volta, t_ida.strip(), t_volta.strip(), nomes)
        if erro:
            return render_template("viagem_nova.html", erro=erro, destino=destino,
                                   ida=t_ida, volta=t_volta,
                                   pessoas=request.form.get("pessoas") or ""), 400
        with engine.begin() as cx:
            vid = cx.execute(insert(viagens).values(
                user_id=contas.usuario_atual()["id"], destino=destino, ida=ida, volta=volta,
            )).inserted_primary_key[0]
            if nomes:
                cx.execute(insert(viagem_pessoas), [{"viagem_id": vid, "nome": n} for n in nomes])
        return redirect(f"/viagens/{vid}")
    return render_template("viagem_nova.html")


@bp.route("/viagens/<int:vid>")
@contas.precisa_login
def abrir(vid):
    _minha(vid)
    return redirect(f"/viagens/{vid}/roteiro")


@bp.route("/viagens/<int:vid>/<aba>")
@contas.precisa_login
def parte(vid, aba):
    if aba not in dict(ABAS) and aba != "ajustes":
        abort(404)
    v = _minha(vid)
    return render_template("viagem.html", v=v, aba=aba, pessoas=_pessoas(vid),
                           erro=request.args.get("erro"))


@bp.post("/viagens/<int:vid>/pessoas")
@contas.precisa_login
def pessoa_nova(vid):
    if not contas.csrf_ok():
        abort(400)
    _minha(vid)
    nomes = _nomes(request.form.get("nome"))[:1]
    atuais = _pessoas(vid)
    if nomes and len(atuais) < MAX_PESSOAS - 1 \
            and nomes[0].lower() not in {p["nome"].lower() for p in atuais}:
        with engine.begin() as cx:
            cx.execute(insert(viagem_pessoas).values(viagem_id=vid, nome=nomes[0]))
    return redirect(f"/viagens/{vid}/pessoas")


@bp.post("/viagens/<int:vid>/pessoas/<int:pid>/tirar")
@contas.precisa_login
def pessoa_tirar(vid, pid):
    if not contas.csrf_ok():
        abort(400)
    _minha(vid)
    with engine.begin() as cx:
        cx.execute(delete(viagem_pessoas).where(
            viagem_pessoas.c.id == pid, viagem_pessoas.c.viagem_id == vid))
    return redirect(f"/viagens/{vid}/pessoas")


@bp.post("/viagens/<int:vid>/apagar")
@contas.precisa_login
def apagar(vid):
    """Apagar não tem volta, então pede uma confirmação marcada na própria página."""
    if not contas.csrf_ok():
        abort(400)
    _minha(vid)
    if request.form.get("confirmo") != "sim":
        return redirect(f"/viagens/{vid}/ajustes?erro=confirmar")
    with engine.begin() as cx:
        cx.execute(delete(viagem_pessoas).where(viagem_pessoas.c.viagem_id == vid))
        cx.execute(delete(viagens).where(viagens.c.id == vid))
    return redirect("/viagens?todas=1")


@bp.route("/viagens/<slug>")
def roteiro_antigo(slug):
    """Os roteiros publicados moravam em /viagens/<nome> e mudaram para Explorar.
    Link antigo (compartilhado, ou na tela de quem instalou) continua chegando."""
    return redirect(f"/explorar/{slug}", code=301)


# ── A viagem de exemplo ─────────────────────────────────────────────────────

@bp.route("/exemplo")
def exemplo():
    return redirect("/exemplo/roteiro")


@bp.route("/exemplo/<aba>")
def exemplo_parte(aba):
    if aba not in TELAS_EXEMPLO:
        abort(404)
    return render_template(TELAS_EXEMPLO[aba], aba=aba, exemplo=EXEMPLO)

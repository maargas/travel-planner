"""Criar conta, entrar e sair.

Guardar a senha de outra pessoa é uma responsabilidade de verdade, mesmo quando
são três amigos testando. Duas regras governam este arquivo:

1. A senha nunca é guardada. O que vai para o banco é o resultado do scrypt, do
   qual não se volta — nem eu, nem o dono do app, nem quem roubar o banco
   consegue ler a senha de ninguém.
2. A senha nunca aparece em log, em mensagem de erro, ou no endereço da página.

A conta é só um nome de usuário e uma senha, sem e-mail. Vantagem: o app não
guarda nenhum dado que identifique a pessoa fora dele. Preço: quem esquecer a
senha não tem como recuperá-la — não há para onde mandar o link. Enquanto são
poucos amigos testando, o dono resolve isso à mão.
"""
import hmac
import re
import secrets
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, session, url_for, g, abort,
)
from sqlalchemy import select, insert, update
from werkzeug.security import generate_password_hash, check_password_hash

from db import engine, users

bp = Blueprint("contas", __name__)

MIN_SENHA = 8
# Letras sem acento, números, ponto e sublinhado: o que funciona igual em
# qualquer teclado de celular, e o que não dá para confundir com outro usuário
# por causa de um acento ou de um espaço invisível.
USUARIO_RE = re.compile(r"^[a-z0-9_.]{3,24}$")


# ── Proteção contra formulário forjado ──────────────────────────────────────
# Sem isto, outro site pode fazer o navegador de quem está logado enviar um
# formulário para cá sem a pessoa perceber. O segredo fica na sessão e tem de
# vir de volta junto com o envio.

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_ok():
    enviado = request.form.get("csrf", "")
    guardado = session.get("csrf", "")
    # compare_digest e não `==`: comparar segredo caractere a caractere vaza,
    # pelo tempo da comparação, quantos caracteres estavam certos.
    return bool(guardado) and hmac.compare_digest(enviado, guardado)


# ── Quem está logado ────────────────────────────────────────────────────────

def usuario_atual():
    """A pessoa logada, ou None. Lida uma vez por requisição."""
    if "user" in g:
        return g.user
    uid = session.get("uid")
    g.user = None
    if uid:
        with engine.connect() as cx:
            linha = cx.execute(
                select(users.c.id, users.c.username, users.c.name).where(users.c.id == uid)
            ).first()
        # A conta pode ter sumido desde que o cookie foi emitido.
        g.user = dict(linha._mapping) if linha else None
        if g.user is None:
            session.pop("uid", None)
    return g.user


def precisa_login(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if usuario_atual() is None:
            return redirect(url_for("contas.entrar", proximo=request.path))
        return view(*a, **kw)
    return wrapper


# ── Validação ───────────────────────────────────────────────────────────────

def _normaliza(usuario):
    """'  Ana.Silva ' vira 'ana.silva'. Um '@' do começo é aceito e descartado,
    porque muita gente escreve o próprio usuário como em rede social."""
    return (usuario or "").strip().lower().lstrip("@")


def _problema(nome, usuario, senha):
    if not nome or len(nome) > 80:
        return "Escreva seu nome."
    if not USUARIO_RE.match(usuario):
        return ("O nome de usuário precisa ter de 3 a 24 caracteres: letras sem "
                "acento, números, ponto ou sublinhado.")
    if len(senha or "") < MIN_SENHA:
        return f"A senha precisa ter pelo menos {MIN_SENHA} caracteres."
    return None


def _destino_seguro(proximo):
    """Só aceita caminho interno.

    Um `proximo` vindo da URL é escrito por quem mandou o link. Sem esta
    checagem, um link de login com `?proximo=https://site-falso` levaria a
    pessoa para fora logo depois de entrar, com a aparência de ter sido o app.
    """
    if proximo and proximo.startswith("/") and not proximo.startswith("//"):
        return proximo
    return "/viagens"


# ── Telas ───────────────────────────────────────────────────────────────────

@bp.route("/criar-conta", methods=["GET", "POST"])
def criar_conta():
    proximo = _destino_seguro(request.values.get("proximo"))
    if usuario_atual():
        return redirect(proximo)

    if request.method == "POST":
        if not csrf_ok():
            return render_template("entrar.html", aba="criar", proximo=proximo,
                                   erro="A página expirou. Tente de novo."), 400

        nome = (request.form.get("nome") or "").strip()
        usuario = _normaliza(request.form.get("usuario"))
        senha = request.form.get("senha") or ""

        erro = _problema(nome, usuario, senha)
        if erro:
            return render_template("entrar.html", aba="criar", erro=erro,
                                   nome=nome, digitado=usuario, proximo=proximo), 400

        with engine.begin() as cx:
            existe = cx.execute(select(users.c.id).where(users.c.username == usuario)).first()
            if existe:
                return render_template("entrar.html", aba="criar", nome=nome, digitado=usuario,
                                       proximo=proximo,
                                       erro="Esse nome de usuário já está em uso. Escolha outro."), 400
            novo = cx.execute(insert(users).values(
                username=usuario, name=nome,
                password_hash=generate_password_hash(senha),
            ))
            uid = novo.inserted_primary_key[0]

        # Sessão nova depois de autenticar, para que um identificador de sessão
        # obtido antes do login não continue valendo depois dele.
        session.clear()
        session["uid"] = uid
        session.permanent = True
        return redirect(proximo)

    return render_template("entrar.html", aba="criar", proximo=proximo)


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    proximo = _destino_seguro(request.values.get("proximo"))
    if usuario_atual():
        return redirect(proximo)

    if request.method == "POST":
        if not csrf_ok():
            return render_template("entrar.html", aba="entrar", proximo=proximo,
                                   erro="A página expirou. Tente de novo."), 400

        usuario = _normaliza(request.form.get("usuario"))
        senha = request.form.get("senha") or ""

        with engine.connect() as cx:
            linha = cx.execute(
                select(users.c.id, users.c.password_hash).where(users.c.username == usuario)
            ).first()

        # Uma só mensagem para "usuário não existe" e "senha errada". Duas
        # mensagens diferentes contam a quem tenta quais usuários existem.
        if linha is None or not check_password_hash(linha.password_hash, senha):
            return render_template("entrar.html", aba="entrar", digitado=usuario, proximo=proximo,
                                   erro="Usuário ou senha não conferem."), 400

        session.clear()
        session["uid"] = linha.id
        session.permanent = True
        return redirect(proximo)

    return render_template("entrar.html", aba="entrar", proximo=proximo)


@bp.post("/sair")
def sair():
    if not csrf_ok():
        abort(400)
    session.clear()
    return redirect("/")


@bp.route("/conta")
@precisa_login
def conta():
    """O lugar de tudo que é da pessoa: quem ela é, trocar a senha, sair.

    Antes, a aba com o nome dela levava ao painel de exemplo, e trocar a senha
    era um link escondido no pé da página — ninguém achava.
    """
    return render_template("conta.html")


@bp.route("/conta/senha", methods=["GET", "POST"])
@precisa_login
def trocar_senha():
    """Trocar a senha, sabendo a atual.

    Pedir a atual impede que alguém com o celular destravado de outra pessoa
    troque a senha dela e fique com a conta.

    Limite conhecido: outros aparelhos em que a pessoa já entrou continuam
    logados. A sessão mora num cookie assinado, e não no banco, então não há
    uma lista de sessões para apagar. Derrubar todas exigiria um contador na
    tabela de usuários — fica para quando houver motivo.
    """
    eu = usuario_atual()
    if request.method == "POST":
        if not csrf_ok():
            return render_template("senha.html", erro="A página expirou. Tente de novo."), 400

        atual = request.form.get("atual") or ""
        nova = request.form.get("nova") or ""

        with engine.connect() as cx:
            guardado = cx.execute(
                select(users.c.password_hash).where(users.c.id == eu["id"])
            ).scalar_one()
        if not check_password_hash(guardado, atual):
            return render_template("senha.html", erro="A senha atual não confere."), 400
        if len(nova) < MIN_SENHA:
            return render_template("senha.html",
                                   erro=f"A senha nova precisa ter pelo menos {MIN_SENHA} caracteres."), 400
        if nova == atual:
            return render_template("senha.html",
                                   erro="A senha nova precisa ser diferente da atual."), 400

        with engine.begin() as cx:
            cx.execute(update(users).where(users.c.id == eu["id"])
                       .values(password_hash=generate_password_hash(nova)))

        # Sessão nova neste aparelho, como no login.
        session.clear()
        session["uid"] = eu["id"]
        session.permanent = True
        return render_template("senha.html", feito=True)

    return render_template("senha.html")

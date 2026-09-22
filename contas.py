"""Criar conta, entrar e sair.

Guardar a senha de outra pessoa é uma responsabilidade de verdade, mesmo quando
são três amigos testando. Duas regras governam este arquivo:

1. A senha nunca é guardada. O que vai para o banco é o resultado do scrypt, do
   qual não se volta — nem eu, nem o dono do app, nem quem roubar o banco
   consegue ler a senha de ninguém.
2. A senha nunca aparece em log, em mensagem de erro, ou no endereço da página.
"""
import hmac
import os
import re
import secrets
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, session, url_for, g, abort,
)
from sqlalchemy import select, insert
from werkzeug.security import generate_password_hash, check_password_hash

from db import engine, users

bp = Blueprint("contas", __name__)

MIN_SENHA = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
                select(users.c.id, users.c.email, users.c.name).where(users.c.id == uid)
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

def _problema(nome, email, senha):
    if not nome or len(nome) > 80:
        return "Escreva seu nome."
    if not EMAIL_RE.match(email or ""):
        return "Esse e-mail não parece válido."
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
    return "/painel"


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
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""

        erro = _problema(nome, email, senha)
        if erro:
            return render_template("entrar.html", aba="criar", erro=erro,
                                   nome=nome, email=email, proximo=proximo), 400

        with engine.begin() as cx:
            existe = cx.execute(select(users.c.id).where(users.c.email == email)).first()
            if existe:
                return render_template("entrar.html", aba="criar", nome=nome, email=email,
                                       proximo=proximo,
                                       erro="Já existe uma conta com esse e-mail. Entre por ali."), 400
            novo = cx.execute(insert(users).values(
                email=email, name=nome,
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

        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""

        with engine.connect() as cx:
            linha = cx.execute(
                select(users.c.id, users.c.password_hash).where(users.c.email == email)
            ).first()

        # Uma só mensagem para "e-mail não existe" e "senha errada". Duas
        # mensagens diferentes contam a quem tenta se aquele e-mail tem conta.
        if linha is None or not check_password_hash(linha.password_hash, senha):
            return render_template("entrar.html", aba="entrar", email=email, proximo=proximo,
                                   erro="E-mail ou senha não conferem."), 400

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

"""Sobe o Farol já "logado", só para olhar as telas de conta no navegador.

Nada aqui toca banco de verdade: o endereço aponta para um arquivo descartável
na pasta temporária, definido antes de o app ler o .env (e o .env não
sobrescreve o que já está definido). O usuário é de mentira, com uma senha
sorteada que ninguém digita nem vê. Nada disto existe no app publicado — só
este lançador faz o login automático.

    Usado pelo .claude/launch.json, configuração "farol-logado", porta 5002.
"""
import os
import secrets
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)

os.environ["MOCK_MODE"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.gettempdir(), "farol_ver_logado.db").replace("\\", "/")

import app  # noqa: E402
import db  # noqa: E402
from flask import session  # noqa: E402
from sqlalchemy import delete, insert  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

assert db.kind() == "sqlite", "o lançador de teste só pode usar banco descartável"

with db.engine.begin() as cx:
    cx.execute(delete(db.viagem_pessoas))
    cx.execute(delete(db.viagens))
    cx.execute(delete(db.requests_table))
    cx.execute(delete(db.users))
    uid = cx.execute(insert(db.users).values(
        username="visitante", name="Visitante",
        password_hash=generate_password_hash(secrets.token_urlsafe(32)),
    )).inserted_primary_key[0]
    # Uma viagem de mentira, só neste banco descartável, para ver as telas cheias.
    from datetime import date
    vid = cx.execute(insert(db.viagens).values(
        user_id=uid, destino="Buenos Aires, Argentina",
        ida=date(2026, 11, 12), volta=date(2026, 11, 16),
    )).inserted_primary_key[0]
    cx.execute(insert(db.viagem_pessoas), [{"viagem_id": vid, "nome": n} for n in ("Maya", "Diego")])


@app.app.before_request
def _ja_logado():
    session["uid"] = uid


app.app.run(port=5002, debug=False)

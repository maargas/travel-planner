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
# O visitante de mentira também é o "dono", para dar para ver a fila.
os.environ["FAROL_DONO"] = "visitante"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.gettempdir(), "farol_ver_logado.db").replace("\\", "/")

import app  # noqa: E402
import db  # noqa: E402
from flask import session  # noqa: E402
from sqlalchemy import delete, insert  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

assert db.kind() == "sqlite", "o lançador de teste só pode usar banco descartável"

with db.engine.begin() as cx:
    cx.execute(delete(db.requests_table))
    cx.execute(delete(db.users))
    uid = cx.execute(insert(db.users).values(
        username="visitante", name="Visitante",
        password_hash=generate_password_hash(secrets.token_urlsafe(32)),
    )).inserted_primary_key[0]
    # Dois pedidos de exemplo, só neste banco descartável.
    from datetime import date
    cx.execute(insert(db.requests_table), [
        {"user_id": uid, "destination": "Lisboa, Portugal", "start_date": date(2027, 4, 10),
         "days": 5, "budget_usd": 1500, "interests": "comida local, miradouros",
         "status": "na fila"},
        {"user_id": uid, "destination": "Buenos Aires", "start_date": None,
         "days": 4, "budget_usd": None, "interests": None, "status": "pesquisando"},
    ])


@app.app.before_request
def _ja_logado():
    session["uid"] = uid


app.app.run(port=5002, debug=False)

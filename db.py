"""Onde as contas e os roteiros ficam guardados.

Um endereço decide tudo: sem `DATABASE_URL` o banco é um arquivo no seu
computador, e com ele é o Postgres lá do Neon. O resto do código não sabe a
diferença, então trocar de banco é trocar uma variável — nunca reescrever
consulta.
"""
import os
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text, Date,
    DateTime, ForeignKey, UniqueConstraint, select, func,
)

# Sem endereço, um arquivo local. Serve para desenvolver e para os testes; no
# Render ele não sobrevive a uma republicação, e é por isso que o de verdade
# mora no Neon.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///compass.db")

# Provedores de Postgres entregam o endereço no formato antigo `postgres://`, que
# o SQLAlchemy 2 não reconhece, e sem dizer qual driver usar. Corrigir aqui evita
# que alguém tenha que editar a string colada do painel do Neon.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# `pool_pre_ping` porque o Neon desliga a conexão quando fica ocioso: sem isso a
# primeira visita depois de um tempo parado recebe um erro de conexão morta.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

meta = MetaData()


def _now():
    return datetime.now(timezone.utc)


users = Table(
    "users", meta,
    Column("id", Integer, primary_key=True),
    # Nome de usuário, e não e-mail: por enquanto o app não guarda nenhum dado
    # que identifique a pessoa fora dele. Sempre em minúsculas, para que "Ana" e
    # "ana" não virem duas contas.
    Column("username", String(24), nullable=False, unique=True),
    Column("name", String(80), nullable=False),
    # Nunca a senha: o resultado do scrypt, do qual não se volta.
    Column("password_hash", String(255), nullable=False),
    Column("created_at", DateTime, default=_now),
)

# Os roteiros de verdade, pesquisados à mão. O app não os inventa: ele os serve.
trips = Table(
    "trips", meta,
    Column("id", Integer, primary_key=True),
    Column("slug", String(80), nullable=False, unique=True),
    Column("destination", String(120), nullable=False),
    Column("country", String(80), nullable=False),
    Column("start_date", Date),
    Column("days", Integer),
    Column("budget_usd", Integer),
    Column("summary", Text),          # a frase que aparece no cartão
    Column("headline", Text),         # o achado que muda a viagem
    Column("body_md", Text),          # o roteiro inteiro, em markdown
    Column("scene", String(40)),      # qual diorama ilustra o cartão
    Column("researched_on", Date),    # quando as fontes foram lidas
    Column("created_at", DateTime, default=_now),
)

trip_sources = Table(
    "trip_sources", meta,
    Column("id", Integer, primary_key=True),
    Column("trip_id", Integer, ForeignKey("trips.id"), nullable=False),
    Column("title", String(255), nullable=False),
    Column("url", String(500), nullable=False),
)

saved = Table(
    "saved", meta,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("trip_id", Integer, ForeignKey("trips.id"), nullable=False),
    Column("created_at", DateTime, default=_now),
    UniqueConstraint("user_id", "trip_id", name="uq_saved"),
)

# Quando alguém pede um destino que ainda não existe, o pedido entra aqui em vez
# de virar uma chamada paga à API. Alguém pesquisa e publica depois.
requests_table = Table(
    "requests", meta,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("destination", String(120), nullable=False),
    Column("start_date", Date),
    Column("days", Integer),
    Column("budget_usd", Integer),
    Column("interests", String(255)),
    Column("status", String(20), default="na fila"),
    Column("created_at", DateTime, default=_now),
)


def init():
    """Cria o que faltar. Não apaga nem altera o que já existe."""
    meta.create_all(engine)


def kind():
    """'postgres' ou 'sqlite' — só para o app poder dizer onde está guardando."""
    return "postgres" if engine.dialect.name.startswith("postgres") else "sqlite"


def count(table):
    with engine.connect() as cx:
        return cx.execute(select(func.count()).select_from(table)).scalar_one()

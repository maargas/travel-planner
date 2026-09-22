"""Carrega no banco os roteiros pesquisados à mão.

O app não inventa estes roteiros: eles foram escritos com pesquisa na web, com
as fontes lidas e anotadas, e ficam em `conteudo/` como arquivos de texto. Este
arquivo só os coloca no banco.

Rodar duas vezes não duplica nada — cada roteiro tem um apelido único, e um
apelido que já existe é atualizado em vez de inserido.
"""
import os
import re
from datetime import date

from sqlalchemy import select, insert, update, delete

from db import engine, trips, trip_sources

CONTEUDO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conteudo")

# O que o cartão mostra antes de alguém abrir o roteiro. Fica aqui, e não dentro
# do markdown, porque é texto de vitrine e não de conteúdo.
CATALOGO = [
    {
        "slug": "banff-julho-2027",
        "arquivo": "banff.md",
        "destination": "Banff",
        "country": "Canadá",
        "start_date": date(2027, 7, 12),
        "days": 5,
        "budget_usd": 2500,
        "scene": "montanha",
        "researched_on": date(2026, 9, 19),
        "summary": "Lagos glaciais, ônibus em vez de carro, e uma semana em que a "
                   "cidade do aeroporto está tomada por um rodeio.",
        "headline": "O Calgary Stampede acontece de 9 a 18 de julho de 2027 — "
                    "a viagem inteira cai dentro dele, e Calgary é o aeroporto de Banff.",
    },
]


def _fontes(markdown):
    """Tira a lista de fontes do fim do arquivo.

    Elas aparecem como itens de lista em markdown: `- [título](endereço)`.
    """
    corte = markdown.find("## Fontes consultadas")
    if corte == -1:
        return []
    achados = re.findall(r"^- \[([^\]]+)\]\((https?://[^)]+)\)",
                         markdown[corte:], flags=re.M)
    return [{"title": t.strip()[:255], "url": u.strip()[:500]} for t, u in achados]


def carregar():
    """Põe no banco tudo que estiver no catálogo. Devolve quantos entraram."""
    n = 0
    for item in CATALOGO:
        caminho = os.path.join(CONTEUDO, item["arquivo"])
        if not os.path.exists(caminho):
            print(f"[semente] faltou o arquivo {caminho}, pulando", flush=True)
            continue

        with open(caminho, encoding="utf-8") as fh:
            corpo = fh.read()

        valores = {k: v for k, v in item.items() if k != "arquivo"}
        valores["body_md"] = corpo

        with engine.begin() as cx:
            existe = cx.execute(
                select(trips.c.id).where(trips.c.slug == item["slug"])
            ).first()

            if existe:
                cx.execute(update(trips).where(trips.c.id == existe.id).values(**valores))
                trip_id = existe.id
                # As fontes são reescritas por inteiro: é mais simples do que
                # descobrir quais mudaram, e são poucas.
                cx.execute(delete(trip_sources).where(trip_sources.c.trip_id == trip_id))
            else:
                novo = cx.execute(insert(trips).values(**valores))
                trip_id = novo.inserted_primary_key[0]
                n += 1

            for f in _fontes(corpo):
                cx.execute(insert(trip_sources).values(trip_id=trip_id, **f))

    return n


if __name__ == "__main__":
    import db
    db.init()
    novos = carregar()
    print(f"[semente] {novos} roteiro(s) novo(s); {db.count(trips)} no total")

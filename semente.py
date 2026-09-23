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


# As fotos do app. Regra: toda foto é do lugar de verdade, com o crédito do
# fotógrafo — a lista completa, com o endereço de cada uma, está em
# static/fotos/CREDITOS.md. Cada foto existe em dois tamanhos: o original, de
# 1600 px, e um de 800 px com o sufixo -800, que é o que o celular baixa.
FOTOS = {
    "moraine": {
        "arquivo": "moraine-lake-woolliscroft",
        "lugar": "Moraine Lake",
        "autor": "Tim Woolliscroft",
        "alt": "Moraine Lake, lago azul-esverdeado cercado de picos, visto do alto do Rockpile",
    },
    "moraine-nublado": {
        "arquivo": "moraine-lake-khandelwal",
        "lugar": "Moraine Lake",
        "autor": "Nandini Khandelwal",
        "alt": "Moraine Lake num dia nublado, com as montanhas atrás",
    },
    "louise": {
        "arquivo": "lake-louise-vanermen",
        "lugar": "Lake Louise",
        "autor": "Febe Vanermen",
        "alt": "Lake Louise ao nascer do sol, com a geleira Victoria ao fundo",
    },
}

# O que a vitrine mostra de cada roteiro além do texto: a foto da capa e um
# trecho de um dia, que vai na primeira tela do site.
#
# O trecho é uma afirmação sobre o roteiro, então segue as regras dele. Cada
# parada e cada deslocamento trazem, em `no_md`, as frases do .md que os
# sustentam, e `teste_contas.py` confere que elas continuam lá: se alguém mudar
# o roteiro, a vitrine não fica dizendo outra coisa. A etiqueta diz só o que o
# roteiro diz — "aberto sempre" onde ele diz isso, "horário estimado" onde ele
# marcou estimativa.
VITRINE = {
    "banff-julho-2027": {
        "foto": "moraine",
        "trecho_dia": "Dia 2",
        "trecho": [
            {"hora": "07:00", "lugar": "Moraine Lake", "etiqueta": "sem carro particular",
             "tipo": "info",
             "no_md": ["07:00 · Moraine Lake", "Moraine Lake não aceita mais carro particular"]},
            {"ida": "~20 min · ônibus",
             "no_md": ["Lake Connector, cerca de 20 min entre os dois lagos"]},
            {"hora": "10:00", "lugar": "Lake Louise", "etiqueta": "aberto sempre", "tipo": "ok",
             "no_md": ["10:00 · Lake Louise", "sem portão, aberto sempre"]},
            {"ida": "~1h15 · subida a pé", "no_md": ["cerca de 1h15 subindo"]},
            {"hora": "13:00", "lugar": "Lake Agnes", "etiqueta": "horário estimado",
             "tipo": "estimativa",
             "no_md": ["13:00 · Chá de Lake Agnes", "fecha 17h — estimativa"]},
        ],
    },
}


def vitrine(slug):
    """A foto e o trecho de um roteiro, ou um dicionário vazio se não houver."""
    v = VITRINE.get(slug, {})
    return {**v, "foto": FOTOS.get(v.get("foto"))} if v else {}


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

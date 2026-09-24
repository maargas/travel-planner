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
    # `posicao` diz que parte da foto fica à vista quando ela é cortada para
    # caber na tela (a foto vertical numa tela larga, por exemplo).
    "jeronimos": {
        "arquivo": "jeronimos-deidda",
        "lugar": "Mosteiro dos Jerónimos",
        "autor": "Vanessa Deidda",
        "alt": "A torre do Mosteiro dos Jerónimos, em pedra clara, contra o céu azul",
        "posicao": "center 35%",
    },
    "louvre": {
        "arquivo": "louvre-nozina",
        "lugar": "Museu do Louvre",
        "autor": "Tomáš Nožina",
        "alt": "A pirâmide de vidro do Louvre num dia de sol",
        "posicao": "center 55%",
    },
    "iguacu": {
        "arquivo": "iguacu-dallcol",
        "lugar": "Cataratas do Iguaçu",
        "autor": "Marcus Dall Col",
        "alt": "As Cataratas do Iguaçu vistas do lado brasileiro, com um arco-íris sobre o rio",
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


# A capa da página inicial: várias fotos, cada uma com um trecho de roteiro
# desenhado por cima. Banff é trecho do roteiro publicado (conferido contra o
# .md, pela VITRINE acima). Os outros são exemplos só da capa: cada horário,
# etiqueta e deslocamento foi conferido nas páginas de `fontes`, na data de
# `conferido_em`. Horário e dia de fechamento mudam — reconferir antes de mexer.
#
# `chegada` é o deslocamento até a primeira parada, quando ele importa.
# `~` marca minuto estimado. (A capa só troca as fotos, sozinha — o dono não
# quis botão de lugar nem de ônibus/carro nela.)
CAPA = [
    {
        "id": "banff", "foto": "moraine", "foto_cel": "louise",
        "lugar": "Banff, Canadá", "dia": "Dia 2", "roteiro": "banff-julho-2027",
        "conferido_em": date(2026, 9, 24),
        "trecho": VITRINE["banff-julho-2027"]["trecho"],
        "fontes": ["conteudo/banff.md"],
    },
    {
        "id": "lisboa", "foto": "jeronimos",
        "lugar": "Belém, Lisboa", "dia": "Uma manhã (de terça a domingo)",
        "conferido_em": date(2026, 9, 24),
        "trecho": [
                {"hora": "09:00", "lugar": "Pastéis de Belém", "etiqueta": "abre às 8h, todo dia",
                 "tipo": "ok"},
                {"ida": "~5 min a pé"},
                {"hora": "09:30", "lugar": "Mosteiro dos Jerónimos", "etiqueta": "fecha às segundas",
                 "tipo": "info"},
                {"ida": "~15 min a pé"},
                {"hora": "11:30", "lugar": "Torre de Belém",
                 "etiqueta": "60 entradas a cada meia hora", "tipo": "info"},
        ],
        "fontes": [
            "https://mosteirojeronimos.torrebelem.gov.pt/visitar",
            "https://observador.pt/2026/05/26/torre-de-belem-reabre-apos-um-ano-de-obras-com-entradas-limitadas-a-900-por-dia-para-reduzir-filas/",
            "https://pasteisdebelem.pt/contactos/",
        ],
    },
    {
        "id": "paris", "foto": "louvre",
        "lugar": "Paris, França", "dia": "Uma quarta-feira",
        "conferido_em": date(2026, 9, 24),
        "trecho": [
                {"hora": "09:00", "lugar": "Museu do Louvre", "etiqueta": "fecha às terças",
                 "tipo": "info"},
                {"ida": "~15 min a pé, pela Pont Royal"},
                {"hora": "14:00", "lugar": "Musée d'Orsay",
                 "etiqueta": "fecha às segundas · reserve o horário", "tipo": "info"},
        ],
        "fontes": [
            "https://www.louvre.fr/en/visit/hours-admission",
            "https://www.musee-orsay.fr/en/visit/admission-opening-times-tickets",
            "https://www.musee-orsay.fr/fr/visiter",
        ],
    },
    {
        "id": "foz", "foto": "iguacu",
        "lugar": "Foz do Iguaçu, Brasil", "dia": "Um dia de semana",
        "conferido_em": date(2026, 9, 24),
        "chegada": "~40 min de ônibus do centro (linha 120)",
        "trecho": [
            {"hora": "09:00", "lugar": "Cataratas do Iguaçu", "etiqueta": "abre às 9h em dia útil",
             "tipo": "ok"},
            {"ida": "ônibus do parque até a entrada + ~5 min a pé"},
            {"hora": "14:00", "lugar": "Parque das Aves", "etiqueta": "entrada até 16h30 (inverno)",
             "tipo": "estimativa"},
        ],
        "fontes": [
            "https://cataratasdoiguacu.com.br/",
            "https://www.parquedasaves.com.br/blog/parque-das-aves-foz-do-iguacu-novo-horario/",
            "https://www.viajenaviagem.com/destino/foz-do-iguacu/como-se-locomover/",
        ],
    },
]


def capa():
    """Os exemplos da capa, já com as fotos resolvidas."""
    return [{**c, "foto": FOTOS[c["foto"]], "foto_cel": FOTOS[c.get("foto_cel", c["foto"])]}
            for c in CAPA]


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

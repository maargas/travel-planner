# Compass — planejador de viagens

App de roteiros de viagem para **quem viaja pouco** e vai a um lugar que não
conhece. O dono (Gabriel, estudante da FGV) não programa e está aprendendo.
O nome "Compass" é **provisório** — a marca ainda está sendo decidida.

A promessa, que manda em toda decisão: **precisão verificável**. O app nasceu
porque uma IA sugeriu um museu a um amigo dele na Alemanha enquanto um evento de
Fórmula 1 acontecia nas datas da viagem. Toda mudança que aumenta a chance de
uma informação errada chegar ao viajante é uma regressão, por mais bonita que seja.

- Preço marcado como **confirmado** (lido numa página) ou **estimativa**. Nunca
  preço de passagem aérea. Se não couber no orçamento, dizer na cara.
- Horário de abertura segue a mesma regra do preço.
- Cada pulo entre duas paradas tem o meio de transporte e os minutos.
- Foto de destino tem de ser **do lugar de verdade**, com crédito ao fotógrafo.

## Regras que não se quebram

1. **Nunca gastar o console da Anthropic.** O saldo está perto de zero. O site
   público roda em modo demonstração (sem `ANTHROPIC_API_KEY` no Render). Os
   roteiros reais são pesquisados à mão, em conversa, e ficam em `conteudo/`.
   Nunca rodar o app em modo real sem o dono pedir e saber o custo.
2. **Nunca vazar segredo.** `.env`, `*.db` e `roteiros/` estão no `.gitignore` —
   conferir antes de todo commit. Endereço de banco e `SECRET_KEY` o dono cola
   direto no painel do Render; ninguém cola isso numa conversa.
3. **Nunca criar conta nem digitar senha** em nome do dono.
4. **Perguntar antes de decisão grande**, e dar opções com recomendação.

## Como testar

```
python teste_modo_real.py   # caminho pago com a API falsificada — não gasta nada
python teste_contas.py      # contas, senha, fila de pedidos, instalação
```

Os dois têm de passar antes de todo commit. Para ver no navegador, o
`.claude/launch.json` sobe o servidor em modo demonstração na porta 5001.

## Como falar com o dono

- Português simples. Explicar o porquê, não só o quê.
- **Toda resposta termina com "O que você precisa fazer"**: numerado, cada item
  com o motivo. Comando em bloco `bash` separado, um por bloco.
- Não afirmar número, preço, data ou fato sem ter conferido. Se não conferiu,
  dizer que não conferiu.
- Ele usa PowerShell no Windows: `VAR=valor comando` não funciona lá.

## Decisões de design já tomadas

Base: pesquisa que ele aprovou — atração julgada em 50 ms; site simples e
"com cara de site de viagem" ganha; o que é bonito parece mais fácil de usar;
nome concreto que vira símbolo (a referência é a marca Caju).

- **Celular:** "Foto e vidro" — foto em tela cheia, botões em vidro fosco,
  destaque verde-limão. O roteiro longo fica em fundo sólido.
- **Site no computador:** a estrutura de "A rota" (a capa mostra um trecho de
  roteiro com horários e minutos entre paradas — vende o produto, tem caráter
  de negócio) com a beleza de "Foto e vidro", para bater com o app.
- Esboços publicados em https://claude.ai/artifact/XrZafrc9AQLpdmsCGiVTrc

## Marca

Ainda em aberto. Nomes já recusados — **não repetir**: atlas, luma, duna, orla,
aria, marea, sotavento, maré, vereda, alísio, rumo, delta, baliza, preamar,
arribada, carimbo. O nome precisa soar igual em português e inglês (sem lh, nh,
ão, ç, acento nem o "j" brasileiro). O que o dono mais pesa: **ligação com o
propósito**, depois apelo visual do símbolo, depois facilidade de falar.

## Onde as coisas estão

- `app.py` — rotas, modo real vs demonstração, tetos de gasto
- `contas.py` — conta só com nome de usuário e senha (sem e-mail, de propósito)
- `db.py` — `DATABASE_URL` escolhe o banco: sem ela, SQLite local
- `semente.py` + `conteudo/` — roteiros reais, carregados a cada arranque
- `templates/_cenas.html` — dioramas em SVG, cada cena com as cores dela
- `static/sw.js` — instalação no celular; **nunca** guarda página, só `/static/`

## Publicação

Render, serviço criado à mão: **não lê o `render.yaml`**. Variável nova se põe
no painel do Render. O plano grátis dorme após 15 min sem visita (~50 s para
acordar). Banco permanente: Neon, ainda pendente — até lá, conta criada no site
some a cada publicação.

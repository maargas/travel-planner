# Farol — planejador de viagens

App de roteiros de viagem para **quem viaja pouco** e vai a um lugar que não
conhece. O dono (Gabriel, estudante da FGV) não programa e está aprendendo.
O nome é **Farol** (decidido em 22/09/2026, depois de quatro rodadas). A ideia
vem das palavras dele: o app tem de "ser um norte pra qualquer um".

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
- **Construído em 22/09/2026.** `/` é a página que vende (capa com foto, como
  funciona, a prova de Banff, o convite); o formulário foi para `/planejar`.
  Cores: marinho `#0f1b2d`, limão `#c6f36a`, fundo `#f3f6f9`; letra Plus
  Jakarta Sans. Os cinco temas antigos saíram — o visual agora é um só.
- O trecho da capa (`semente.VITRINE`) é afirmação sobre o roteiro: cada
  parada traz as frases do .md que a sustentam, e o teste confere. Etiqueta
  diz só o que o roteiro diz ("aberto sempre", "horário estimado").
- Foto: sempre do lugar de verdade, em dois tamanhos (1600 e `-800`), com o
  crédito visível na tela e em `static/fotos/CREDITOS.md`.

## Marca

**Farol.** Decidido — ele disse que não quer mais gastar tempo com nome. Não
reabrir o assunto por conta própria.

- Símbolo: farol gordinho, torre vermelha com faixa creme, lanterna amarela,
  cúpula e pedra azul-marinho, facho aceso para os dois lados. Fonte da verdade:
  `static/farol.svg`. Cores: vermelho `#c8382e`, amarelo `#ffc93c`, marinho
  `#1f3a5f`, creme `#fff6e6`.
- Nome escrito em **Fredoka 600** (arredondada) — só na marca.
- Ícones PNG gerados a partir do mesmo desenho: `icon-192`, `icon-512`,
  `icon-maskable-512` (com margem para o Android recortar) e `apple-touch-icon`.
- Pendente, e do dono: conferir `farol.com.br` no registro.br e a marca no INPI.

## Onde as coisas estão

- `app.py` — rotas, modo real vs demonstração, tetos de gasto
- `contas.py` — conta só com nome de usuário e senha (sem e-mail, de propósito)
- `db.py` — `DATABASE_URL` escolhe o banco: sem ela, SQLite local
- `semente.py` + `conteudo/` — roteiros reais, carregados a cada arranque;
  `FOTOS` e `VITRINE` dizem a foto e o trecho de vitrine de cada um
- `templates/inicio.html` — a página que vende; `planejar.html` — o formulário
- `templates/_marca.html` — o farol em SVG, a foto com os dois tamanhos, o sair
- `templates/_cenas.html` — dioramas em SVG, cada cena com as cores dela
- `static/sw.js` — instalação no celular; **nunca** guarda página, só `/static/`

## Publicação

Render, serviço criado à mão: **não lê o `render.yaml`**. Variável nova se põe
no painel do Render. O plano grátis dorme após 15 min sem visita (~50 s para
acordar). Banco permanente: Neon, ainda pendente — até lá, conta criada no site
some a cada publicação.

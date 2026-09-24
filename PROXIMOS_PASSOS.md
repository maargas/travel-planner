# Próximos passos do Farol

A lista viva do que vem depois, em ordem, com o porquê e a balança (o que se
ganha e o que se perde) de cada item. Quem mantém: o Claude, com o agente
`proximos-passos`. Quem decide: o Gabriel — **nada novo começa sem o sim dele.**
A mesma lista fica numa página fixada no claude.ai ("Rumo do Farol").

Os pilares do app (ver `CLAUDE.md`): **roteiro detalhista por interesses**,
**organizador da viagem** (orçamento, quem deve a quem, documentos) e, desde
23/09/2026, uma **pegada de rede social**. Ideia fora deles entra quando faz
sentido — sempre com esboço visual.

Tamanho: **P** = uma sessão curta · **M** = uma sessão · **G** = mais de uma.

## Decidido

- **Estrutura A** (23/09/2026): barra Início · Viagens · Explorar · Conta;
  dentro da viagem, Roteiro · Gastos · Documentos · Pessoas. **Montada e
  publicada.** A página inicial com as fotos abre para todo mundo.

## Decisão em aberto: a logo nova

As cores do farol (vermelho, amarelo, creme) não conversam com o site. Três
caminhos em marinho e limão na página fixada: **farol limpo** (recomendado — o
mesmo farol, mais simples), **o facho** (só a luz) e **o F aceso** (a letra
com facho; depende do nome).

## Ideias das marcas (com esboço na página fixada)

- **A busca sobre a foto** (Airbnb): "Para onde? · Quando? · Quem vai?" em
  vidro na capa, criando a viagem. O caminho mais curto entre ver e usar.
- **"Encontre a sua viagem"** (Shoe Finder da On): perguntas curtas —
  interesses, tempo, como vai se locomover — que sugerem destinos.
- **A história numa frase** (Nike): contar na capa o museu sugerido na semana
  da Fórmula 1, que é por que o Farol existe.

## Ideia em aberto: a pegada de rede social

Ideia dele (23/09/2026): ver quem é seu amigo no app, onde está viajando, qual a
próxima viagem. Esboço e balança na página fixada — decidir onde fica e o que
os amigos podem ver antes de construir.

## Próximos, em ordem (propostas — nada começa sem o sim dele)

1. **Gastos e quem deve a quem (M–G).** Lançar um gasto, dividir entre quem
   participou, ver o saldo de cada um. *Por quê:* pilar 2, e é o que um grupo
   usa todo dia na viagem. *Perde:* exige cuidado com arredondamento e moedas
   diferentes.
2. **Amigos e viajar junto (G).** Aba Amigos, amizade dos dois lados, cada
   viagem dizendo quem vê; e chamar um amigo para dentro de uma viagem.
   *Depende de duas respostas dele:* onde fica (aba própria — a barra fica com
   cinco —, recomendado, ou dentro de Explorar) e o que os amigos veem por padrão (destino e mês,
   recomendado; nada; ou destino e datas). *Perde:* privacidade é o risco —
   quem viaja deixa a casa vazia.
3. **Roteiro dentro da viagem (G).** Pedir o roteiro com os interesses e
   guardá-lo na viagem. *Decisão sua:* pela API custa dinheiro do console
   (cerca de US$ 0,11 por roteiro, nas medições de antes); em conversa comigo
   usa o seu plano, mas não é instantâneo.
4. **Documentos (M–G).** Passagens e reservas. *Decisão sua:* documento é dado
   sensível, com o cuidado das senhas, e o plano grátis do Render não guarda
   arquivos — precisaria de um serviço de arquivos.

## Consertos pequenos (não mudam o rumo)

- **Páginas de erro em português (P).** Hoje, endereço errado mostra página
  crua em inglês, e quem erra a senha vezes demais recebe o aviso dentro da
  tela de planejar viagem.
- **Recusar senhas comuns (P).** Com uma lista guardada no próprio app, sem
  mandar nada para fora.

## Em espera — o Gabriel avisa quando quiser

- Ajustes e detalhes do visual (aprovado; ele volta a isso quando quiser).
- Cor de destaque: limão, como está, ou o amarelo do farol.
- Nome, domínio e marca (INPI) — o nome ainda não é fixo.
- Dioramas em 3D — provavelmente dispensáveis com fotos reais.
- Achados do revisor no caminho pago (só importam se a API voltar).

## Feito

- 24/09/2026 — **A capa troca de foto sozinha**: Banff, Belém, Paris e Foz do
  Iguaçu, cada uma com um trecho de roteiro conferido em fonte oficial. E a
  **opção de carro** no formulário de roteiro.
- 24/09/2026 — Pesquisa de marcas (Apple, On, Nike, Airbnb, Polarsteps) e três
  caminhos para a logo nova, na página fixada.
- 23/09/2026 — Página inicial com as fotos **de volta para quem está logado**,
  e a aba Início na barra (eu tinha escondido; ele mandou corrigir).
- 23/09/2026 — **Estrutura A no ar**: Viagens · Explorar · Conta. Dá para
  criar uma viagem de verdade (destino, datas, quem vai), com as quatro partes
  por dentro; Roteiro, Gastos e Documentos mostram o que vai morar ali. As telas
  de exemplo viraram a "viagem de exemplo" de Lisboa. O "pedir um destino" saiu.
- 22/09/2026 — Fila de pedidos **removida**: não foi pedida e não serve aos
  dois pilares.
- 22/09/2026 — Página "Sua conta" e troca de senha, com testes que falham se
  qualquer senha aparecer em página, banco ou registro do servidor.
- 22/09/2026 — Banco permanente no Neon (Oregon, junto do servidor) e
  `SECRET_KEY` no Render: contas não somem e ninguém é deslogado.
- 22/09/2026 — Visual "Foto e vidro" no celular e "A rota" no computador.

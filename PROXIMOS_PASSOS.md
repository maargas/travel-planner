# Próximos passos do Farol

A lista viva do que vem depois, em ordem, com o porquê e a balança (o que se
ganha e o que se perde) de cada item. Quem mantém: o Claude, com o agente
`proximos-passos`. Quem decide: o Gabriel — **nada novo começa sem o sim dele.**
A mesma lista fica numa página fixada no claude.ai ("Rumo do Farol").

Tudo aqui serve a um dos dois pilares do app (ver `CLAUDE.md`):
**roteiro detalhista por interesses** e **organizador da viagem** (orçamento,
quem deve a quem, documentos), para quem vai sozinho ou em grupo.

Tamanho: **P** = uma sessão curta · **M** = uma sessão · **G** = mais de uma.

## Decisão em aberto: a estrutura do app

Hoje as partes não conversam: "Roteiros" mostra Banff, "Planejar" monta um
roteiro que não fica guardado em lugar nenhum, e seis telas de exemplo
(Painel, Lugares, Orçamento, Documentos, Viajantes, Ajustes) mostram uma
viagem inventada a Lisboa. Falta um centro, e a conta não tem lugar próprio.

Três opções, com esboço, na página fixada:

- **A — Tudo mora dentro de uma viagem (recomendada).** Barra: Viagens ·
  Explorar · Conta. Dentro de cada viagem: Roteiro · Gastos · Documentos ·
  Pessoas. Com uma viagem só, o app abre direto nela.
- **B — Uma aba por ferramenta.** Roteiros · Gastos · Documentos · Conta,
  cada aba misturando todas as viagens.
- **C — Só a viagem da vez.** O app é sempre a viagem atual, com troca no
  topo e a conta num ícone no canto.

## Depois da estrutura (propostas, em ordem)

1. **Montar a estrutura escolhida (M).** Navegação nova, "Conta" como lugar
   próprio (perfil, senha, preferências, sair) e telas vazias que explicam o
   que vai em cada parte. *Por quê:* todo o resto se pendura nela. *Perde:* as
   telas de exemplo com dados inventados saem ou viram o "vazio" explicado.
2. **Criar e guardar uma viagem de verdade (M).** Destino, datas e quem vai
   (pessoas podem ser só nomes, sem conta). *Por quê:* é o centro; hoje toda
   tela de viagem é de mentira.
3. **Gastos e quem deve a quem (M–G).** Lançar um gasto, dividir entre quem
   participou, ver o saldo de cada um. *Por quê:* pilar 2, e é o que um grupo
   usa todo dia na viagem. *Perde:* exige cuidado com arredondamento e moedas
   diferentes.
4. **Roteiro dentro da viagem (G).** Pedir o roteiro com os interesses e
   guardá-lo na viagem. *Balança que é decisão sua:* gerar na hora pela API
   custa dinheiro do console (cerca de US$ 0,11 por roteiro, nas medições de
   antes); montar em conversa comigo usa o seu plano, não o console, mas não é
   instantâneo.
5. **Documentos (M–G).** Guardar passagens e reservas. *Balança:* documento é
   dado sensível (passaporte), com o mesmo cuidado das senhas; e o plano grátis
   do Render não guarda arquivos — precisaria de um serviço de arquivos.
   Decisão sua.
6. **Viajar junto (G).** Convidar amigos para a mesma viagem, cada um com a
   sua conta. *Por quê:* sem isso, os gastos ficam só no celular de quem lançou.

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

- 22/09/2026 — Fila de pedidos **removida**: não foi pedida e não serve aos
  dois pilares.
- 22/09/2026 — Página "Sua conta" e troca de senha, com testes que falham se
  qualquer senha aparecer em página, banco ou registro do servidor.
- 22/09/2026 — Banco permanente no Neon (Oregon, junto do servidor) e
  `SECRET_KEY` no Render: contas não somem e ninguém é deslogado.
- 22/09/2026 — Visual "Foto e vidro" no celular e "A rota" no computador.

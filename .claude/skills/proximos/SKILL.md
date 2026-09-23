---
name: proximos
description: Chama o agente proximos-passos para revisar onde o Farol está, o que fazer depois e por quê, e trazer ideias novas. Atalho do dono — ele digita /proximos.
context: fork
agent: proximos-passos
background: false
disable-model-invocation: true
---

Revise os próximos passos do Farol seguindo as suas instruções: leia
`CLAUDE.md`, `PROXIMOS_PASSOS.md`, o `git log` recente e a memória do projeto,
e entregue no formato combinado — onde estamos, próximos passos (com o porquê e
a balança de cada um), ideias novas se houver, e o que deveria mudar na lista.

Breve e em português simples: o dono lê no celular. Toda ideia nova vem com a
descrição concreta da tela, para ser desenhada.

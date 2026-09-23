# Próximos passos do Farol

A lista viva do que vem depois, em ordem. Cada item diz **por que** está ali e
o que se ganha e se perde. Quem mantém: o Claude, com a ajuda do agente
`proximos-passos`, sempre que uma etapa termina. Quem decide a ordem final: o
Gabriel.

Tamanho: **P** = uma sessão curta · **M** = uma sessão · **G** = mais de uma.

## Agora, em ordem

1. **"Seus pedidos" na conta de cada amigo (M).** O app não pede e-mail, então
   não tem como avisar ninguém. Mostrar o pedido com a situação (na fila,
   pesquisando, pronto) é o único jeito de o amigo saber que o roteiro dele saiu.
   *Ganha:* motivo para ele voltar ao app. *Perde:* você passa a ter de marcar a
   situação de cada pedido.
2. **Pesquisar o próximo roteiro de verdade (M).** O site tem um roteiro só.
   O primeiro pedido de amigo é o candidato natural: resolve a viagem dele e
   vira a segunda prova do produto. *Ganha:* conteúdo, que é o produto.
   *Perde:* tempo de conversa, não dinheiro (é pesquisado à mão).
3. **Páginas de erro em português, no visual novo (P).** Hoje quem erra um
   endereço vê uma página crua, em inglês. Para quem viaja pouco, parece que o
   app quebrou. No mesmo conserto: quem erra a senha vezes demais recebe o
   aviso de "muitos acessos" dentro da tela de planejar viagem, que não tem
   nada a ver (achado do agente `proximos-passos`). *Ganha:* confiança, menos
   confusão. *Perde:* nada.
4. **Recusar senhas comuns na criação e na troca (P).** Com uma lista guardada
   no próprio app — nada é enviado para fora. Se um dia o banco for roubado,
   senha comum é a primeira a ser adivinhada a partir do embaralhado.
   *Ganha:* menos risco. *Perde:* um amigo pode ter de escolher outra senha.

## Quando o modo real (com a API) voltar

Achados do revisor que só importam no caminho pago, hoje desligado:
roteiro que vem pela metade sem aviso; erro na segunda rodada que descarta o
texto; demonstração que corta em 10 dias; carregamento fora da tela no
celular; comentários desatualizados no código.

## Em espera — o Gabriel avisa quando quiser

- Ajustes e detalhes do visual (ele aprovou o resultado e disse que volta a isso).
- Cor de destaque: limão, como está, ou o amarelo do farol.
- Nome, domínio (registro.br) e marca (INPI) — o nome ainda não é fixo.
- Dioramas em 3D — provavelmente dispensáveis agora que há fotos reais.

## Feito

- 22/09/2026 — Fila de pedidos em `/fila`, só para o dono (quem está em
  `FAROL_DONO` no Render): mostra cada pedido e deixa marcar "na fila",
  "pesquisando" ou "pronto". Para qualquer outra pessoa, a página não existe.
- 22/09/2026 — Banco permanente no Neon (Oregon, junto do servidor): contas
  não somem mais a cada publicação. `SECRET_KEY` no Render: ninguém é
  deslogado quando o servidor reinicia.
- 22/09/2026 — Página "Sua conta" e troca de senha, com testes que garantem
  que nenhuma senha aparece em página, banco ou registro do servidor.
- 22/09/2026 — Visual "Foto e vidro" no celular e "A rota" no computador.

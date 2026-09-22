// O que faz o Farol instalar no celular e abrir sem internet.
//
// Regra de privacidade, e ela manda em tudo aqui: SÓ arquivos estáticos entram
// no cache. Nenhuma página é guardada.
//
// A versão anterior guardava toda resposta GET, o que incluía as telas de quem
// estava logado — e-mail, nome, roteiros salvos. Num celular compartilhado,
// isso é a página de uma pessoa reaparecendo para outra, e continua no aparelho
// mesmo depois de sair da conta. Página agora vai sempre à rede; se não houver
// rede, aparece um aviso, e não uma cópia velha de coisa de alguém.

// Trocar este nome apaga tudo que estava guardado. Virou farol-v1 com a troca
// de nome e de ícone, para ninguém ficar com o ícone antigo.
const CACHE = 'farol-v1';
const ESTATICOS = [
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/farol.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ESTATICOS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      // Apaga os caches antigos, inclusive o 'atlas-v1', que guardava páginas.
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const estatico = url.origin === self.location.origin && url.pathname.startsWith('/static/');

  if (estatico) {
    // Ícone e manifesto podem vir do cache: não são de ninguém. Mas o cache
    // não pode ser a palavra final. A versão anterior servia a cópia guardada e
    // nunca mais perguntava ao servidor — um ícone trocado continuaria o antigo
    // para sempre no celular de quem instalou, justamente na troca de logo.
    // Agora entrega o que tem na hora (rápido) e, por trás, busca a versão nova
    // para a próxima vez.
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(req).then((guardado) => {
          const atualizar = fetch(req).then((res) => {
            if (res.ok) cache.put(req, res.clone());
            return res;
          }).catch(() => guardado);
          return guardado || atualizar;
        })
      )
    );
    return;
  }

  // Todo o resto é página, e página nunca é guardada.
  event.respondWith(
    fetch(req).catch(() => new Response(
      `<!doctype html><meta charset="utf-8">
       <meta name="viewport" content="width=device-width,initial-scale=1">
       <title>Sem internet — Farol</title>
       <div style="font-family:system-ui;padding:2.5rem 1.5rem;text-align:center;
                   background:#1a1020;color:#f6edf6;min-height:100vh">
         <h1 style="font-size:1.25rem;margin:0 0 .5rem">Sem internet</h1>
         <p style="opacity:.75;font-size:.9rem;line-height:1.5">
           O Farol precisa de conexão para mostrar seus roteiros.<br>
           Assim que voltar, recarregue a página.
         </p>
       </div>`,
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    ))
  );
});

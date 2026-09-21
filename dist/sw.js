const CACHE = 'romeo-card-af055b602496';
const PRECACHE = ["/", "/app.mjs", "/assets/apple-touch-icon.png", "/assets/favicon-32.png", "/assets/fonts/cormorant-italic.ttf", "/assets/fonts/cormorant-roman.ttf", "/assets/fonts/dm-sans-0.ttf", "/assets/fonts/dm-sans-1.ttf", "/assets/icon-192.png", "/assets/icon-512.png", "/assets/icon-maskable-512.png", "/assets/images/beet-carrot.webp", "/assets/images/ginger-shot.webp", "/assets/images/logo.webp", "/assets/qr-card.png", "/config.mjs", "/no-script.css", "/romeo-health-heaven.vcf", "/sharing.mjs", "/site.webmanifest", "/styles.css", "/assets/qr-card.svg"];
const ALLOWED = new Set(PRECACHE);

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PRECACHE)));
  // Wait for old tabs to close; don't swap a running page's files mid-interaction.
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith('romeo-card-') && key !== CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  const isCard = request.mode === 'navigate' && (url.pathname === '/' || url.pathname === '/index.html');
  const key = isCard ? '/' : url.pathname;
  if (!isCard && !ALLOWED.has(key)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      // Revalidate every file online: a new HTML response must not load old scripts.
      const response = await fetch(request);
      if (response.ok) await cache.put(key,response.clone());
      return response;
    } catch {
      const saved = await cache.match(key);
      return saved || new Response('Please reconnect to open this file.',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}});
    }
  })());
});

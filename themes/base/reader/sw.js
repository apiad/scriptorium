// The HTML book's service worker. One cache per book and per edition: the
// name carries the book's path, so books sharing an origin never touch each
// other's caches, and the version, the hash of every file listed below, so a
// changed book is a changed sw.js and the browser installs it.
const VERSION = '__VERSION__';
const ASSETS = __ASSETS__;
// true when img/ is not precached: an image is cached the first time it is fetched
const LAZY_IMAGES = __LAZY_IMAGES__;
const SCOPE = new URL('./', self.location).pathname;
const PREFIX = 'book:' + SCOPE + ':';
const CACHE = PREFIX + VERSION;

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await c.addAll(ASSETS.map((a) => new Request(a, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith(PREFIX) && k !== CACHE) await caches.delete(k);
    await self.clients.claim();
    for (const c of await self.clients.matchAll({ includeUncontrolled: true })) c.postMessage({ type: 'cached' });
  })());
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || !url.pathname.startsWith(SCOPE)) return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const hit = await c.match(e.request.mode === 'navigate' ? './' : e.request, { ignoreSearch: true });
    if (hit) return hit;
    const res = await fetch(e.request);
    if (LAZY_IMAGES && res.ok && url.pathname.startsWith(SCOPE + 'img/')) await c.put(e.request, res.clone());
    return res;
  })());
});

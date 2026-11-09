// Service worker: hace instalable la app (PWA), la deja abrir sin conexión y recibe los push.
const CACHE = 'vecino-sf-v1';

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(['/', '/manifest.webmanifest', '/icono.svg'])));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

// Red primero; si no hay conexión, lo último guardado. La API nunca se cachea: los datos
// (saldos, estados) tienen que ser los actuales o ninguno.
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/') || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        const copia = r.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
        return r;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('/'))),
  );
});

self.addEventListener('push', (e) => {
  const d = e.data ? e.data.json() : { titulo: 'Vecino SF', cuerpo: '' };
  e.waitUntil(
    self.registration.showNotification(d.titulo, {
      body: d.cuerpo,
      icon: '/icono-192.png',
      badge: '/icono-192.png',
      tag: `aviso-${d.id || Date.now()}`,
      data: { enlace: d.enlace || '/' },
    }),
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(self.clients.openWindow(e.notification.data.enlace));
});

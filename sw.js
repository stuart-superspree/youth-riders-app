// Youth Riders Service Worker
// Caches the app shell for offline use
// Updates automatically when files change

const CACHE_NAME = 'youth-riders-v1';

// Files to cache on install — the app shell
const SHELL_FILES = [
  './',
  './index.html',
  './data.json',
  './icon-192.png',
  './icon-512.png'
];

// ── INSTALL: cache the app shell ──────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[SW] Caching app shell');
      // Use individual adds so one failure doesn't break the whole install
      return Promise.allSettled(
        SHELL_FILES.map(url => cache.add(url).catch(e => console.warn('[SW] Could not cache:', url, e)))
      );
    }).then(() => self.skipWaiting())
  );
});

// ── ACTIVATE: remove old caches ───────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          })
      )
    ).then(() => self.clients.claim())
  );
});

// ── FETCH: network-first for data.json, cache-first for shell ──
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // data.json: always try network first so content stays fresh
  // Fall back to cache if offline
  if (url.pathname.endsWith('data.json')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Update cache with fresh data
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Google Fonts and external resources: network only
  if (!url.origin.includes(self.location.origin)) {
    event.respondWith(fetch(event.request).catch(() => new Response('')));
    return;
  }

  // Everything else: cache-first, fall back to network
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        return response;
      });
    })
  );
});

// The service worker: makes boredroom installable and quick to open. Pages come from the
// network when it's there and from the last copy when it isn't; built assets have hashed
// names, so a cached one never goes stale. The API is never cached: scores are live.
// Google Fonts are kept too, so text doesn't swap fonts or shift on a slow or offline open.
const CACHE = 'boredroom-v2'
const FONTS = ['https://fonts.googleapis.com', 'https://fonts.gstatic.com']

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.add('/')).then(() => self.skipWaiting()))
})

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()))
})

self.addEventListener('fetch', e => {
  const req = e.request
  const url = new URL(req.url)
  if (req.method !== 'GET') return
  if (FONTS.includes(url.origin)) {
    // the font files never change; the stylesheet is refreshed behind the cached copy
    e.respondWith(caches.open(CACHE).then(c => c.match(req).then(hit => {
      if (hit && url.origin === FONTS[1]) return hit
      const net = fetch(req).then(res => { if (res.ok || res.type === 'opaque') c.put(req, res.clone()); return res })
      return hit ? (net.catch(() => hit), hit) : net
    })))
    return
  }
  if (url.origin !== location.origin) return
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/og/')) return

  if (req.mode === 'navigate') {
    // the app routes itself, so any page can fall back to the shell
    e.respondWith(fetch(req).then(res => {
      if (res.ok && url.pathname === '/') { const copy = res.clone(); caches.open(CACHE).then(c => c.put('/', copy)) }
      return res
    }).catch(() => caches.match('/')))
    return
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)) }
      return res
    })))
  }
})

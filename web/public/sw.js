// The service worker: makes boredroom installable and quick to open. Pages come from the
// network when it's there and from the last copy when it isn't (or the server isn't answering); built assets have hashed
// names, so a cached one never goes stale. The API is never cached: scores are live.
// Google Fonts are kept too, so text doesn't swap fonts or shift on a slow or offline open.
// It also shows reminders: every push becomes a notification (iPhones revoke silent ones).
const CACHE = 'boredroom-v3'
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
    // and so can a server that isn't answering: the tunnel's error page (502…) never replaces the app
    e.respondWith(fetch(req).then(res => {
      // every page is the same shell, so any of them keeps the copy current (not only '/')
      if (res.ok && (res.headers.get('content-type') ?? '').includes('text/html')) { const copy = res.clone(); caches.open(CACHE).then(c => c.put('/', copy)) }
      if (res.status >= 500) return caches.match('/').then(hit => hit || res)
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

self.addEventListener('push', e => {
  let p = {}
  try { p = e.data ? e.data.json() : {} } catch { p = { body: e.data && e.data.text() } }
  e.waitUntil(self.registration.showNotification(p.title || 'boredroom', {
    body: p.body || '', tag: p.tag || 'boredroom', data: { url: p.url || '/' },
    icon: '/icons/icon-192.png', badge: '/icons/badge-96.png',
  }))
})

// a tap opens the board: the app's window if it's open, else a new one
self.addEventListener('notificationclick', e => {
  e.notification.close()
  const url = new URL(e.notification.data?.url || '/', location.origin).href
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(ws => {
    const w = ws.find(w => new URL(w.url).origin === location.origin)
    return w ? w.focus().then(w => w.navigate(url)) : self.clients.openWindow(url)
  }))
})

// the browser replaced the subscription: hand the new one to the server, same seat
self.addEventListener('pushsubscriptionchange', e => {
  const opts = e.oldSubscription && e.oldSubscription.options
  if (!opts) return
  e.waitUntil(self.registration.pushManager.subscribe(opts).then(sub =>
    fetch('/api/v1/me/push/renew', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old: e.oldSubscription.endpoint, sub: sub.toJSON() }) })))
})

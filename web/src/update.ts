import { net, set } from './net'

// A new version: the server says which web build it serves (its main script's hashed
// name, in /config); this copy knows its own. When they differ, the top bar offers a
// reload. It checks when the app comes back to the screen, every half hour while it's
// open, and when the server answers again after a restart. Nothing reloads by itself.

const own = (() => { try { return new URL(import.meta.url).pathname } catch { return '' } })()
let first: string | null = null  // the newest release when this copy first asked
let dismissed: string | null = null  // "later": not this build again this visit
const EVERY = 30 * 60 * 1000

export async function check() {
  if (!own.startsWith('/assets/')) return  // a dev server: nothing to compare
  try {
    const r = await fetch('/api/v1/config', { cache: 'no-store' })
    if (!r.ok) return
    const c: { web_build: string | null; release?: { id: string; title: string } } = await r.json()
    if (c.release && first === null) first = c.release.id
    if (!c.web_build || c.web_build === own || c.web_build === dismissed) return
    const title = c.release && c.release.id !== first ? c.release.title : null
    if (net().update?.build !== c.web_build) set({ update: { build: c.web_build, title } })
  } catch { /* offline: the net bar says so */ }
}

export const later = () => { dismissed = net().update?.build ?? null; set({ update: null }) }
export const reload = () => location.reload()

if (typeof window !== 'undefined') {
  check()
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') check() })
  window.addEventListener('boredroom:back', () => { check() })
  window.setInterval(() => { if (document.visibilityState === 'visible') check() }, EVERY)
}

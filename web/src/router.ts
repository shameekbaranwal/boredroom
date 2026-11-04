// A tiny history router: the app has a handful of paths, so no library.
import { useEffect, useState } from 'react'

// Going back puts you where you were. The browser's own restoring can't: the page comes
// back empty and fills in a moment later, so it lands at the top. Each page keeps how far
// down it was when you left, and back scrolls there once the page is tall enough again.
const SPOTS = 'boredroom.spots'
const here = () => location.pathname + location.search
const spots: Record<string, number> = (() => { try { return JSON.parse(sessionStorage.getItem(SPOTS) ?? '{}') } catch { return {} } })()
const keep = (path: string) => {
  spots[path] = Math.round(window.scrollY)
  try { sessionStorage.setItem(SPOTS, JSON.stringify(spots)) } catch { /* private window: this visit only */ }
}
let shown = here()
let ours = false  // go()'s own popstate: a new page, which starts at the top
let stop: (() => void) | null = null

/** Holds the page at y while it fills in: done once it has stayed there a moment, after a
 *  few seconds, or as soon as you scroll yourself. */
function restore(y: number) {
  stop?.()
  if (y <= 0) return
  const until = Date.now() + 4000
  let frame = 0, held = 0
  const mine = ['wheel', 'touchstart', 'keydown', 'mousedown'] as const
  const quit = () => { cancelAnimationFrame(frame); mine.forEach(e => removeEventListener(e, quit)); stop = null }
  const step = () => {
    window.scrollTo(0, y)
    held = Math.abs(window.scrollY - y) < 2 ? held + 1 : 0
    if (held > 15 || Date.now() > until) return quit()
    frame = requestAnimationFrame(step)
  }
  mine.forEach(e => addEventListener(e, quit, { passive: true }))
  stop = quit
  frame = requestAnimationFrame(step)
}

if (typeof window !== 'undefined') {
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual'
  window.addEventListener('popstate', () => {
    if (ours) return
    const was = shown
    shown = here()
    if (shown === was) return  // an overlay closing: the page under it never moved
    keep(was)
    restore(spots[shown] ?? 0)
  })
  window.addEventListener('pagehide', () => keep(here()))
  // a reload comes back to the same spot; opening the app afresh starts at the top
  const nav = performance.getEntriesByType?.('navigation')[0] as PerformanceNavigationTiming | undefined
  if (nav?.type === 'reload') restore(spots[shown] ?? 0)
}

export function go(path: string, replace = false) {
  keep(here())
  stop?.()
  // an open overlay holds a history entry of its own (so back closes it); leaving from
  // one takes that entry's place rather than stacking on it
  if (replace || history.state?.overlay) history.replaceState(null, '', path)
  else history.pushState({ from: location.pathname + location.search }, '', path)
  shown = here()
  ours = true
  try { window.dispatchEvent(new PopStateEvent('popstate')) } finally { ours = false }
  window.scrollTo(0, 0)
}

export function usePath(): string {
  const [path, setPath] = useState(location.pathname + location.search)
  useEffect(() => {
    const on = () => setPath(location.pathname + location.search)
    window.addEventListener('popstate', on)
    return () => window.removeEventListener('popstate', on)
  }, [])
  return path
}

/** Matches "/b/:slug/m/:game" style patterns; returns the params or null. */
export function match(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split('/'), a = path.split('?')[0].split('/')
  if (p.length !== a.length) return null
  const out: Record<string, string> = {}
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(':')) out[p[i].slice(1)] = decodeURIComponent(a[i])
    else if (p[i] !== a[i]) return null
  }
  return out
}

export function query(path: string): URLSearchParams {
  return new URLSearchParams(path.split('?')[1] ?? '')
}

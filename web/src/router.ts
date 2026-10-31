// A tiny history router: the app has a handful of paths, so no library.
import { useEffect, useState } from 'react'

export function go(path: string, replace = false) {
  // an open overlay holds a history entry of its own (so back closes it); leaving from
  // one takes that entry's place rather than stacking on it
  if (replace || history.state?.overlay) history.replaceState(null, '', path)
  else history.pushState({ from: location.pathname + location.search }, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
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

// Light, dark, or follow the device. The choice lives in localStorage (a per-device
// convenience) and is applied as data-theme on <html>; index.html applies it before paint.
import { useEffect, useState } from 'react'

export type Pref = 'system' | 'light' | 'dark'
const KEY = 'boredroom.theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

export function pref(): Pref {
  try { const t = localStorage.getItem(KEY); return t === 'light' || t === 'dark' ? t : 'system' } catch { return 'system' }
}

export function resolved(p: Pref = pref()): 'light' | 'dark' {
  return p === 'system' ? (media().matches ? 'dark' : 'light') : p
}

function apply(p: Pref) {
  const root = document.documentElement
  if (p === 'system') delete root.dataset.theme
  else root.dataset.theme = p
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolved(p) === 'dark' ? '#182033' : '#217346')
  window.dispatchEvent(new Event('boredroom:theme'))
}

type VT = { ready: Promise<void> }
type DocVT = Document & { startViewTransition?: (cb: () => void) => VT }

/** Saves and applies the preference. Given where the tap was, the new theme spreads out
 *  from there in a circle (view transitions); otherwise, or with reduced motion, it just switches. */
export function setPref(p: Pref, from?: { x: number; y: number }) {
  try { if (p === 'system') localStorage.removeItem(KEY); else localStorage.setItem(KEY, p) } catch { /* private mode */ }
  const doc = document as DocVT
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (!doc.startViewTransition || calm) { apply(p); return }
  const x = from?.x ?? innerWidth / 2, y = from?.y ?? 0
  const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
  doc.startViewTransition(() => apply(p)).ready.then(() => {
    document.documentElement.animate(
      { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
      { duration: 520, easing: 'cubic-bezier(.4,0,.2,1)', pseudoElement: '::view-transition-new(root)' },
    )
  }).catch(() => {})
}

/** [the preference, what's showing]; re-renders on change and when the device flips. */
export function useTheme(): [Pref, 'light' | 'dark'] {
  const [, bump] = useState(0)
  useEffect(() => {
    const on = () => bump(n => n + 1)
    const m = media()
    window.addEventListener('boredroom:theme', on)
    m.addEventListener('change', on)
    apply(pref())
    return () => { window.removeEventListener('boredroom:theme', on); m.removeEventListener('change', on) }
  }, [])
  const p = pref()
  return [p, resolved(p)]
}

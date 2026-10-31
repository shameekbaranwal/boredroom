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

/** Saves and applies the preference. Colours fade across over a third of a second on the
 *  live page (not a view transition: its snapshots dropped sticky headers when scrolled);
 *  with reduced motion it just switches. */
export function setPref(p: Pref) {
  try { if (p === 'system') localStorage.removeItem(KEY); else localStorage.setItem(KEY, p) } catch { /* private mode */ }
  const root = document.documentElement
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    root.classList.add('theming')
    clearTimeout(fading)
    fading = setTimeout(() => root.classList.remove('theming'), 400)
  }
  apply(p)
}
let fading: ReturnType<typeof setTimeout> | undefined

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

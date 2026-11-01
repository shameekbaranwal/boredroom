export const standalone = () =>
  matchMedia('(display-mode: standalone)').matches || (navigator as { standalone?: boolean }).standalone === true
export const ios = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
const android = () => /android/i.test(navigator.userAgent)

// Where a game's play link opens from the installed app on a phone: inside the app (the
// default), or handed to the phone's browser, where you may already be signed in to the game.
export type Opens = 'app' | 'browser'
const OPENS = 'boredroom.games.open'
/** The choice only exists on an installed phone app; elsewhere links open the usual way. */
export const canChooseOpens = () => standalone() && (ios() || android())
export const opensIn = (): Opens => { try { return localStorage.getItem(OPENS) === 'browser' ? 'browser' : 'app' } catch { return 'app' } }
export const setOpensIn = (o: Opens) => { try { localStorage.setItem(OPENS, o) } catch { /* private window */ } }
/** The link to put on a play button, and whether it opens a new tab. */
export function playLink(url: string): { href: string; newTab: boolean } {
  if (!canChooseOpens() || opensIn() === 'app') return { href: url, newTab: true }
  if (ios()) return { href: `x-safari-${url}`, newTab: false }  // safari, from ios 17
  const u = new URL(url)
  return { href: `intent://${u.host}${u.pathname}${u.search}#Intent;scheme=https;S.browser_fallback_url=${encodeURIComponent(url)};end`, newTab: false }
}

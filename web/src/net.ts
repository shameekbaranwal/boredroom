import { useSyncExternalStore } from 'react'

// How the line to the server is doing, for the strip at the top of every screen. A call
// that can't get through (offline, or the server restarting for a deploy) says so here;
// a watcher then knocks on /health until it answers, and "boredroom:back" tells every
// screen to load again. What a screen last loaded is kept on this device (see api.ts),
// so it shows that copy, marked with its time, instead of nothing.

export type Away = 'offline' | 'down'
export type NetState = {
  away: Away | null
  stale: number | null    // a screen is showing a copy from this time
  waiting: number         // results held on this device until the server's back
  update: { build: string; title: string | null } | null  // a newer version is out (update.ts)
}

let state: NetState = { away: null, stale: null, waiting: 0, update: null }
const subs = new Set<() => void>()
export const set = (p: Partial<NetState>) => { state = { ...state, ...p }; subs.forEach(f => f()) }
export const net = () => state

export function useNet(): NetState {
  return useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, () => state)
}

/** The server answered: if it was away, every screen loads again. */
export function reached() {
  const was = state.away
  if (was || state.stale) set({ away: null, stale: null })
  if (was) window.dispatchEvent(new Event('boredroom:back'))
}

let timer: number | null = null, checking = false, wait = 3000
async function check() {
  timer = null
  if (checking) return
  checking = true
  try {
    if ((await fetch('/health', { cache: 'no-store' })).ok) { wait = 3000; reached(); return }
  } catch { /* still away */ } finally { checking = false }
  wait = Math.min(wait * 1.5, 30000)
  timer = window.setTimeout(check, wait)
}

/** A call didn't get through. Knock until the server answers: every 3s, then slower. */
export function lost(why: Away) {
  if (state.away !== why) set({ away: why })
  if (timer === null && !checking) timer = window.setTimeout(check, wait)
}

/** Knock now: a retry button, or the phone coming back online or to the front. */
export function knock() {
  if (!state.away) return
  if (timer !== null) window.clearTimeout(timer)
  check()
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', knock)
  window.addEventListener('offline', () => { if (state.away) set({ away: 'offline' }) })
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') knock() })
}

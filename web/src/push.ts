import { useSyncExternalStore } from 'react'
import { api } from './api'
import { ios, standalone } from './opens'
import { useApp } from './ui'

// Reminders on this device: a web push subscription, kept on the server under your seat.
// iPhones only take pushes in the installed app; Android and desktop browsers take them in
// a tab too. The browser asks for permission only from a tap ("yes, nudge me", a switch, a
// bell), never on its own.

export type Support = 'ok' | 'install' | 'none'
export type PushState = {
  ready: boolean        // the first look is done
  support: Support
  server: boolean       // this server sends pushes (it has a key)
  perm: NotificationPermission
  on: boolean           // this device is subscribed
  busy: boolean
}

let key: string | null = null
let state: PushState = { ready: false, support: 'none', server: false, perm: 'default', on: false, busy: false }
const subs = new Set<() => void>()
const set = (p: Partial<PushState>) => { state = { ...state, ...p }; subs.forEach(f => f()) }

const support = (): Support => {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator) || !('Notification' in window)) return ios() ? 'install' : 'none'
  if (ios() && !standalone()) return 'install'
  return 'PushManager' in window ? 'ok' : 'none'
}

const bytes = (b64: string) => {
  const s = atob((b64 + '='.repeat((4 - b64.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(s, c => c.charCodeAt(0))
}
const same = (a: ArrayBuffer | null | undefined, b: Uint8Array) => !!a && a.byteLength === b.length && new Uint8Array(a).every((x, i) => x === b[i])
const sub = async () => (await navigator.serviceWorker.getRegistration())?.pushManager.getSubscription() ?? null

/** Looks at this device once a visit: is it subscribed, and with this server's key? A key
 *  that changed (a server's keys were replaced) means quietly subscribing again. */
export async function look() {
  const sp = support()
  set({ support: sp, perm: 'Notification' in window ? Notification.permission : 'default' })
  try { key = (await api.config()).vapid_public_key } catch { key = null }
  set({ server: !!key })
  if (sp !== 'ok' || !key) { set({ ready: true }); return }
  try {
    let s = await sub()
    if (s && !same(s.options.applicationServerKey, bytes(key))) {
      await s.unsubscribe()
      s = Notification.permission === 'granted' ? await subscribeHere() : null
    }
    if (s) await api.subscribe(s.toJSON())  // the server has it, under whoever is signed in now
    set({ on: !!s, ready: true })
  } catch { set({ ready: true }) }
}

async function subscribeHere() {
  const reg = await navigator.serviceWorker.ready
  return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes(key!) })
}

/** Turns reminders on for this device. Call it from a tap. Returns whether it worked. */
export async function enable(): Promise<boolean> {
  if (state.support !== 'ok' || !key) return false
  set({ busy: true })
  try {
    const perm = await Notification.requestPermission()
    set({ perm })
    if (perm !== 'granted') return false
    const s = (await sub()) ?? await subscribeHere()
    await api.subscribe(s.toJSON())
    set({ on: true })
    return true
  } catch { return false } finally { set({ busy: false }) }
}

export async function disable() {
  set({ busy: true })
  try {
    const s = await sub()
    if (s) {
      const mine = (await api.devices()).devices.find(d => d.endpoint === s.endpoint)
      if (mine) await api.unsubscribe(mine.id)
      await s.unsubscribe()
    }
    set({ on: false })
  } finally { set({ busy: false }) }
}

export function usePush(): PushState {
  return useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, () => state)
}

// the ask: a memo on the agenda on your 2nd to 4th day of opening boredroom, never the first
const VISITS = 'boredroom.visits', LATER = 'boredroom.ask.later'
const today = () => new Date().toLocaleDateString('en-CA')
function visits(): string[] {
  try {
    const v: string[] = JSON.parse(localStorage.getItem(VISITS) ?? '[]')
    if (!v.includes(today())) { v.push(today()); localStorage.setItem(VISITS, JSON.stringify(v.slice(-5))) }
    return v
  } catch { return [today()] }
}
export const shouldAsk = (p: PushState) => {
  if (!p.ready || p.support !== 'ok' || !p.server || p.on || p.perm !== 'default') return false
  const n = visits().length
  try { if (localStorage.getItem(LATER) === today()) return false } catch { /* fine */ }
  return n >= 2 && n <= 4
}
export const askLater = () => { try { localStorage.setItem(LATER, today()) } catch { /* fine */ } }

if (typeof window !== 'undefined') visits()

export const why = (p: PushState) => p.perm === 'denied' ? "notifications are blocked for boredroom in your browser's settings."
  : "this device didn't take reminders. try again in a moment."

/** Turns this device on if it isn't, from the tap that asked. Says why when it can't. */
export function useDevice() {
  const p = usePush()
  const { toast } = useApp()
  const ensure = async () => {
    if (p.on) return true
    const ok = await enable()
    if (!ok) toast(why({ ...p, perm: 'Notification' in window ? Notification.permission : p.perm }))
    return ok
  }
  return { p, ensure, usable: p.ready && p.support === 'ok' && p.server && p.perm !== 'denied' }
}

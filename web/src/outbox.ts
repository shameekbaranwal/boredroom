import { api, ApiError, token, type Event as FilingEvent } from './api'
import { set } from './net'

// Results pasted while the server can't be reached: held on this device, and filed by
// themselves once it answers again, stamped with when they were pasted (the server takes
// that up to a day back), so a result held across a reset isn't filed late.

export type Held = { id: string; text: string; source: 'paste' | 'share'; at: string; seat: string }
const OUT = 'boredroom.outbox'

function read(): Held[] {
  try { return JSON.parse(localStorage.getItem(OUT) ?? '[]') } catch { return [] }
}
function write(xs: Held[]) {
  try { if (xs.length) localStorage.setItem(OUT, JSON.stringify(xs)); else localStorage.removeItem(OUT) } catch { /* private window: held for this visit only */ }
  set({ waiting: mine(xs).length })
}
// only the seat that pasted them sends them
const mine = (xs: Held[]) => { const t = token(); return xs.filter(x => x.seat === t?.slice(0, 12)) }

export function hold(text: string, source: 'paste' | 'share'): Held {
  const h = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, text, source, at: new Date().toISOString(), seat: token()?.slice(0, 12) ?? '' }
  write([...read(), h])
  return h
}
export function unhold(id: string) { write(read().filter(x => x.id !== id)) }
/** What this seat has waiting, oldest first. */
export const held = () => mine(read())
/** A held result, corrected before it goes; emptied, it's dropped. */
export function edit(id: string, text: string) {
  write(text.trim() ? read().map(x => x.id === id ? { ...x, text } : x) : read().filter(x => x.id !== id))
}

/** What sending found: results filed, and any that need a word from you. */
export type Sent = { filed: number; conflicts: (FilingEvent & { paste_id: number })[]; failed: string[] }

let sending = false
/** Sends what's held, oldest first, stopping at the first that can't get through. */
export async function send(): Promise<void> {
  if (sending) return
  const xs = mine(read())
  if (!xs.length) { set({ waiting: 0 }); return }
  sending = true
  const out: Sent = { filed: 0, conflicts: [], failed: [] }
  try {
    for (const x of xs) {
      try {
        const f = await api.paste(x.text, x.source, x.at)
        out.filed += f.events.filter(e => e.kind === 'filed' || e.kind === 'merged').length
        out.conflicts.push(...f.events.filter(e => e.kind === 'conflict').map(e => ({ ...e, paste_id: f.paste_id })))
      } catch (e) {
        if (e instanceof ApiError && e.away) break  // still away: try again when it's back
        out.failed.push((e as Error).message)  // the server said no: holding it won't change that
      }
      unhold(x.id)
    }
  } finally { sending = false }
  if (out.filed || out.conflicts.length || out.failed.length) window.dispatchEvent(new CustomEvent<Sent>('boredroom:sent', { detail: out }))
}

if (typeof window !== 'undefined') {
  window.addEventListener('boredroom:back', () => { send() })
  window.addEventListener('online', () => { send() })
  set({ waiting: mine(read()).length })
}

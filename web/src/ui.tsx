import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Game, Me } from './api'
import { hue } from './format'
import { go } from './router'

export type Ctx = {
  me: Me
  games: Record<string, Game>
  refreshMe: () => Promise<void>
  toast: (msg: string, action?: { label: string; run: () => void }) => void
  signOut: () => void
}
export const AppCtx = createContext<Ctx>(null as unknown as Ctx)
export const useApp = () => useContext(AppCtx)

export function Header({ title, meta, onTitle, back }: { title: string; meta?: string; onTitle?: () => void; back?: string }) {
  return (
    <div className="hd">
      {back && <button className="back" onClick={() => go(back)} aria-label="back">‹</button>}
      <span className="t">
        {onTitle ? <button className="ttl" onClick={onTitle} aria-label="switch board">{title}<span className="car">▾</span></button> : title}
      </span>
      {meta && <span className="m">{meta}</span>}
    </div>
  )
}

/** The formula bar: the screen's query, written out. Read-only for now. */
export function Fx({ fn, args }: { fn: string; args: [string, string][] }) {
  return (
    <div className="fx keep">
      <i>fx</i>={fn}(
      {args.map(([k, v], i) => <span key={k}>{k}:<b>"{v.toLowerCase()}"</b>{i < args.length - 1 ? ',' : ''}</span>)}
      )
    </div>
  )
}

export function Nav({ slug, on, temp }: { slug: string; on: 'agenda' | 'review' | 'you' | null; temp?: string }) {
  return (
    <nav className="nav">
      <button className={on === 'agenda' && !temp ? 'on' : ''} onClick={() => go(`/b/${slug}`)}>agenda</button>
      <button disabled title="coming in the next milestone">review</button>
      <button className={on === 'you' && !temp ? 'on' : ''} onClick={() => go(`/b/${slug}/you`)}>you</button>
      {temp && <span className="on tmp" style={{ padding: '12px 14px' }}>{temp}</span>}
    </nav>
  )
}

export function Av({ name }: { name: string }) {
  return <span className="av" style={{ ['--h' as string]: hue(name) }}>{name.slice(0, 1)}</span>
}

export function Tile({ game, name }: { game: string; name: string }) {
  return <span className="ic" style={{ ['--h' as string]: hue(game) }}>{name.slice(0, 1)}</span>
}

export function Clip() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect x="3.5" y="2.75" width="9" height="11.5" rx="1.5" /><path d="M6 2.75h4v1.5H6z" />
    </svg>
  )
}

/** Re-renders every 30 s, for the reset clocks. */
export function useNow(): number {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t) }, [])
  return now
}

export function Loading({ what = 'the minutes' }: { what?: string }) {
  return <div className="center muted">fetching {what}…</div>
}

export function Toast({ msg, action, onDone }: { msg: string; action?: { label: string; run: () => void }; onDone: () => void }) {
  const done = useRef(onDone)
  done.current = onDone
  useEffect(() => { const t = setTimeout(() => done.current(), 6000); return () => clearTimeout(t) }, [msg])
  return (
    <div className="toast" role="status">
      <span>{msg}</span>
      {action && <button onClick={() => { action.run(); onDone() }}>{action.label}</button>}
    </div>
  )
}

export function Overlay({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="ovl" role="dialog" aria-label={title}>
      <div className="panel"><div className="ph-h">{title}</div>{children}</div>
      <button className="close" onClick={onClose} aria-label="close" />
    </div>
  )
}

/** Hand a text to WhatsApp (or anything else) via the share sheet, else the clipboard. */
export async function sendOn(text: string, toast: Ctx['toast']) {
  if (navigator.share) {
    try { await navigator.share({ text }); return } catch (e) { if ((e as Error).name === 'AbortError') return }
  }
  try { await navigator.clipboard.writeText(text); toast('copied. paste it in the group.') }
  catch { toast("couldn't copy that") }
}

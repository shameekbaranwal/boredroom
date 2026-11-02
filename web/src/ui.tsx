import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Game, Me } from './api'
import { hue } from './format'
import { go } from './router'
import { knock, useNet } from './net'
import { TableMark, ThemeToggle, Wordmark } from './brand'

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
      {back && <button className="back" onClick={() => goBack(back)} aria-label="back">‹</button>}
      <span className="t">
        {onTitle ? <button className="ttl" onClick={onTitle} aria-label="switch board">{title}<span className="car">▾</span></button> : title}
      </span>
      {meta && <span className="m">{meta}</span>}
    </div>
  )
}

/** Back to `to`: the browser's back when that's where we came from (so Android back and
 *  this arrow agree), else straight there. */
export function goBack(to: string) {
  const from = (history.state?.from ?? '').split(/[?#]/)[0]
  if (from === to.split(/[?#]/)[0]) history.back()
  else go(to, true)
}

/** Loads again when you come back to the app (after playing the puzzle, say) or back online. */
export function useFresh(load: () => void) {
  const f = useRef(load)
  f.current = load
  useEffect(() => {
    const on = () => { if (document.visibilityState === 'visible') f.current() }
    const back = () => f.current()
    document.addEventListener('visibilitychange', on)
    window.addEventListener('online', on)
    window.addEventListener('boredroom:back', back)  // the server answers again (net.ts)
    return () => {
      document.removeEventListener('visibilitychange', on); window.removeEventListener('online', on)
      window.removeEventListener('boredroom:back', back)
    }
  }, [])
}

/** A cell edited in place, the way a spreadsheet does it: in the formula bar.
 *  Enter or ✓ saves, Esc or ✕ puts it back. `note` speaks under the bar (a username check). */
export function FxEdit({ fn, field, value, onChange, onSave, onCancel, ok = true, busy = false, note, max = 40 }: {
  fn: string; field: string; value: string; onChange: (v: string) => void; onSave: () => void; onCancel: () => void
  ok?: boolean; busy?: boolean; note?: { text: string; tone: string }; max?: number
}) {
  const el = useRef<HTMLInputElement>(null)
  useEffect(() => { el.current?.focus(); el.current?.select() }, [])
  return <>
    <div className="fx fxe keep">
      <i>fx</i><span>={fn}({field}:"</span>
      <input ref={el} className="fxe-in" value={value} maxLength={max} aria-label={field} autoCapitalize="none" autoComplete="off" spellCheck={false}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && ok && !busy) onSave(); if (e.key === 'Escape') onCancel() }} />
      <span>")</span>
      <button className="fxe-b ok" onClick={onSave} disabled={!ok || busy} aria-label="save">✓</button>
      <button className="fxe-b" onClick={onCancel} aria-label="cancel">✕</button>
    </div>
    {note && <div className={`fx-note ${note.tone}`} aria-live="polite">{note.text}</div>}
  </>
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

/** One argument of an editable formula bar: tap it for its options (typing narrows them). */
export type Token = { key: string; value: string; options: [string, string][]; onPick: (v: string) => void }

/** The formula bar as the screen's controls (UX-NOTES §2): =fn(key:"value", …), each value
 *  a picker. Changing the screen rewrites the bar; picking in the bar changes the screen. */
export function FxQuery({ fn, tokens }: { fn: string; tokens: Token[] }) {
  return (
    <div className="fx fxq keep" role="group" aria-label="query">
      <i>fx</i><span>={fn}(</span>
      {tokens.map((t, i) => (
        <label key={t.key} className="tok">
          <span>{t.key}:</span>
          <span className="tv">
            <span aria-hidden="true">"{t.options.find(([v]) => v === t.value)?.[1] ?? t.value}"</span>
            <select value={t.value} aria-label={t.key} onChange={e => t.onPick(e.target.value)}>
              {t.options.map(([v, l]) => <option key={v} value={v}>"{l}"</option>)}
            </select>
          </span>{i < tokens.length - 1 ? ',' : ''}
        </label>
      ))}
      <span>)</span>
    </div>
  )
}

export function Nav({ slug, on, temp }: { slug?: string; on: 'agenda' | 'meeting' | 'review' | 'you' | null; temp?: string }) {
  const { me } = useApp()
  return (
    <nav className="nav">
      <div className="nav-brand wide-only">
        <TableMark size={30} tile />
        <Wordmark size={22} />
      </div>
      <button className={on === 'agenda' && !temp ? 'on' : ''} onClick={() => go(slug ? `/b/${slug}` : '/desk')}>agenda</button>
      <button className={on === 'meeting' && !temp ? 'on' : ''} onClick={() => go(slug ? `/b/${slug}/meeting` : '/meeting')}>memos</button>
      <button className={on === 'review' && !temp ? 'on' : ''} onClick={() => go(slug ? `/b/${slug}/review` : '/review')}>review</button>
      <button className={on === 'you' && !temp ? 'on' : ''} onClick={() => go(slug ? `/b/${slug}/you` : '/me')}>you</button>
      {temp && <span className="on tmp">{temp}</span>}
      <div className="nav-boards wide-only">
        <span className="nav-sec">your boards</span>
        {me.boards.map(b => (
          <button key={b.slug} className={b.slug === slug ? 'cur' : ''} onClick={() => go(`/b/${b.slug}`)}>{b.name}<small>{b.nickname}</small></button>
        ))}
        <button className="nav-new" onClick={() => go('/new')}>+ start a board</button>
        <button className="nav-new" onClick={() => go('/desk#join')}>+ join with an invite</button>
      </div>
      <div className="nav-foot wide-only"><ThemeToggle /><span>{me.username}</span></div>
    </nav>
  )
}

export function Av({ name }: { name: string }) {
  return <span className="av" style={{ ['--h' as string]: hue(name) }}>{name.slice(0, 1)}</span>
}

export function Tile({ game, name }: { game: string; name: string }) {
  return <span className="ic" style={{ ['--h' as string]: hue(game) }}>{name.slice(0, 1)}</span>
}

/** The library's one mark for a weekly game: a new puzzle a week, not a day. */
export function Weekly({ game }: { game: string }) {
  const { games } = useApp()
  return games[game]?.weekly ? <span className="wk" title="a new puzzle every week">weekly</span> : null
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

/** Rows that hold the sheet's shape while it loads, so nothing around them jumps. */
export function Ghost({ what, rows = 5 }: { what: string; rows?: number }) {
  return (
    <div className="bd" aria-busy="true" aria-label={`fetching ${what}`}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="it ghost-row" aria-hidden="true"><span className="gh-ic" /><span className="g"><i style={{ width: `${70 - i * 9}%` }} /><i /></span></div>
      ))}
    </div>
  )
}

/** The strip at the top while the server can't be reached, or results wait to be sent.
 *  A tap knocks again. */
export function NetBar() {
  const n = useNet()
  if (!n.away && !n.waiting) return null
  const at = n.stale && new Date(n.stale).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  const parts = [
    n.away === 'offline' ? 'offline' : n.away ? "can't reach boredroom" : 'sending',
    at && `showing ${at}'s copy`,
    n.waiting && `${n.waiting} result${n.waiting > 1 ? 's' : ''} waiting to send`,
  ].filter(Boolean)
  return (
    <button className={`netbar${n.away ? ' away' : ''}`} role="status" onClick={knock} aria-label={`${parts.join(', ')}. tap to try again`}>
      <span className="dot" aria-hidden="true" />{parts.join(' · ')}{n.away && <u>try again</u>}
    </button>
  )
}

/** A screen that couldn't load: why, and a way to try again (it also tries by itself). */
export function Trouble({ err, retry }: { err: string; retry: () => void }) {
  return <div className="center trouble"><span className="err">{err}</span><button className="lnk" onClick={retry}>try again</button></div>
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

/** A panel over the screen. It takes a history entry, so Android back closes it. */
export function Overlay({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    if (!history.state?.overlay) history.pushState({ ...history.state, overlay: true }, '')
    const pop = () => close.current()
    window.addEventListener('popstate', pop)
    return () => window.removeEventListener('popstate', pop)
  }, [])
  const dismiss = () => (history.state?.overlay ? history.back() : onClose())
  return (
    <div className="ovl" role="dialog" aria-label={title} onKeyDown={e => e.key === 'Escape' && dismiss()}>
      <div className="panel"><div className="ph-h">{title}</div>{children}</div>
      <button className="close" onClick={dismiss} aria-label="close" />
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

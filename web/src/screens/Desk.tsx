import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type MyResult } from '../api'
import { headline } from '../format'
import { go } from '../router'
import { Fx, Header, Nav, Tile, useApp } from '../ui'
import { Pasteboard } from './Agenda'

/** Typing an invite's words (or pasting its link) to open it. */
export function JoinByCode({ autoFocus = false }: { autoFocus?: boolean }) {
  const [code, setCode] = useState('')
  const el = useRef<HTMLInputElement>(null)
  useEffect(() => { if (autoFocus) el.current?.focus() }, [autoFocus])
  // the server forgives case and spacing; only the link around the words goes here
  const typed = code.trim().split('/join/').pop()!.trim().replace(/[\s,]+/g, '-')
  const open = () => { if (typed) go(`/join/${encodeURIComponent(typed)}`) }
  return (
    <div className="field">
      <label htmlFor="code">have an invite? type its three words</label>
      <div className="guest">
        <input id="code" ref={el} className="input" placeholder="smug walrus adjourns" value={code}
          onChange={e => setCode(e.target.value)} onKeyDown={e => e.key === 'Enter' && open()}
          autoCapitalize="none" autoComplete="off" spellCheck={false} />
        <button className="btn" onClick={open} disabled={!typed}>open</button>
      </div>
    </div>
  )
}

/** Home when you're not on a board: you can still file results (they count once you join
 *  a board that plays the game), and the way onto a board is right at the top. */
export default function Desk({ shared }: { shared?: string }) {
  const { me, games } = useApp()
  const [mine, setMine] = useState<MyResult[] | null>(null)
  const load = useCallback(() => { api.results().then(setMine).catch(() => setMine([])) }, [])
  useEffect(load, [load])
  const filed = (mine ?? []).filter(r => !r.withdrawn)

  return (
    <div className="app">
      <Header title="desk.xlsx" meta={me.username} />
      <Fx fn="desk" args={[['boards', me.boards.length ? String(me.boards.length) : 'none yet']]} />
      <div className="bd">
        {me.boards.length === 0 && (
          <div className="card desk-cta">
            <b>you're not on a board yet.</b>
            <small>join your friends' board with its invite, or start one and send yours.</small>
            <JoinByCode autoFocus={location.hash === '#join'} />
            <div className="row-a"><button className="btn ghost" onClick={() => go('/new')}>start a board</button></div>
          </div>
        )}
        {me.boards.length > 0 && <JoinByCode autoFocus={location.hash === '#join'} />}
        <Pasteboard shared={shared} onFiled={load} />
        <div className="sec">your results · {filed.length}</div>
        {mine && filed.length === 0 && <div className="sub wrap">nothing filed yet. paste a result above: it's kept, and counts on any board you join that plays it.</div>}
        {filed.slice(0, 30).map(r => (
          <div key={r.id} className="it" style={{ cursor: 'default' }}>
            <Tile game={r.game} name={r.name} />
            <div className="g">
              <div className="nm">{r.name} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>{r.puzzle}</span></div>
              <div className="sub">{headline(games[r.game], r.metrics, r.outcome)}{r.late && <span className="stamp">filed late</span>}</div>
            </div>
            <div className="pr"><span className="rs">{r.day ?? ''}</span></div>
          </div>
        ))}
      </div>
      <Nav on="agenda" />
    </div>
  )
}

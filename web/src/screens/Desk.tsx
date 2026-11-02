import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Board, type MyResult } from '../api'
import { headline } from '../format'
import { go } from '../router'
import { Fx, Header, Nav, Tile, useApp } from '../ui'
import { Pasteboard } from './Agenda'

/** Typing an invite's words (or pasting its link) to open it. */
export function JoinByCode({ autoFocus = false, label = 'have an invite? type its three words' }: { autoFocus?: boolean; label?: string }) {
  const [code, setCode] = useState('')
  const el = useRef<HTMLInputElement>(null)
  useEffect(() => { if (autoFocus) el.current?.focus() }, [autoFocus])
  // the server forgives case and spacing; only the link around the words goes here
  const typed = code.trim().split('/join/').pop()!.trim().replace(/[\s,]+/g, '-')
  const open = () => { if (typed) go(`/join/${encodeURIComponent(typed)}`) }
  return (
    <div className="field">
      <label htmlFor="code">{label}</label>
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
  const { me, games, toast } = useApp()
  const [mine, setMine] = useState<MyResult[] | null>(null)
  const [boards, setBoards] = useState<Board[]>([])
  useEffect(() => { Promise.all(me.boards.map(b => api.board(b.slug))).then(setBoards).catch(() => {}) }, [me.boards])
  // a result opens that day's minutes on the first board that plays the game
  const open = (r: MyResult) => {
    const b = boards.find(x => x.library.some(g => g.game === r.game))
    if (b) go(`/b/${b.slug}/m/${r.game}${r.day ? `/${r.day}` : ''}`)
    else toast(me.boards.length ? `none of your boards plays ${r.name} yet` : `join a board to see how others did on ${r.name}`)
  }
  const load = useCallback(() => { api.results().then(setMine).catch(e => { if (!e.away) setMine([]) }) }, [])
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
            <div className="either">
              <section>
                <h3>join your friends' board</h3>
                <JoinByCode autoFocus={location.hash === '#join'} label="type the three words from their invite" />
              </section>
              <div className="or" aria-hidden="true"><span>or</span></div>
              <section>
                <h3>start your own</h3>
                <small>name it, then send your friends its three words.</small>
                <button className="btn ghost" onClick={() => go('/new')}>start a board →</button>
              </section>
            </div>
          </div>
        )}
        {me.boards.length > 0 && <JoinByCode autoFocus={location.hash === '#join'} />}
        <Pasteboard shared={shared} onFiled={load} />
        <div className="sec">your results · {filed.length}</div>
        {mine && filed.length === 0 && <div className="sub wrap">nothing filed yet. paste a result above: it's kept, and counts on any board you join that plays it.</div>}
        {filed.slice(0, 30).map(r => (
          <div key={r.id} className="it" role="button" tabIndex={0} onClick={() => open(r)} onKeyDown={e => e.key === 'Enter' && open(r)}>
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

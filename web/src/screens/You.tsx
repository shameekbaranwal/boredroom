import { useEffect, useState } from 'react'
import { api, type Board } from '../api'
import { query, usePath } from '../router'
import { Fx, Header, Loading, Nav, Tile, sendOn, useApp } from '../ui'
import { Personal } from './Personal'

export default function You({ slug }: { slug: string }) {
  const { me, games, refreshMe, toast } = useApp()
  const path = usePath()
  const welcome = query(path).get('welcome')
  const [b, setB] = useState<Board | null>(null)
  const [nick, setNick] = useState('')
  const [q, setQ] = useState('')
  const [err, setErr] = useState('')
  useEffect(() => { api.board(slug).then(x => { setB(x); setNick(x.you.nickname) }).catch(e => setErr(e.message)) }, [slug])
  useEffect(() => { if (location.hash === '#seats') document.getElementById('seats')?.scrollIntoView() }, [b])

  if (err) return <div className="app"><Header title="you.xlsx" /><div className="center err">{err}</div></div>
  if (!b) return <div className="app"><Header title="you.xlsx" meta={me.username} /><Loading what="your seat" /></div>

  const lib = new Map(b.library.map(g => [g.game, g]))
  const all = Object.values(games).sort((x, y) => x.name.localeCompare(y.name))
  const onBoard = all.filter(g => lib.has(g.id))
  // the rest of the catalogue sits below the search box, so typing never moves the box
  const term = q.trim().toLowerCase()
  const more = all.filter(g => !lib.has(g.id) && (!term || g.name.includes(term) || g.id.includes(term)))
  const mine = new Set(b.you.agenda)
  const toggle = async (g: string) => {
    try { setB(await api.agenda(slug, g, !mine.has(g))) } catch (e) { toast((e as Error).message) }
  }
  const saveNick = async () => {
    if (nick.trim() && nick !== b.you.nickname) {
      try { setB(await api.nickname(slug, nick.trim())); refreshMe(); toast('noted in the minutes') } catch (e) { toast((e as Error).message) }
    }
  }
  const placeholders = b.members.filter(m => m.kind === 'placeholder')
  const claim = async (username: string, nickname: string) => {
    if (!confirmClaim(nickname)) return
    try {
      const r = await api.claim(slug, username)
      setB(r.board); refreshMe(); toast(`welcome back. ${r.moved} results are yours now.`)
    } catch (e) { toast((e as Error).message) }
  }
  const invite = `${location.origin}/join/${b.invite_code}`

  return (
    <div className="app">
      <Header title="you.xlsx" meta={me.username} />
      <Fx fn="seat" args={[['board', b.name]]} />
      <div className="bd">
        {welcome && <div className="card"><b>welcome aboard, {b.you.nickname}.</b><small>pick your games below. you can always paste a result to add its game.</small></div>}
        <div className="field">
          <label htmlFor="nick">your name on {b.name}</label>
          <input id="nick" className="input" value={nick} onChange={e => setNick(e.target.value)} onBlur={saveNick} onKeyDown={e => e.key === 'Enter' && saveNick()} />
        </div>

        <div className="sec">your games · {mine.size} of {b.library.length} in {b.name}</div>
        {onBoard.map(g => {
          const lg = lib.get(g.id)!
          return (
            <div key={g.id} className="it" style={{ cursor: 'default' }}>
              <Tile game={g.id} name={g.name} />
              <span className="nm" style={{ flex: 1 }}>{g.name}</span>
              <span className="sub">{lg.players} play{g.ranked ? '' : ' · for fun'}</span>
              <button className={`add${mine.has(g.id) ? ' on' : ''}`} onClick={() => toggle(g.id)}>{mine.has(g.id) ? '✓ mine' : 'add'}</button>
            </div>
          )
        })}
        {onBoard.length === 0 && <div className="sub wrap">no games on {b.name} yet. pick some below; adding one puts it on the board for everyone.</div>}
        <div className="field">
          <label htmlFor="q">add a game to the board</label>
          <input id="q" className="input" placeholder="search the games boredroom reads" value={q} onChange={e => setQ(e.target.value)} />
        </div>
        {more.map(g => (
          <div key={g.id} className="it" style={{ cursor: 'default' }}>
            <Tile game={g.id} name={g.name} />
            <span className="nm" style={{ flex: 1 }}>{g.name}</span>
            <span className="sub">new to the board</span>
            <button className="add" onClick={() => toggle(g.id)}>add</button>
          </div>
        ))}
        {term && more.length === 0 && <div className="sub wrap">no game called "{term}" yet. paste one of its results on the agenda and the clerk will ask for it.</div>}

        <div className="sec">invite</div>
        <div className="row-a">
          <span style={{ flex: 1, minWidth: 0 }}>
            <b className="invite-words">{b.invite_code.replace(/-/g, ' ')}</b>
            <span className="sub keep" style={{ display: 'block' }}>{invite}</span>
          </span>
          <button className="btn" onClick={() => sendOn(`join ${b.name} on boredroom: ${invite} (or type "${b.invite_code.replace(/-/g, ' ')}" in the app)`, toast)}>send invite</button>
        </div>

        {placeholders.length > 0 && <>
          <div className="sec" id="seats">imported seats · claim yours to take its history</div>
          {placeholders.map(p => (
            <div key={p.username} className="it" style={{ cursor: 'default' }}>
              <span className="nm" style={{ flex: 1 }}>{p.nickname}</span>
              <span className="sub">{p.games} games</span>
              <button className="add" onClick={() => claim(p.username, p.nickname)}>that's me</button>
            </div>
          ))}
        </>}

        <div className="sec">members · {b.members.length}</div>
        {b.members.filter(m => m.kind !== 'placeholder').map(m => (
          <div key={m.username} className="mrow">
            <span>{m.nickname} <span className="muted">{m.role === 'chair' ? '· chair' : ''}</span></span>
            <span className="chip">{m.games} games</span>
          </div>
        ))}

        <Personal />
      </div>
      <Nav slug={slug} on="you" />
    </div>
  )
}

function confirmClaim(nickname: string): boolean {
  // a real dialog would be nicer; this keeps it to one tap plus a check
  return window.confirm(`claim ${nickname}'s seat? their history becomes yours.`)
}


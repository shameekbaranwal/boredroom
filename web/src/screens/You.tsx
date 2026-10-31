import { useEffect, useState, type ReactNode } from 'react'
import { api, type Board } from '../api'
import { left } from '../format'
import { query, usePath } from '../router'
import { Av, Fx, Header, Loading, Nav, Tile, sendOn, useApp, useNow } from '../ui'
import Boards from './Boards'
import { Personal } from './Personal'

const PEEK = 4  // rows a folded group still shows

/** Which groups are unfolded, remembered on this device. */
function useFold(key: string, open: boolean): [boolean, () => void] {
  const k = `boredroom.fold.${key}`
  const [on, setOn] = useState(() => { try { const v = localStorage.getItem(k); return v === null ? open : v === '1' } catch { return open } })
  return [on, () => setOn(v => { try { localStorage.setItem(k, v ? '0' : '1') } catch { /* fine */ } return !v })]
}

/** A row group, like a spreadsheet's outline: the [−]/[+] sits in the gutter. */
function Group({ id, title, note, open, onFold }: { id?: string; title: ReactNode; note?: ReactNode; open: boolean; onFold: () => void }) {
  return (
    <button id={id} className="sec grp" aria-expanded={open} onClick={onFold}>
      <span className="ol" aria-hidden="true"><span>{open ? '−' : '+'}</span></span>
      <span className="grp-t">{title}</span>
      {note && <span className="grp-n">{note}</span>}
    </button>
  )
}

/** On or off, and it says which. */
export function Switch({ on, label, onFlip }: { on: boolean; label: string; onFlip: () => void }) {
  return (
    <button className={`sw${on ? ' on' : ''}`} role="switch" aria-checked={on} aria-label={label} onClick={onFlip}>
      <span className="sw-w">{on ? 'playing' : 'not playing'}</span><i aria-hidden="true" />
    </button>
  )
}

export default function You({ slug }: { slug: string }) {
  const { me, games, refreshMe, toast } = useApp()
  const path = usePath()
  const now = useNow()
  const welcome = query(path).get('welcome')
  const [b, setB] = useState<Board | null>(null)
  const [nick, setNick] = useState('')
  const [q, setQ] = useState('')
  const [browse, setBrowse] = useState(false)
  const [err, setErr] = useState('')
  const [asking, setAsking] = useState('')  // the seat whose "that's me" is waiting for a yes
  const [picker, setPicker] = useState(false)
  const [gamesOpen, foldGames] = useFold('games', false)
  const [seatsOpen, foldSeats] = useFold('seats', false)
  const [membersOpen, foldMembers] = useFold('members', false)
  const [youOpen, foldYou] = useFold('you', false)
  useEffect(() => { api.board(slug).then(x => { setB(x); setNick(x.you.nickname) }).catch(e => setErr(e.message)) }, [slug])
  useEffect(() => { if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView() }, [b])

  if (err) return <div className="app"><Header title="you.xlsx" /><div className="center err">{err}</div></div>
  if (!b) return <div className="app"><Header title="you.xlsx" meta={me.username} /><Loading what="your seat" /></div>

  const lib = new Map(b.library.map(g => [g.game, g]))
  const mine = new Set(b.you.agenda)
  const all = Object.values(games).sort((x, y) => x.name.localeCompare(y.name))
  // yours first, then the rest of the board's library
  const onBoard = all.filter(g => lib.has(g.id)).sort((x, y) => Number(mine.has(y.id)) - Number(mine.has(x.id)))
  const showGames = gamesOpen || location.hash === '#games' ? onBoard : onBoard.slice(0, Math.max(PEEK, [...mine].length))
  const term = q.trim().toLowerCase()
  const more = all.filter(g => !lib.has(g.id) && (!term || g.name.includes(term) || g.id.includes(term)))
  const toggle = async (g: string) => {
    try { setB(await api.agenda(slug, g, !mine.has(g))) } catch (e) { toast((e as Error).message) }
  }
  const saveNick = async () => {
    if (nick.trim() && nick !== b.you.nickname) {
      try { setB(await api.nickname(slug, nick.trim())); refreshMe(); toast('noted in the minutes') } catch (e) { toast((e as Error).message) }
    }
  }
  const placeholders = b.members.filter(m => m.kind === 'placeholder')
  const people = b.members.filter(m => m.kind !== 'placeholder')
  const claim = async (username: string) => {
    setAsking('')
    try {
      const r = await api.claim(slug, username)
      setB(r.board); setNick(r.board.you.nickname); refreshMe(); toast(`welcome back. ${r.moved} results are yours now.`)
    } catch (e) { toast((e as Error).message) }
  }
  const words = b.invite.code.replace(/-/g, ' ')
  const link = `${location.origin}/join/${b.invite.code}`
  const renew = async () => {
    try { setB(await api.renewInvite(slug)); toast('new invite. the old one stopped working.') } catch (e) { toast((e as Error).message) }
  }

  return (
    <div className="app">
      <Header title={`${b.name}.xlsx`} meta="you" onTitle={() => setPicker(true)} />
      <Fx fn="seat" args={[['board', b.name], ['as', b.you.nickname]]} />
      <div className="bd">
        {welcome && <div className="card"><b>welcome aboard, {b.you.nickname}.</b><small>switch on the games you play. pasting a result switches its game on too.</small></div>}
        <div className="field">
          <label htmlFor="nick">your name on {b.name}</label>
          <input id="nick" className="input" value={nick} onChange={e => setNick(e.target.value)} onBlur={saveNick} onKeyDown={e => e.key === 'Enter' && saveNick()} />
        </div>

        <div className="invite-row" id="invite">
          <div className="inv-top">
            <span className="inv-k">your invite to {b.name}</span>
            {b.invite.expires_at && <span className="inv-exp">works for {left(b.invite.expires_at, now)} more</span>}
          </div>
          <b className="invite-words keep">{words}</b>
          <span className="sub keep">{link}</span>
          <div className="row-a">
            <button className="btn" onClick={() => sendOn(`join ${b.name} on boredroom: ${link} (or type "${words}" in the app). it works for a day.`, toast)}>send invite</button>
            <button className="lnk" onClick={renew}>new words</button>
          </div>
          <small className="muted">it's yours: anyone who joins with it shows up as invited by {b.you.nickname}. a new one every day, or sooner if you ask.</small>
        </div>

        <Group id="games" title={<>your games <b>{mine.size}</b> of {b.library.length}</>} note={gamesOpen ? 'fold' : onBoard.length > showGames.length ? `+${onBoard.length - showGames.length} more` : undefined} open={gamesOpen} onFold={foldGames} />
        {showGames.map(g => {
          const lg = lib.get(g.id)!
          return (
            <div key={g.id} className={`it${mine.has(g.id) ? '' : ' off'}`} style={{ cursor: 'default' }}>
              <Tile game={g.id} name={g.name} />
              <div className="g">
                <div className="nm">{g.name}</div>
                <div className="sub">{lg.players} of {b.members.length} play{g.ranked ? '' : ' · for fun'}</div>
              </div>
              <Switch on={mine.has(g.id)} label={`${g.name} on my agenda`} onFlip={() => toggle(g.id)} />
            </div>
          )
        })}
        {!gamesOpen && onBoard.length > showGames.length && (
          <button className="more" onClick={foldGames}>{onBoard.length - showGames.length} more in {b.name}'s library ↓</button>
        )}
        {onBoard.length === 0 && <div className="sub wrap">no games on {b.name} yet. find some below; switching one on puts it on the board for everyone.</div>}
        {(gamesOpen || onBoard.length === 0) && <>
          <div className="field">
            <label htmlFor="q">add a game to {b.name}</label>
            <input id="q" className="input" placeholder={`search ${all.length - onBoard.length} more games boredroom reads`} value={q} onChange={e => setQ(e.target.value)} />
          </div>
          {(term || browse) && more.map(g => (
            <div key={g.id} className="it off" style={{ cursor: 'default' }}>
              <Tile game={g.id} name={g.name} />
              <div className="g"><div className="nm">{g.name}</div><div className="sub">new to the board</div></div>
              <Switch on={false} label={`add ${g.name}`} onFlip={() => toggle(g.id)} />
            </div>
          ))}
          {!term && !browse && more.length > 0 && <button className="more" onClick={() => setBrowse(true)}>browse all {more.length} ↓</button>}
          {term && more.length === 0 && <div className="sub wrap">no game called "{term}" yet. paste one of its results on the agenda and the clerk will ask for it.</div>}
        </>}

        {placeholders.length > 0 && <>
          <Group id="seats" title={<>unclaimed seats <b>{placeholders.length}</b></>} note="from the chat history" open={seatsOpen} onFold={foldSeats} />
          {(seatsOpen || location.hash === '#seats' ? placeholders : placeholders.slice(0, 3)).map(p => (
            <div key={p.username} className="it" style={{ cursor: 'default' }}>
              <Av name={p.nickname} />
              <div className="g"><div className="nm">{p.nickname}</div><div className="sub">{p.games} {p.games === 1 ? 'game' : 'games'} · waiting for its owner</div></div>
              {asking === p.username
                ? <span className="row-a ask"><span className="muted">their history becomes yours.</span><button className="btn" onClick={() => claim(p.username)}>claim</button><button className="lnk" onClick={() => setAsking('')}>no</button></span>
                : <button className="add" onClick={() => setAsking(p.username)}>that's me</button>}
            </div>
          ))}
          {!seatsOpen && location.hash !== '#seats' && placeholders.length > 3 && <button className="more" onClick={foldSeats}>{placeholders.length - 3} more unclaimed seats ↓</button>}
        </>}

        <Group id="members" title={<>members <b>{people.length}</b></>} open={membersOpen} onFold={foldMembers}
          note={!membersOpen && <span className="faces">{people.slice(0, 6).map(m => <Av key={m.username} name={m.nickname} />)}</span>} />
        {membersOpen && people.map(m => (
          <div key={m.username} className="mrow">
            <span className="who"><Av name={m.nickname} />{m.nickname} <span className="muted" style={{ fontWeight: 400 }}>{m.role === 'chair' ? '· chair' : ''}{m.kind === 'guest' ? ' · guest' : ''}</span></span>
            <span className="chip">{m.games} games</span>
          </div>
        ))}

        <Group id="you" title="you, everywhere" note={!youOpen && <span className="keep">{me.tz} · {me.kind === 'account' ? 'signed in' : 'guest'}</span>} open={youOpen} onFold={foldYou} />
        {youOpen ? <Personal /> : me.kind === 'guest' && <Personal guestOnly />}
      </div>
      <Nav slug={slug} on="you" />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
    </div>
  )
}

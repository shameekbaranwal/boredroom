import { useEffect, useRef, useState } from 'react'
import { api, type Board } from '../api'
import { left } from '../format'
import { go, query, usePath } from '../router'
import { Av, Fx, Header, Loading, Nav, Tile, sendOn, useApp, useNow } from '../ui'
import Boards from './Boards'
import { Motion, Personal } from './Personal'

const SEATS = 3  // unclaimed seats shown before "n more"

/** On or off, and it says which. */
export function Switch({ on, label, onFlip }: { on: boolean; label: string; onFlip: () => void }) {
  return (
    <button className={`sw${on ? ' on' : ''}`} role="switch" aria-checked={on} aria-label={label} onClick={onFlip}>
      <span className="sw-w">{on ? 'playing' : 'not playing'}</span><i aria-hidden="true" />
    </button>
  )
}

/** Yours first, then the rest, by name. Worked out once a visit so rows never jump. */
function sortGames(b: Board, names: (g: string) => string): string[] {
  const mine = new Set(b.you.agenda)
  return b.library.map(g => g.game).sort((x, y) => Number(mine.has(y)) - Number(mine.has(x)) || names(x).localeCompare(names(y)))
}

/** Flipping games: the switch moves on the tap, the server catches up behind it. One
 *  request per game at a time; taps made meanwhile send only where they ended up. */
function useAgenda(slug: string, b: Board | null, setB: (b: Board) => void) {
  const { toast } = useApp()
  const [want, setWant] = useState<Record<string, boolean>>({})
  const latest = useRef<Record<string, boolean>>({})
  const busy = useRef<Set<string>>(new Set())
  const server = new Set(b?.you.agenda ?? [])
  const on = (g: string) => want[g] ?? server.has(g)
  const drop = (g: string) => { delete latest.current[g]; setWant(w => { const { [g]: _, ...rest } = w; return rest }) }
  const sync = async (g: string, name: string) => {
    if (busy.current.has(g)) return
    busy.current.add(g)
    try {
      for (;;) {
        const sent = latest.current[g]
        const nb = await api.agenda(slug, g, sent)
        if (latest.current[g] === sent) { setB(nb); drop(g); break }
      }
    } catch {
      drop(g)
      toast(`couldn't reach the clerk. ${name} is back how it was.`, { label: 'try again', run: () => set(g, name, !server.has(g)) })
    } finally { busy.current.delete(g) }
  }
  const set = (g: string, name: string, v: boolean) => {
    latest.current[g] = v
    setWant(w => ({ ...w, [g]: v }))
    sync(g, name)
  }
  const flip = (g: string, name: string) => {
    const v = !on(g)
    set(g, name, v)
    if (!v) toast(`${name} is off your agenda. results stay in the minutes.`, { label: 'undo', run: () => set(g, name, true) })
  }
  // the "n of m play" count, with the tap already counted
  const players = (g: string, n: number) => n + (on(g) === server.has(g) ? 0 : on(g) ? 1 : -1)
  return { on, flip, players, count: (ids: string[]) => ids.filter(on).length }
}

/** The row flashes once when its game goes on. */
function useLit(): [(g: string) => boolean, (g: string) => void] {
  const [lit, setLit] = useState<Set<string>>(new Set())
  const light = (g: string) => {
    setLit(s => new Set(s).add(g))
    setTimeout(() => setLit(s => { const n = new Set(s); n.delete(g); return n }), 750)
  }
  return [g => lit.has(g), light]
}

export default function You({ slug }: { slug: string }) {
  const { me, games, refreshMe, toast } = useApp()
  const path = usePath()
  const now = useNow()
  const welcome = query(path).get('welcome')
  const [sheet, setSheet] = useState<'board' | 'everywhere'>(() => location.hash === '#everywhere' ? 'everywhere' : 'board')
  const [b, setB] = useState<Board | null>(null)
  const [err, setErr] = useState('')
  const [picker, setPicker] = useState(false)
  const [deleting, setDeleting] = useState(false)
  useEffect(() => { api.board(slug).then(setB).catch(e => setErr(e.message)) }, [slug])
  useEffect(() => { if (location.hash && location.hash !== '#everywhere') document.getElementById(location.hash.slice(1))?.scrollIntoView() }, [b])
  const show = (s: 'board' | 'everywhere') => {
    setSheet(s)
    history.replaceState(null, '', location.pathname + location.search + (s === 'everywhere' ? '#everywhere' : ''))
  }

  if (err) return <div className="app"><Header title="you.xlsx" /><div className="center err">{err}</div></div>
  if (!b) return <div className="app"><Header title="you.xlsx" meta={me.username} /><Loading what="your seat" /></div>

  return (
    <div className="app">
      <Header title={`${b.name}.xlsx`} meta="you" onTitle={() => setPicker(true)} />
      {sheet === 'board'
        ? <Fx fn="seat" args={[['board', b.name], ['as', b.you.nickname]]} />
        : <Fx fn="you" args={[['username', me.username], ['tz', me.tz]]} />}
      <div className="sheets" role="tablist">
        <button role="tab" aria-selected={sheet === 'board'} className={sheet === 'board' ? 'on' : ''} onClick={() => show('board')}>on {b.name}</button>
        <button role="tab" aria-selected={sheet === 'everywhere'} className={sheet === 'everywhere' ? 'on' : ''} onClick={() => show('everywhere')}>everywhere</button>
      </div>
      {sheet === 'board'
        ? <BoardSheet b={b} setB={setB} welcome={!!welcome} now={now} games={games} refreshMe={refreshMe} toast={toast}
            onDelete={() => { setDeleting(true); show('everywhere'); window.scrollTo(0, 0) }} />
        : <div className="bd"><Personal deleting={deleting} /></div>}
      <Nav slug={slug} on="you" />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
    </div>
  )
}

type Ctx = ReturnType<typeof useApp>

function BoardSheet({ b, setB, welcome, now, onDelete, games, refreshMe, toast }:
  { b: Board; setB: (b: Board) => void; welcome: boolean; now: number; onDelete: () => void; games: Ctx['games']; refreshMe: Ctx['refreshMe']; toast: Ctx['toast'] }) {
  const { me } = useApp()
  const slug = b.slug
  const name = (g: string) => games[g]?.name ?? b.library.find(x => x.game === g)?.name ?? g
  const agenda = useAgenda(slug, b, setB)
  const [isLit, light] = useLit()
  const [nick, setNick] = useState(b.you.nickname)
  const [order, setOrder] = useState(() => sortGames(b, name))
  const [adding, setAdding] = useState<string[] | null>(null)  // the games new to the board, as the search opened
  const [q, setQ] = useState('')
  const [browse, setBrowse] = useState(false)
  const [seatsAll, setSeatsAll] = useState(false)
  const [asking, setAsking] = useState('')  // the seat whose "that's me" is waiting for a yes
  const [membersOpen, setMembersOpen] = useState(false)
  const addRef = useRef<HTMLInputElement>(null)

  // games new to the library join the list when the search closes, not under your finger
  const libIds = b.library.map(g => g.game)
  useEffect(() => {
    if (adding) return
    setOrder(o => {
      const fresh = libIds.filter(g => !o.includes(g))
      fresh.forEach(light)
      return [...o.filter(g => libIds.includes(g)), ...fresh]
    })
  }, [libIds.join(), adding === null])  // eslint-disable-line react-hooks/exhaustive-deps

  const lib = new Map(b.library.map(g => [g.game, g]))
  const flip = (g: string) => { if (!agenda.on(g)) light(g); agenda.flip(g, name(g)) }
  const all = Object.values(games)
  const catalogue = all.filter(g => !lib.has(g.id)).length
  const term = q.trim().toLowerCase()
  const found = (adding ?? []).filter(g => !term || name(g).includes(term) || g.includes(term))
  const openAdd = () => {
    setAdding(all.filter(g => !lib.has(g.id)).map(g => g.id).sort((x, y) => name(x).localeCompare(name(y))))
    setTimeout(() => addRef.current?.focus(), 0)
  }
  const closeAdd = () => { setAdding(null); setQ(''); setBrowse(false) }

  const saveNick = async () => {
    if (nick.trim() && nick !== b.you.nickname) {
      try { setB(await api.nickname(slug, nick.trim())); refreshMe(); toast('noted in the minutes') } catch (e) { toast((e as Error).message) }
    }
  }
  const placeholders = b.members.filter(m => m.kind === 'placeholder')
  const people = b.members.filter(m => m.kind !== 'placeholder')
  const chair = people.find(m => m.role === 'chair')
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
    <div className="bd">
      {welcome && <div className="card"><b>welcome aboard, {b.you.nickname}.</b><small>switch on the games you play. pasting a result switches its game on too.</small></div>}
      <div className="field inline">
        <label htmlFor="nick">your name on {b.name}</label>
        <input id="nick" className="input" value={nick} onChange={e => setNick(e.target.value)} onBlur={saveNick} onKeyDown={e => e.key === 'Enter' && saveNick()} />
      </div>

      <div className="invite-row" id="invite">
        <div className="inv-top">
          <b className="invite-words keep">{words}</b>
          {b.invite.expires_at && <span className="inv-exp">{left(b.invite.expires_at, now)} left</span>}
        </div>
        <div className="row-a">
          <button className="btn" onClick={() => sendOn(`join ${b.name} on boredroom: ${link} (or type "${words}" in the app). it works for a day.`, toast)}>send invite</button>
          <button className="lnk" onClick={renew}>new words</button>
        </div>
        <small className="muted">your invite. anyone who joins with it shows up as invited by you.</small>
      </div>

      <div className="sec" id="games">your games <b className="num">{agenda.count(order)}</b> of {b.library.length}</div>
      {order.filter(g => lib.has(g)).map(g => {
        const lg = lib.get(g)!, on = agenda.on(g)
        return (
          <div key={g} className={`it game${on ? '' : ' off'}${isLit(g) ? ' lit' : ''}`}>
            <Tile game={g} name={name(g)} />
            <div className="g">
              <div className="nm">{name(g)}</div>
              <div className="sub">{agenda.players(g, lg.players)} of {b.members.length} play{games[g]?.ranked === false ? ' · for fun' : ''}</div>
            </div>
            <Switch on={on} label={`${name(g)} on my agenda`} onFlip={() => flip(g)} />
          </div>
        )
      })}
      {order.length === 0 && !adding && <div className="sub wrap">no games on {b.name} yet. add one; it goes on the board for everyone.</div>}
      {adding === null
        ? <button className="more add-row" onClick={openAdd}>+ add a game <span className="muted">· {catalogue} more boredroom reads</span></button>
        : <>
          <div className="field">
            <label htmlFor="q">add a game to {b.name} <button className="lnk" onClick={closeAdd}>done</button></label>
            <input id="q" ref={addRef} className="input" placeholder={`search ${adding.length} games`} value={q} onChange={e => setQ(e.target.value)}
              onKeyDown={e => e.key === 'Escape' && closeAdd()} />
          </div>
          {(term || browse) && found.map(g => {
            const on = agenda.on(g)
            return (
              <div key={g} className={`it game${on ? '' : ' off'}${isLit(g) ? ' lit' : ''}`}>
                <Tile game={g} name={name(g)} />
                <div className="g"><div className="nm">{name(g)}</div><div className="sub">{on ? `on ${b.name} now` : `new to ${b.name}`}</div></div>
                <Switch on={on} label={`add ${name(g)}`} onFlip={() => flip(g)} />
              </div>
            )
          })}
          {!term && !browse && <button className="more" onClick={() => setBrowse(true)}>browse all {adding.length} ↓</button>}
          {term && found.length === 0 && <div className="sub wrap">no game called "{term}" yet. paste one of its results on the agenda and the clerk will ask for it.</div>}
        </>}

      {placeholders.length > 0 && <>
        <div className="sec" id="seats">unclaimed seats <b className="num">{placeholders.length}</b> <span className="sec-n">· from the chat history</span></div>
        {(seatsAll || location.hash === '#seats' ? placeholders : placeholders.slice(0, SEATS)).map(p => (
          <div key={p.username} className="it" style={{ cursor: 'default' }}>
            <Av name={p.nickname} />
            <div className="g"><div className="nm">{p.nickname}</div><div className="sub">{p.games} {p.games === 1 ? 'game' : 'games'} · waiting for its owner</div></div>
            {asking === p.username
              ? <span className="row-a ask"><span className="muted">their history becomes yours.</span><button className="btn" onClick={() => claim(p.username)}>claim</button><button className="lnk" onClick={() => setAsking('')}>no</button></span>
              : <button className="add" onClick={() => setAsking(p.username)}>that's me</button>}
          </div>
        ))}
        {!seatsAll && location.hash !== '#seats' && placeholders.length > SEATS && <button className="more" onClick={() => setSeatsAll(true)}>{placeholders.length - SEATS} more ↓</button>}
      </>}

      <button className="sec grp" id="members" aria-expanded={membersOpen} onClick={() => setMembersOpen(v => !v)}>
        <span className="ol" aria-hidden="true"><span>{membersOpen ? '−' : '+'}</span></span>
        <span className="grp-t">members <b>{people.length}</b></span>
        <span className="grp-n">{!membersOpen && <span className="faces">{people.slice(0, 6).map(m => <Av key={m.username} name={m.nickname} />)}</span>}{chair && <span>&nbsp;chair: {chair.nickname}</span>}</span>
      </button>
      {membersOpen && people.map(m => (
        <div key={m.username} className="mrow">
          <span className="who"><Av name={m.nickname} />{m.nickname} <span className="muted" style={{ fontWeight: 400 }}>{m.role === 'chair' ? '· chair' : ''}{m.kind === 'guest' ? ' · guest' : ''}</span></span>
          <span className="chip">{m.games} games</span>
        </div>
      ))}

      {b.you.role === 'chair' && <>
        <div className="sec" id="board">{b.name}'s settings <span className="sec-n">· you hold the chair</span></div>
        <ChairSettings board={b} onBoard={x => { setB(x); refreshMe() }} />
      </>}

      {me.kind === 'guest' && <Personal guestOnly />}
      <LeaveBoard b={b} onDelete={onDelete} />
    </div>
  )
}

/** Giving up your seat on this board. Says exactly what goes where before it happens. */
function LeaveBoard({ b, onDelete }: { b: Board; onDelete: () => void }) {
  const { me, refreshMe, toast } = useApp()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const l = b.leaving
  const leave = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api.leave(b.slug)
      await refreshMe()
      const next = me.boards.find(x => x.slug !== b.slug)
      toast(r.closed ? `${b.name} has been wound up.` : `you've left ${b.name}. your absence is noted in the minutes.`)
      go(next ? `/b/${next.slug}` : '/desk', true)
    } catch (e) { setErr((e as Error).message); setBusy(false) }
  }
  return (
    <Motion label={`leave ${b.name}`} heading={`motion to leave ${b.name}`}
      yes={busy ? 'leaving…' : `yes, leave ${b.name}`} no="no, stay" busy={busy} err={err} onYes={leave}
      foot={<button className="lnk" onClick={onDelete}>leaving everything? delete your account instead ›</button>}>
      <p>your seat and your games here go. what you filed stays yours, on your other boards, and stops showing on {b.name}.</p>
      {l.claimed && <p>the {l.claimed.results} {l.claimed.results === 1 ? 'result' : 'results'} imported from the chat go back to an unclaimed seat called <b>{l.claimed.nickname}</b>, so it can be claimed again.</p>}
      {l.alone
        ? <p>you're the only member. leaving dissolves {b.name} and its minutes, for good.</p>
        : l.chair && l.heir && <p>you hold the chair. it passes to <b>{l.heir}</b>, the longest-serving member.</p>}
      <p className="muted">you can come back with an invite.</p>
    </Motion>
  )
}

/** What only the chair can change. Each change that can't be taken back asks once, in place. */
function ChairSettings({ board, onBoard }: { board: Board; onBoard: (b: Board) => void }) {
  const { games, toast } = useApp()
  const [name, setName] = useState(board.name)
  const [drop, setDrop] = useState('')
  const [sure, setSure] = useState<'' | 'drop' | 'retire'>('')
  const run = async (f: () => Promise<Board>, done: string) => {
    setSure('')
    try { onBoard(await f()); toast(done) } catch (e) { toast((e as Error).message) }
  }
  const rename = () => {
    const v = name.trim().toLowerCase()
    if (v && v !== board.name) run(() => api.rename(board.slug, v), `the board is ${v} now. links still work.`)
  }
  const dropping = board.library.find(g => g.game === drop)
  return <>
    <div className="field">
      <label htmlFor="bname">the board's name</label>
      <input id="bname" className="input" value={name} onChange={e => setName(e.target.value)} onBlur={rename} onKeyDown={e => e.key === 'Enter' && rename()} />
    </div>
    <div className="field">
      <label htmlFor="drop">take a game off the board <span className="muted">· it leaves everyone's agenda; results stay in the minutes</span></label>
      <div className="guest">
        <select id="drop" className="input" value={drop} onChange={e => { setDrop(e.target.value); setSure('') }}>
          <option value="">pick a game</option>
          {board.library.map(g => <option key={g.game} value={g.game}>{games[g.game]?.name ?? g.name} · {g.players} play</option>)}
        </select>
        {sure === 'drop' && dropping
          ? <button className="btn danger" onClick={() => run(() => api.dropGame(board.slug, drop).then(x => { setDrop(''); return x }), `${dropping.name} is off the board.`)}>yes, remove</button>
          : <button className="btn ghost" disabled={!drop} onClick={() => setSure('drop')}>remove</button>}
      </div>
      {sure === 'drop' && dropping && <small className="muted">{dropping.players} {dropping.players === 1 ? 'person has' : 'people have'} it on their agenda. sure?</small>}
    </div>
    <div className="field">
      <label>every invite that's out there</label>
      <div className="row-a">
        {sure === 'retire'
          ? <><button className="btn danger" onClick={() => run(() => api.retireInvites(board.slug).then(r => r.board), 'every old invite stopped working. members have new words.')}>yes, retire them all</button>
              <button className="lnk" onClick={() => setSure('')}>no</button></>
          : <button className="btn ghost" onClick={() => setSure('retire')}>retire all invites</button>}
      </div>
      <small className="muted">for when a link ended up somewhere it shouldn't. everyone's words stop working; each member gets new ones.</small>
    </div>
  </>
}

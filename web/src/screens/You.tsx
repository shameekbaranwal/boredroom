import { useEffect, useRef, useState } from 'react'
import { api, type Board, type Member } from '../api'
import { left } from '../format'
import { go, query, usePath } from '../router'
import { Av, Fx, FxEdit, Ghost, Header, Nav, Tile, goBack, sendOn, useApp, useFresh, useNow } from '../ui'
import Boards from './Boards'
import { CloseAccount, Motion, YourFile, useUsernameEdit } from './Personal'

// The "you" page keeps a board's books: your seat, your agenda, the register of members,
// the bylaws. Two things about games, kept apart in the words too:
//   the board's games (its library): shared; anyone adds, the chair (or whoever added it) takes off
//   your agenda: which of those you play; a switch per game, yours alone Every row is one of three kinds, and nothing folds:
//   a value cell changes in place (undo by toast); text is edited in the formula bar
//   a document row (›) opens its own page, with the bottom tabs still there
//   a motion (red, always last) opens a page that says what will happen, then yes or no

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
    return v
  }
  // the "n of m play" count, with the tap already counted
  const players = (g: string, n: number) => n + (on(g) === server.has(g) ? 0 : on(g) ? 1 : -1)
  return { on, flip, players, count: (ids: string[]) => ids.filter(on).length }
}

/** A row marked for a moment: lit green when a game goes on your agenda, struck through when it comes off. */
function useMark(ms = 750): [(g: string) => boolean, (g: string) => void] {
  const [marked, setMarked] = useState<Set<string>>(new Set())
  const mark = (g: string) => {
    setMarked(s => new Set(s).add(g))
    setTimeout(() => setMarked(s => { const n = new Set(s); n.delete(g); return n }), ms)
  }
  return [g => marked.has(g), mark]
}

const buzz = () => navigator.vibrate?.(8)
const people = (b: Board) => b.members.filter(m => m.kind !== 'placeholder')
const unissued = (b: Board) => b.members.filter(m => m.kind === 'placeholder')
const bySeniority = (ms: Member[]) => [...ms].sort((x, y) => x.joined_at.localeCompare(y.joined_at))

type Page = 'add' | 'register' | 'bylaws' | 'claim' | 'strike' | 'retire' | 'resign' | 'close'
const TITLES: Record<Page, string> = {
  add: 'add a game', register: 'the register', bylaws: 'the bylaws', claim: 'a claim',
  strike: 'a game off', retire: 'invitations', resign: 'resignation', close: 'wind up',
}

export default function You({ slug, page, arg }: { slug: string; page?: string; arg?: string }) {
  const { me } = useApp()
  const [b, setB] = useState<Board | null>(null)
  const [err, setErr] = useState('')
  const load = () => api.board(slug).then(setB).catch(e => setErr(e.message))
  useEffect(() => { load() }, [slug])  // eslint-disable-line react-hooks/exhaustive-deps
  useFresh(load)

  const pg = (page && page in TITLES ? page : null) as Page | null
  const home = `/b/${slug}/you`
  if (err) return <div className="app"><Header title="you.xlsx" /><div className="center err">{err}</div><Nav slug={slug} on="you" /></div>
  if (!b) return (
    <div className="app">
      <Header title={`${me.boards.find(x => x.slug === slug)?.name ?? slug}.xlsx`} meta={pg ? TITLES[pg] : 'you'} back={pg ? home : undefined} />
      <Fx fn="seat" args={[['board', slug]]} />
      <Ghost what="your seat" />
      <Nav slug={slug} on="you" />
    </div>
  )
  if (!pg) return <Main b={b} setB={setB} />

  const parent = pg === 'claim' ? `${home}/register` : pg === 'strike' || pg === 'retire' ? `${home}/bylaws` : home
  const props = { b, setB, back: parent, arg: arg ?? '' }
  return (
    <div className="app">
      <Header title={`${b.name}.xlsx`} meta={TITLES[pg]} back={parent} />
      {pg === 'add' && <AddGame {...props} />}
      {pg === 'register' && <Register {...props} />}
      {pg === 'bylaws' && <Bylaws {...props} />}
      {pg === 'claim' && <><Fx fn="claim" args={[['board', b.name], ['seat', arg ?? '']]} /><Claim {...props} /></>}
      {pg === 'strike' && <><Fx fn="strike" args={[['board', b.name], ['game', arg ?? '']]} /><Strike {...props} /></>}
      {pg === 'retire' && <><Fx fn="retire" args={[['board', b.name], ['invitations', 'all']]} /><Retire {...props} /></>}
      {pg === 'resign' && <><Fx fn="resign" args={[['board', b.name], ['as', b.you.nickname]]} /><Resign {...props} /></>}
      {pg === 'close' && <><Fx fn="close" args={[['username', me.username]]} /><CloseAccount back={home} /></>}
      <Nav slug={slug} on="you" />
    </div>
  )
}

type P = { b: Board; setB: (b: Board) => void; back: string; arg: string }

/** The main page: two sheets, "on {board}" and "everywhere". */
function Main({ b, setB }: { b: Board; setB: (b: Board) => void }) {
  const { me, games, refreshMe, toast } = useApp()
  const path = usePath()
  const now = useNow()
  const slug = b.slug
  const [sheet, setSheet] = useState<'board' | 'everywhere'>(() => location.hash === '#everywhere' ? 'everywhere' : 'board')
  const [picker, setPicker] = useState(false)
  const [nick, setNick] = useState<string | null>(null)  // editing your name, in the formula bar
  const [recalc, setRecalc] = useState<number | null>(null)
  const recalcT = useRef<ReturnType<typeof setTimeout>>(undefined)
  const user = useUsernameEdit()
  const name = (g: string) => games[g]?.name ?? b.library.find(x => x.game === g)?.name ?? g
  const agenda = useAgenda(slug, b, setB)
  const [isLit, light] = useMark()
  const [isStruck, strike] = useMark(600)
  const [order] = useState(() => sortGames(b, name))
  const stamp = query(path).get('stamp')

  useEffect(() => {
    if (location.hash === '#seats') go(`/b/${slug}/you/register#seats`, true)
    else if (location.hash === '#games') document.getElementById('games')?.scrollIntoView()
    if (stamp) setTimeout(() => history.replaceState(history.state, '', location.pathname), 1200)
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const show = (s: 'board' | 'everywhere') => {
    setSheet(s); setNick(null)
    history.replaceState(history.state, '', location.pathname + (s === 'everywhere' ? '#everywhere' : ''))
  }
  const saveNick = async () => {
    const v = (nick ?? '').trim()
    if (!v || v === b.you.nickname) { setNick(null); return }
    try { setB(await api.nickname(slug, v)); refreshMe(); setNick(null); toast('noted in the minutes') } catch (e) { toast((e as Error).message) }
  }

  // games added since the visit began go at the end, not where your finger is
  const lib = new Map(b.library.map(g => [g.game, g]))
  const ids = [...order.filter(g => lib.has(g)), ...b.library.map(g => g.game).filter(g => !order.includes(g))]
  const flip = (g: string) => {
    buzz()
    const v = agenda.flip(g, name(g))
    if (v) light(g); else strike(g)
    clearTimeout(recalcT.current)
    setRecalc(agenda.count(ids) + (v ? 1 : -1))
    recalcT.current = setTimeout(() => setRecalc(null), 1300)
  }
  const ps = people(b)
  const small = ps.length < 3  // a young board's first job is recruiting
  const catalogue = Object.values(games).filter(g => !lib.has(g.id)).length
  const seat = bySeniority(ps).findIndex(m => m.username === me.username) + 1
  const mine = b.members.find(m => m.username === me.username)
  const since = mine ? new Date(mine.joined_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }).toLowerCase() : ''
  const open = unissued(b)

  const fx = sheet === 'everywhere'
    ? user.fx ?? <Fx fn="you" args={[['username', me.username], ['tz', me.tz]]} />
    : nick !== null
      ? <FxEdit fn="seat" field="as" value={nick} onChange={setNick} onSave={saveNick} onCancel={() => setNick(null)} ok={!!nick.trim()}
          note={{ text: `your name on ${b.name}. others see it in the minutes.`, tone: 'idle' }} />
      : recalc !== null
        ? <div className="fx keep recalc"><i>fx</i>=COUNTIF(agenda,"playing")<b>&nbsp;→ {recalc}</b></div>
        : <Fx fn="seat" args={[['board', b.name], ['as', b.you.nickname]]} />

  return (
    <div className="app">
      <Header title={`${b.name}.xlsx`} meta="you" onTitle={() => setPicker(true)} />
      {fx}
      <div className="sheets" role="tablist">
        <button role="tab" aria-selected={sheet === 'board'} className={sheet === 'board' ? 'on' : ''} onClick={() => show('board')}>on {b.name}</button>
        <button role="tab" aria-selected={sheet === 'everywhere'} className={sheet === 'everywhere' ? 'on' : ''} onClick={() => show('everywhere')}>everywhere</button>
      </div>
      {sheet === 'everywhere'
        ? <div className="bd"><YourFile onEditName={user.start} closeTo={`/b/${slug}/you/close`} /></div>
        : <div className="bd">
          {query(path).get('welcome') && <div className="card"><b>welcome aboard, {b.you.nickname}.</b><small>switch on the games you play. pasting a result switches its game on too.</small></div>}
          <div className="seat-card">
            <Av name={b.you.nickname} />
            <div className="g">
              <button className="seat-name" onClick={() => setNick(b.you.nickname)} aria-label={`your name on ${b.name}: ${b.you.nickname}. change it`}>
                {b.you.nickname}<span className="pen" aria-hidden="true">✎</span>
              </button>
              <div className="sub">seat {seat || '–'} of {ps.length}{since && ` · since ${since}`} · {mine?.results ?? 0} on file</div>
            </div>
            {b.you.role === 'chair' && <span className="rstamp">chair</span>}
            {stamp === 'claimed' && <span className="rstamp thunk">claimed</span>}
          </div>
          {small && <Invitation b={b} setB={setB} now={now} />}

          <div className="sec" id="games">your agenda <b className={`num${recalc !== null ? ' lit' : ''}`}>{agenda.count(ids)}</b> <span className="sec-n">of {b.name}'s {b.library.length} {b.library.length === 1 ? 'game' : 'games'} · switch on the ones you play</span></div>
          {ids.map(g => {
            const lg = lib.get(g)!, on = agenda.on(g)
            return (
              <div key={g} className={`it game${on ? '' : ' off'}${isLit(g) ? ' lit' : ''}${isStruck(g) ? ' struck' : ''}`}>
                <Tile game={g} name={name(g)} />
                <div className="g">
                  <div className="nm"><span>{name(g)}</span></div>
                  <div className="sub">{agenda.players(g, lg.players)} of {b.members.length} play{games[g]?.ranked === false ? ' · for fun' : ''}</div>
                </div>
                <Switch on={on} label={`${name(g)} on my agenda`} onFlip={() => flip(g)} />
              </div>
            )
          })}
          {ids.length === 0 && <div className="sub wrap">{b.name} has no games yet. add one: it goes on the board for everyone, and on your agenda.</div>}
          <button className="go" onClick={() => go(`/b/${slug}/you/add`)}>
            <span className="k">+ add a game to {b.name}</span><span className="v">{catalogue ? `${catalogue} more on file` : 'it has them all'}</span>
          </button>

          <div className="sec">the board</div>
          {!small && <Invitation b={b} setB={setB} now={now} />}
          <CapTable b={b} limit={3} />
          <button className="go" onClick={() => go(`/b/${slug}/you/register`)}>
            <span className="k">the register</span><span className="v">all {ps.length} {ps.length === 1 ? 'member' : 'members'}</span>
          </button>
          {open.length > 0 && !b.leaving.claimed && (
            <button className="go unissued" onClick={() => go(`/b/${slug}/you/register#seats`)}>
              <span className="k">{open.length} unissued {open.length === 1 ? 'seat' : 'seats'}</span><span className="v">one of them yours?</span>
            </button>
          )}
          <button className="go" onClick={() => go(`/b/${slug}/you/bylaws`)}>
            <span className="k">{b.you.role === 'chair' ? 'amend the bylaws' : 'the bylaws'}</span>
            <span className="v">{b.you.role === 'chair' ? <span className="chip badge">you hold the chair</span> : `${bylawCount(b)} articles`}</span>
          </button>

          {me.kind === 'guest' && <button className="go note" onClick={() => show('everywhere')}><span className="k">you're a guest on this device</span><span className="v">keep your seat</span></button>}
          <button className="go bad" onClick={() => go(`/b/${slug}/you/resign`)}><span className="k">resign from {b.name}</span></button>
        </div>}
      <Nav slug={slug} on="you" />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
    </div>
  )
}

/** Your invitation: a slip with a perforated edge. Words, how long they last, send. */
function Invitation({ b, setB, now }: { b: Board; setB: (b: Board) => void; now: number }) {
  const { toast } = useApp()
  const words = b.invite.code.replace(/-/g, ' ')
  const link = `${location.origin}/join/${b.invite.code}`
  const renew = async () => {
    try { setB(await api.renewInvite(b.slug)); toast('new words. the old ones are void.') } catch (e) { toast((e as Error).message) }
  }
  return (
    <div className="invite-row slip" id="invite">
      <div className="inv-top">
        <span className="inv-k">your invitation</span>
        {b.invite.expires_at && <span className="inv-exp">{left(b.invite.expires_at, now)} left</span>}
      </div>
      <b className="invite-words keep">{words}</b>
      <div className="row-a">
        <button className="btn" onClick={() => sendOn(`join ${b.name} on boredroom: ${link} (or type "${words}" in the app). it works for a day.`, toast)}>send</button>
        <button className="lnk" onClick={renew}>new words</button>
      </div>
    </div>
  )
}

let grown = false  // the share bars grow in once a visit, not on every page

/** The cap table: who's on the board and their share of what's on file here. Tap a column
 *  heading to sort by it, as in a sheet. */
function CapTable({ b, limit, sortable = false }: { b: Board; limit?: number; sortable?: boolean }) {
  const { me } = useApp()
  const [by, setBy] = useState<'share' | 'seat'>(limit ? 'share' : 'seat')
  const [grow] = useState(() => !grown)
  useEffect(() => { grown = true }, [])
  const ps = people(b)
  const seat = new Map(bySeniority(ps).map((m, i) => [m.username, i + 1]))
  const total = b.members.reduce((n, m) => n + m.results, 0)
  const pct = (m: Member) => (total ? Math.round((m.results / total) * 100) : 0)
  const s = (m: Member) => seat.get(m.username) ?? 0
  let rows = [...ps].sort(by === 'share' ? (x, y) => y.results - x.results || s(x) - s(y) : (x, y) => s(x) - s(y))
  if (limit && rows.length > limit) {
    const top = rows.slice(0, limit)
    const you = rows.find(m => m.username === me.username)
    rows = you && !top.includes(you) ? [...top.slice(0, limit - 1), you] : top
  }
  const head = (k: 'share' | 'seat', label: string) => sortable
    ? <button className={by === k ? 'on' : ''} onClick={() => setBy(k)} aria-pressed={by === k}>{label}{by === k ? ' ↓' : ''}</button>
    : <span>{label}</span>
  const held = b.members.filter(m => m.kind === 'placeholder').reduce((n, m) => n + m.results, 0)
  if (ps.length === 1 && !held && limit) return <div className="sub wrap ct-solo">you own 100% of the minutes. invite someone to dilute.</div>
  return <>
    <div className="ct ct-h"><span>member</span>{head('seat', 'seat')}{head('share', 'share of the minutes')}</div>
    {rows.map(m => (
      <div key={m.username} className={`ct${m.username === me.username ? ' me' : ''}`}>
        <span className="who"><Av name={m.nickname} /><span className="nmx">{m.nickname}</span>{m.role === 'chair' && <span className="chip badge">chair</span>}{m.kind === 'guest' && <span className="chip">guest</span>}</span>
        <span className="n">{s(m)}</span>
        <span className="share"><span className={`bar${grow ? ' grow' : ''}`}><i style={{ width: `${pct(m)}%` }} /></span><b>{pct(m)}%</b></span>
      </div>
    ))}
    {held > 0 && limit && (
      <div className="ct unissued-row">
        <span className="who"><span className="av" /><span className="nmx">unissued seats</span></span>
        <span className="n">–</span>
        <span className="share"><span className={`bar${grow ? ' grow' : ''}`}><i style={{ width: `${Math.round((held / total) * 100)}%` }} /></span><b>{Math.round((held / total) * 100)}%</b></span>
      </div>
    )}
  </>
}

const bylawCount = (b: Board) => (unissued(b).length ? 5 : 4)

/** The register: every member by seat, then the seats imported from the chat. */
function Register({ b }: P) {
  const open = unissued(b)
  const total = b.members.reduce((n, m) => n + m.results, 0)
  useEffect(() => { if (location.hash === '#seats') document.getElementById('seats')?.scrollIntoView({ block: 'start' }) }, [])
  return <>
    <Fx fn="register" args={[['board', b.name], ['members', String(people(b).length)]]} />
    <div className="bd page">
      <div className="sec">members <b>{people(b).length}</b> <span className="sec-n">· {total} results on file here</span></div>
      <CapTable b={b} sortable />
      {open.length > 0 && <>
        <div className="sec" id="seats">unissued seats <b>{open.length}</b> <span className="sec-n">· from the chat history, waiting for their owners</span></div>
        {b.leaving.claimed && <div className="sub wrap">you claimed {b.leaving.claimed.nickname}. one seat each, so these wait for someone else.</div>}
        {[...open].sort((x, y) => y.results - x.results).map(p => (
          <div key={p.username} className="it unissued">
            <Av name={p.nickname} />
            <div className="g"><div className="nm">{p.nickname}</div><div className="sub">{p.results} on file · {p.games} {p.games === 1 ? 'game' : 'games'}</div></div>
            {!b.leaving.claimed && <button className="add" onClick={() => go(`/b/${b.slug}/you/claim/${encodeURIComponent(p.username)}`)}>that's me ›</button>}
          </div>
        ))}
      </>}
    </div>
  </>
}

/** The bylaws: what the board is and how it runs, as numbered articles. Everyone can read
 *  them; the chair's copy has the pen. */
function Bylaws({ b, setB }: P) {
  const { me, games, refreshMe, toast } = useApp()
  const [name, setName] = useState<string | null>(null)
  const chairing = b.you.role === 'chair'
  const ps = people(b)
  const chair = b.members.find(m => m.role === 'chair')  // can be a seat imported from the chat, until it's claimed
  const heir = bySeniority(ps).find(m => m.role !== 'chair')
  const open = unissued(b)
  const rename = async () => {
    const v = (name ?? '').trim().toLowerCase()
    if (!v || v === b.name) { setName(null); return }
    try { setB(await api.rename(b.slug, v)); refreshMe(); setName(null); toast(`the board is ${v} now. links still work.`) } catch (e) { toast((e as Error).message) }
  }
  const gname = (g: string, fallback: string) => games[g]?.name ?? fallback
  return <>
    {name !== null
      ? <FxEdit fn="bylaws" field="name" value={name} onChange={setName} onSave={rename} onCancel={() => setName(null)} ok={!!name.trim()} max={60}
          note={{ text: 'article 1. links to the board keep working.', tone: 'idle' }} />
      : <Fx fn="bylaws" args={[['board', b.name]]} />}
    <div className="bd page">
      <div className="art">
        <span className="art-n">article 1</span>
        <p>the board shall be known as <b>{b.name}</b>.</p>
        {chairing && <button className="lnk amend" onClick={() => setName(b.name)}>amend ✎</button>}
      </div>
      <div className="art">
        <span className="art-n">article 2</span>
        <p>the board keeps <b>{b.library.length}</b> {b.library.length === 1 ? 'game' : 'games'}; each member puts the ones they play on their own agenda. any member may add a game to the board. whoever added one may take it off again until someone else plays it; the chair may take off any.</p>
      </div>
      {[...b.library].sort((x, y) => gname(x.game, x.name).localeCompare(gname(y.game, y.name))).map(g => (
        <div key={g.game} className="it game sub-art compact">
          <Tile game={g.game} name={gname(g.game, g.name)} />
          <div className="g"><div className="nm">{gname(g.game, g.name)} <small className="muted">{g.players} play{games[g.game]?.ranked === false ? ' · for fun' : ''}</small></div></div>
          {g.removable && <button className="add strike" onClick={() => go(`/b/${b.slug}/you/strike/${encodeURIComponent(g.game)}`)}>take off ›</button>}
        </div>
      ))}
      <div className="art">
        <span className="art-n">article 3</span>
        <p>each member holds one invitation, good for a day. new words void the old.</p>
        {chairing && <button className="lnk amend bad" onClick={() => go(`/b/${b.slug}/you/retire`)}>retire every invitation ›</button>}
      </div>
      <div className="art">
        <span className="art-n">article 4</span>
        <p>the chair is held by <b>{chair?.username === me.username ? 'you' : chair?.nickname ?? 'no one'}</b>{chair?.kind === 'placeholder' ? ', an unissued seat' : ''}.{heir && <> should the chair resign, it passes to the longest-serving member: <b>{heir.username === me.username ? 'you' : heir.nickname}</b>.</>}</p>
      </div>
      {open.length > 0 && (
        <div className="art">
          <span className="art-n">article 5</span>
          <p>seats imported from the chat wait for their owners: <b>{open.length}</b>. each member may claim one.</p>
          <button className="lnk amend" onClick={() => go(`/b/${b.slug}/you/register#seats`)}>see the seats ›</button>
        </div>
      )}
      <div className="sub wrap">{chairing ? 'you hold the chair: amend, or take games off, above.' : 'only the chair amends the bylaws.'}</div>
    </div>
  </>
}

/** Adding a game to the board: the whole catalogue, searched in the formula bar. Adding one
 *  puts it on the board for everyone and on your agenda; whoever adds it can take it back. */
function AddGame({ b, setB }: P) {
  const { games, toast } = useApp()
  const [q, setQ] = useState('')
  const [isLit, light] = useMark()
  const [busy, setBusy] = useState('')
  const agenda = useAgenda(b.slug, b, setB)
  const el = useRef<HTMLInputElement>(null)
  const [order] = useState(() => Object.values(games).sort((x, y) => x.name.localeCompare(y.name)).map(g => g.id))
  useEffect(() => { if (matchMedia('(pointer: fine)').matches) el.current?.focus() }, [])
  const lib = new Map(b.library.map(g => [g.game, g]))
  const name = (g: string) => games[g]?.name ?? g
  const term = q.trim().toLowerCase()
  const found = order.filter(g => !term || name(g).toLowerCase().includes(term) || g.includes(term))
  // which list a game sits in is decided when the page opens, so adding one doesn't move it
  const [onAtOpen] = useState(() => new Set(b.library.map(g => g.game)))
  const fresh = found.filter(g => !onAtOpen.has(g)), standing = found.filter(g => onAtOpen.has(g))
  const row = (g: string) => {
    const lg = lib.get(g)
    return (
      <div key={g} className={`it game${lg && !agenda.on(g) ? ' off' : ''}${isLit(g) ? ' lit' : ''}`}>
        <Tile game={g} name={name(g)} />
        <div className="g">
          <div className="nm">{name(g)}</div>
          <div className="sub">{lg ? `${agenda.players(g, lg.players)} play it here` : games[g]?.ranked === false ? 'for fun' : 'ranked'}</div>
        </div>
        {lg ? <Switch on={agenda.on(g)} label={`${name(g)} on my agenda`} onFlip={() => { buzz(); agenda.flip(g, name(g)) }} />
          : <button className="btn sm" disabled={busy === g} onClick={() => add(g)}>add</button>}
      </div>
    )
  }
  const add = async (g: string) => {
    setBusy(g); buzz()
    try {
      setB(await api.agenda(b.slug, g, true)); light(g)
      toast(`${name(g)} is on ${b.name} now, and on your agenda.`, {
        label: 'undo', run: () => { api.dropGame(b.slug, g).then(setB).then(() => toast(`${name(g)} is off ${b.name} again.`)).catch(e => toast((e as Error).message)) },
      })
    } catch (e) { toast((e as Error).message) } finally { setBusy('') }
  }
  return <>
    <div className="fx fxe keep">
      <i>fx</i><span>=find(game:"</span>
      <input ref={el} className="fxe-in" value={q} onChange={e => setQ(e.target.value)} placeholder="type to search" aria-label="find a game"
        autoCapitalize="none" autoComplete="off" spellCheck={false} />
      <span>")</span>
      {q && <button className="fxe-b" onClick={() => { setQ(''); el.current?.focus() }} aria-label="clear">✕</button>}
    </div>
    <div className="bd page">
      {fresh.length > 0 && <div className="sec">not on {b.name} yet <b>{fresh.length}</b> <span className="sec-n">· add puts it on the board for everyone, and on your agenda</span></div>}
      {!term && fresh.length === 0 && <div className="sub wrap">{b.name} already has every game on file. know one we don't read? paste a result on the agenda and the clerk will ask for it.</div>}
      {fresh.map(row)}
      {standing.length > 0 && <div className="sec">already on {b.name} <b>{standing.length}</b> <span className="sec-n">· the switch is your agenda</span></div>}
      {standing.map(row)}
      {found.length === 0 && <div className="sub wrap">nothing called "{term}" on file. paste one of its results on the agenda and the clerk will ask for it.</div>}
    </div>
  </>
}

/** "That's me": taking over a seat imported from the chat. */
function Claim({ b, setB, back, arg }: P) {
  const { refreshMe, toast } = useApp()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const p = unissued(b).find(m => m.username === arg)
  const yes = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api.claim(b.slug, arg)
      setB(r.board); refreshMe(); buzz()
      toast(`welcome back. ${r.moved} results are yours now.`)
      go(`/b/${b.slug}/you?stamp=claimed`, true)
    } catch (e) { setErr((e as Error).message); setBusy(false) }
  }
  if (!p || b.leaving.claimed) return <div className="bd page"><div className="sub wrap">{b.leaving.claimed ? `you've claimed ${b.leaving.claimed.nickname} already. one seat each.` : 'that seat has been claimed.'}</div></div>
  return (
    <div className="bd page">
      <Motion heading={`motion to claim ${p.nickname}`} yes={busy ? 'claiming…' : "yes, that's me"} no="no" busy={busy} err={err} onYes={yes} onNo={() => goBack(back)}>
        <p>the {p.results} {p.results === 1 ? 'result' : 'results'} imported from the chat as <b>{p.nickname}</b> become yours, on {b.name} and wherever else you play those games.</p>
        <p>the seat closes. you keep your own name here, {b.you.nickname}.</p>
        <p className="muted">one seat each, so claim only your own. resigning later puts it back.</p>
      </Motion>
    </div>
  )
}

/** Taking a game off the board. */
function Strike({ b, setB, back, arg }: P) {
  const { games, toast } = useApp()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const g = b.library.find(x => x.game === arg)
  const nm = games[arg]?.name ?? g?.name ?? arg
  const yes = async () => {
    setBusy(true); setErr('')
    try { setB(await api.dropGame(b.slug, arg)); toast(`${nm} is off ${b.name}.`); go(back, true) }
    catch (e) { setErr((e as Error).message); setBusy(false) }
  }
  if (!g) return <div className="bd page"><div className="sub wrap">{nm} isn't on {b.name}.</div></div>
  return (
    <div className="bd page">
      <Motion heading={`motion to take ${nm} off ${b.name}`} yes={busy ? 'taking it off…' : 'yes, take it off'} no="no" busy={busy} err={err} onYes={yes} onNo={() => goBack(back)}>
        <p>{nm} comes off the board{g.players ? `, and off the agenda of the ${g.players} ${g.players === 1 ? 'member who plays' : 'members who play'} it` : ''}.</p>
        <p>results already filed stay in the minutes. anyone can add it back.</p>
      </Motion>
    </div>
  )
}

/** Retiring every invitation that's out there. */
function Retire({ b, setB, back }: P) {
  const { toast } = useApp()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const yes = async () => {
    setBusy(true); setErr('')
    try { setB((await api.retireInvites(b.slug)).board); toast('every old invitation is void. members have new words.'); go(back, true) }
    catch (e) { setErr((e as Error).message); setBusy(false) }
  }
  return (
    <div className="bd page">
      <Motion heading="motion to retire every invitation" yes={busy ? 'retiring…' : 'yes, retire them all'} no="no" busy={busy} err={err} onYes={yes} onNo={() => goBack(back)}>
        <p>for when a link ended up somewhere it shouldn't. everyone's words stop working, yours too, and each member gets new ones.</p>
        <p className="muted">nobody already on {b.name} is affected.</p>
      </Motion>
    </div>
  )
}

/** A letter of resignation: what goes where, signed by holding. */
function Resign({ b, back }: P) {
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
      toast(r.closed ? `${b.name} has been wound up.` : `you've resigned from ${b.name}. your absence is noted in the minutes.`)
      go(next ? `/b/${next.slug}` : '/desk', true)
    } catch (e) { setErr((e as Error).message); setBusy(false) }
  }
  return (
    <div className="bd page">
      <Motion heading={`motion to resign from ${b.name}`} sign yes={`resign as ${b.you.nickname}`} no="no, stay" busy={busy} err={err} onYes={leave} onNo={() => goBack(back)}
        foot={<button className="lnk" onClick={() => go(`/b/${b.slug}/you/close`, true)}>leaving everything? wind up your account instead ›</button>}>
        <p>your seat and your agenda here go. what you filed stays yours, on your other boards, and stops showing on {b.name}.</p>
        {l.claimed && <p>the {l.claimed.results} {l.claimed.results === 1 ? 'result' : 'results'} imported from the chat go back to an unissued seat called <b>{l.claimed.nickname}</b>, so it can be claimed again.</p>}
        {l.alone
          ? <p>you're the only member. resigning dissolves {b.name} and its minutes, for good.</p>
          : l.chair && l.heir && <p>you hold the chair. it passes to <b>{l.heir}</b>, the longest-serving member.</p>}
        <p className="muted">you can come back with an invitation.</p>
      </Motion>
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, type Board, type Filing, type Item, type Memo, type Minutes, type Today } from '../api'
import { hold, unhold, type Held } from '../outbox'
import { headline, left } from '../format'
import { go } from '../router'
import { Av, Clip, Fx, FxQuery, Ghost, Header, Nav, Overlay, Tile, Trouble, Who, Whos, sendOn, useApp, useFresh, useNow, type Token } from '../ui'
import Boards from './Boards'
import { InstallMemo } from '../install'
import { NewsMemo } from '../news'
import { playLink } from '../opens'
import { MemoRow } from '../memos'
import { orderOptions, readSort, sortOptions, sorted, writeSort, type Sort, type SortBy } from '../sort'

const TODO = 8  // open games shown before "n more"
const playUrl = (i: Item) => i.play
const unit = (i: Item) => (i.weekly ? 'week' : 'day')  // a weekly game's tenure counts weeks
const DAY = 86400000
const AWAY = 'boredroom.away'  // the game you left to play, so the agenda can greet you when you're back
type Away = { game: string; name: string; at: number }
const readAway = (): Away | null => { try { return JSON.parse(sessionStorage.getItem(AWAY) ?? 'null') } catch { return null } }
const writeAway = (a: Away | null) => { try { if (a) sessionStorage.setItem(AWAY, JSON.stringify(a)); else sessionStorage.removeItem(AWAY) } catch { /* private window */ } }

export default function Agenda({ slug, shared }: { slug: string; shared?: string }) {
  const { games, toast, me, refreshMe } = useApp()
  const [today, setToday] = useState<Today | null>(null)
  const [board, setBoard] = useState<Board | null>(null)
  const [err, setErr] = useState('')
  const [picker, setPicker] = useState(false)
  const [pickTab, setTab] = useState<'open' | 'filed' | null>(null)
  const [all, setAll] = useState(false)
  // your account's order (see sort.ts); a pick shows at once and holds until the account has it
  const [picked, setPicked] = useState<Sort | null>(null)
  const sort = picked ?? readSort(me.agenda_sort)
  const setSort = (x: Sort) => {
    setPicked(x)
    setAll(false)
    api.updateMe({ agenda_sort: writeSort(x) }).then(refreshMe).then(() => setPicked(null))
      .catch(() => toast("the order didn't save. it holds here for now."))
  }
  const [fresh, setFresh] = useState<Set<string>>(new Set())  // just filed: the rows flash once
  const [peek, setPeek] = useState<string | null>(null)  // the row opened in place
  const [hidden, setHidden] = useState(false)  // the skipped games, opened from their strip
  const [away, setAwayState] = useState<Away | null>(readAway)
  const [back, setBack] = useState(() => !!readAway())  // came back from playing: the pasteboard asks for the result
  const now = useNow()
  const setAway = (a: Away | null) => { writeAway(a); setAwayState(a); if (!a) setBack(false) }
  // an hour old, or already filed: stop asking
  useEffect(() => {
    if (away && (now - away.at > 3600000 || today?.items.some(i => i.game === away.game && i.filed))) setAway(null)
  }, [away, now, today])
  useEffect(() => {
    const on = () => { if (document.visibilityState === 'visible' && readAway()) setBack(true) }
    document.addEventListener('visibilitychange', on)
    window.addEventListener('focus', on)
    return () => { document.removeEventListener('visibilitychange', on); window.removeEventListener('focus', on) }
  }, [])

  const load = useCallback(() => {
    api.today(slug).then(t => { setToday(t); setErr('') }).catch(e => setErr(e.message))
    api.board(slug).then(setBoard).catch(() => {})
  }, [slug])
  useEffect(load, [load])
  useFresh(load)
  const filedNow = (gs: string[]) => {
    load()
    if (away && gs.includes(away.game)) setAway(null)
    setFresh(new Set(gs))
    setTimeout(() => setFresh(new Set()), 1400)
  }

  if (err) return (
    <div className="app">
      <Header title="boredroom.xlsx" />
      <Trouble err={err} retry={load} />
      <Nav slug={slug} on="agenda" />
    </div>
  )
  if (!today || !board) return (
    <div className="app">
      <Header title={`${board?.name ?? slug}.xlsx`} meta="agenda" />
      <Fx fn="agenda" args={[['board', board?.name ?? slug], ['puzzles', 'current']]} />
      <Ghost what="the agenda" />
      <Nav slug={slug} on="agenda" />
    </div>
  )

  const items = sorted(today.items, sort)
  const open = items.filter(i => !i.filed && !i.skipped), filed = items.filter(i => i.filed), skipped = items.filter(i => i.skipped)
  const tab = pickTab ?? (open.length || !filed.length || skipped.length ? 'open' : 'filed')
  const extra = board.library.filter(g => !board.you.agenda.includes(g.game)).length
  const placeholders = board.members.filter(m => m.kind === 'placeholder')
  const toggle = (g: string) => setPeek(p => (p === g ? null : g))
  // sitting a game out: off the to-do list until it resets, on every board; undo puts it back
  const skip = async (i: Item, on: boolean) => {
    setPeek(null)
    setToday(t => t && { ...t, items: t.items.map(x => x.game === i.game ? { ...x, skipped: on } : x) })
    try {
      setToday(await api.skip(slug, i.game, on))
      if (on) toast(`skipped ${i.name} till it resets.`, { label: 'undo', run: () => skip(i, false) })
      else toast(`${i.name} is back on the agenda.`)
    } catch (e) { load(); toast((e as Error).message) }
  }

  return (
    <div className="app">
      <Header title={`${board.name}.xlsx`} meta="agenda" onTitle={() => setPicker(true)} />
      <FxQuery fn="agenda" tokens={tokens(slug, me.boards, sort, setSort)} />
      <div className="bd">
        <Pasteboard board={board} shared={shared} onFiled={filedNow} back={back ? away : null} onBackDone={() => setAway(null)} />
        <NewsMemo />
        <InstallMemo onDone={ok => ok && toast('installed. see you on the home screen.')} />
        {placeholders.length > 0 && !board.you.claimed && (
          <button className="more" onClick={() => go(`/b/${slug}/you/register#seats`)}>
            {placeholders.length} imported seats unclaimed · is one of them yours? →
          </button>
        )}
        {today.items.length > 0 && (
          <div className="tabs" role="tablist" aria-label="today">
            <button role="tab" aria-selected={tab === 'open'} className={tab === 'open' ? 'on' : ''} onClick={() => setTab('open')}>to do <b>{open.length}</b></button>
            <button role="tab" aria-selected={tab === 'filed'} className={tab === 'filed' ? 'on' : ''} onClick={() => setTab('filed')}>filed <b>{filed.length}</b></button>
            <button className="tab-lib" onClick={() => go(`/b/${slug}/you#games`)}>{extra ? `${extra} more on ${board.name} →` : 'your agenda →'}</button>
          </div>
        )}
        {tab === 'open' && <>
          {open.length === 0 && today.items.length > 0 && <div className="sub wrap">
            {skipped.length ? <>nothing left to do: {filed.length} filed, {skipped.length} skipped till reset.</> : <>all {filed.length} filed. the board thanks you.</>}
          </div>}
          {(all || open.length <= TODO + 1 ? open : open.slice(0, TODO)).map(i => <OpenRow key={i.game} i={i} slug={slug} now={now} lit={fresh.has(i.game)}
            open={peek === i.game} onToggle={() => toggle(i.game)}
            playing={away?.game === i.game} onPlay={() => setAway({ game: i.game, name: i.name, at: Date.now() })} by={sort.by}
            onSkip={() => skip(i, true)} />)}
          {!all && open.length > TODO + 1 && <button className="more" onClick={() => setAll(true)}>{open.length - TODO} more to do ↓</button>}
          {skipped.length > 0 && (
            // like a spreadsheet's hidden rows: the numbers jump, and a thin strip says what's tucked away
            <button className="hid" style={{ counterIncrement: `r ${skipped.length}` }} aria-haspopup="dialog" onClick={() => setHidden(true)}>
              <span>{skipped.length} skipped till reset · {skipped.map(i => i.name).join(', ')}</span><span className="hid-a">show</span>
            </button>
          )}
        </>}
        {tab === 'filed' && <>
          {filed.length === 0 && <div className="sub wrap">nothing filed yet today. paste a result above.</div>}
          {filed.map(i => (
            <div key={i.game} className={`row${peek === i.game ? ' open' : ''}`}>
            <div className={`it${fresh.has(i.game) ? ' lit' : ''}`} role="button" tabIndex={0} aria-expanded={peek === i.game}
              onClick={() => toggle(i.game)} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle(i.game))}>
              <Tile game={i.game} name={i.name} />
              <div className="g">
                <div className="nm">{i.name} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>{i.mine?.puzzle}</span></div>
                <div className="sub">
                  {i.mine && headline(games[i.game], i.mine.metrics, i.mine.outcome)}
                  {i.mine?.late && <span className="stamp">filed late</span>}
                  <span>· {i.present}/{i.players} present</span>
                  {i.tenure.days >= 2 && <span className="tenure">· {i.tenure.days}-{unit(i)} tenure</span>}
                  <By i={i} by={sort.by} />
                </div>
              </div>
              <div className="pr">
                <span className="pill done">{i.ranked && i.place ? `#${i.place}` : '✓'}</span>
                <span className="rs">resets in {left(i.resets_at, now)}</span>
                <span className="pr-a">
                  {i.mine?.forward && <button className="lnk" onClick={e => { e.stopPropagation(); sendOn(i.mine!.forward!, toast) }}>send on</button>}
                  {i.play && <SiteLink i={i} />}
                </span>
              </div>
            </div>
            {peek === i.game && <Peek slug={slug} i={i} />}
            </div>
          ))}
        </>}
        <Memos slug={slug} memos={today.memos} onChange={memos => setToday(t => t && { ...t, memos })} />
        {today.items.length === 0 && <div className="sub wrap">nothing on your agenda yet. pick your games, or just paste a result: its game joins your agenda.</div>}
        {today.items.length === 0 && <button className="more" onClick={() => go(`/b/${slug}/you#games`)}>{extra ? `${extra} of ${board.name}'s games aren't on your agenda →` : 'your agenda →'}</button>}
      </div>
      <Nav slug={slug} on="agenda" />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
      {hidden && skipped.length > 0 && <Skipped items={skipped} now={now} onClose={() => setHidden(false)}
        onBack={i => { if (skipped.length === 1) setHidden(false); skip(i, false) }} onPlay={i => setAway({ game: i.game, name: i.name, at: Date.now() })} />}
    </div>
  )
}

/** Memos from the chair: the day's big news, two at most; the rest is in the memos tab. */
function Memos({ slug, memos, onChange }: { slug: string; memos: Memo[]; onChange: (m: Memo[]) => void }) {
  const { games, toast } = useApp()
  if (!memos.length) return null
  const dismiss = async (m: Memo) => {
    onChange(memos.filter(x => x.id !== m.id))
    try {
      await api.dismissMemo(slug, m.id, true)
      toast('noted.', { label: 'undo', run: () => api.dismissMemo(slug, m.id, false).then(r => { onChange(r.memos); toast('back on the record.') }).catch(() => {}) })
    } catch (e) { onChange(memos); toast((e as Error).message) }
  }
  return (
    <div className="memos">
      <div className="ph-sec"><span>memos from the chair</span><button className="lnk" onClick={() => go(`/b/${slug}/meeting`)}>the daily bored meeting →</button></div>
      {memos.map(m => <MemoRow key={m.id} m={m} game={m.game ? games[m.game] : undefined} onDismiss={() => dismiss(m)} />)}
    </div>
  )
}

/** The formula bar as the agenda's controls: which board, and the order of its games. */
function tokens(slug: string, boards: { slug: string; name: string }[], sort: Sort, set: (s: Sort) => void): Token[] {
  return [
    { key: 'board', value: slug, options: boards.map(b => [b.slug, b.name]), onPick: s => go(`/b/${s}`) },
    { key: 'sort', value: sort.by, options: sortOptions, onPick: by => set({ by: by as SortBy, order: 'first' }) },
    ...(sort.by === 'usual' ? [] : [{ key: 'order', value: sort.order, options: orderOptions(sort.by), onPick: (o: string) => set({ ...sort, order: o as Sort['order'] }) }]),
  ]
}

/** What a row is sorted by, when the row doesn't already say it. */
function By({ i, by }: { i: Item; by: SortBy }) {
  const t = by === 'mine' ? (i.results ? `${i.results} filed by you` : 'new to you')
    : by === 'popular' ? (i.board_month ? `${i.board_month} this month` : 'quiet this month')
      : by === 'tenure' && i.tenure.days >= 2 && !i.filed && !i.tenure.at_risk ? `${i.tenure.days}-${unit(i)} tenure` : null
  return t ? <span className="by"> · {t}</span> : null
}

/** A filed game's own site, for its archive, stats or tomorrow's teaser. */
function SiteLink({ i }: { i: Item }) {
  const link = playLink(i.play!)
  return (
    <a className="lnk" href={link.href} target={link.newTab ? '_blank' : undefined} rel="noreferrer"
      aria-label={`open ${i.name}'s site`} onClick={e => e.stopPropagation()}>site ↗</a>
  )
}

/** The skipped games, from their strip: when each comes back, and the ways to have it sooner. */
function Skipped({ items, now, onClose, onBack, onPlay }:
  { items: Item[]; now: number; onClose: () => void; onBack: (i: Item) => void; onPlay: (i: Item) => void }) {
  return (
    <Overlay title="skipped till reset" onClose={onClose}>
      <div className="skip-m">
        <p>these are off your agenda on every board until each one resets, then they're back as usual. nothing for you to do.</p>
        <p className="sub">changed your mind? put one back, or just play it: filing a result ends the skip.</p>
      </div>
      {items.map(i => {
        const link = i.play ? playLink(i.play) : null
        return (
          <div key={i.game} className="skip-r">
            <Tile game={i.game} name={i.name} />
            <div className="g">
              <div className="nm">{i.name}</div>
              <div className="sub">back in {left(i.resets_at, now)}</div>
              {i.tenure.at_risk && i.tenure.days >= 2 && <div className="risk-l">your {i.tenure.days}-{unit(i)} tenure still lapses at reset</div>}
            </div>
            <div className="row-a">
              {link && <a className="lnk" href={link.href} target={link.newTab ? '_blank' : undefined} rel="noreferrer" onClick={() => onPlay(i)}>play ↗</a>}
              <button className="btn" onClick={() => onBack(i)}>put back</button>
            </div>
          </div>
        )
      })}
      <div className="skip-m"><button className="lnk" onClick={onClose}>leave them skipped</button></div>
    </Overlay>
  )
}

function OpenRow({ i, slug, now, lit, open, onToggle, playing, onPlay, by, onSkip }:
  { i: Item; slug: string; now: number; lit: boolean; open: boolean; onToggle: () => void; playing: boolean; onPlay: () => void; by: SortBy; onSkip: () => void }) {
  const { games } = useApp()
  const url = playUrl(i)
  const link = url ? playLink(url) : null
  const ms = new Date(i.resets_at).getTime() - now
  const urg = ms < 3600000
  return (
    <div className={`row${open ? ' open' : ''}`}>
      <div className={`it${lit ? ' lit' : ''}`} role="button" tabIndex={0} aria-expanded={open}
        onClick={onToggle} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onToggle())}>
        <Tile game={i.game} name={i.name} />
        <div className="g">
          <div className="nm">{i.name} {i.puzzle && <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>{i.puzzle}</span>}</div>
          <div className="sub">
            {i.present === 0 ? <>no one yet · be first<By i={i} by={by} /></> : <>
              <span className="stack">{i.filed_by.slice(0, 4).map(n => <Av key={n} name={n} />)}</span>
              {i.present}/{i.players} present
              {i.leader && <> · {i.leader.nickname ? <Who slug={slug} name={i.leader.nickname} /> : `${i.leader.tied} tied`} {headline(games[i.game], i.leader.metrics)}</>}
              <By i={i} by={by} />
            </>}
          </div>
          {i.tenure.at_risk && i.tenure.days >= 2 && <div className="risk-l">your {i.tenure.days}-{unit(i)} tenure lapses at reset</div>}
        </div>
        <div className="pr">
          {link
            ? <a className={`play${urg ? ' urg' : ''}${playing ? ' away' : ''}`} href={link.href} target={link.newTab ? '_blank' : undefined} rel="noreferrer"
                style={{ ['--left' as string]: Math.max(0, Math.min(1, ms / (i.weekly ? 7 * DAY : DAY))) }}
                aria-label={`play ${i.name}, ${left(i.resets_at, now)} left`}
                onClick={e => { e.stopPropagation(); onPlay() }}>
                <span className="play-i" aria-hidden="true">{playing ? '' : '▶'}</span>{playing ? 'playing' : 'play'}<span className="play-x" aria-hidden="true">↗</span>
              </a>
            : <span className="pill todo">open</span>}
          <span className={`rs${urg ? ' urg' : ''}`}>{left(i.resets_at, now)} left</span>
        </div>
      </div>
      {open && <Peek slug={slug} i={i} onSkip={onSkip} />}
    </div>
  )
}

/** A row opened in place: today's standings at a glance, without leaving the agenda. */
function Peek({ slug, i, onSkip }: { slug: string; i: Item; onSkip?: () => void }) {
  const { games } = useApp()
  const [m, setM] = useState<Minutes | null>(null)
  const [err, setErr] = useState(false)
  useEffect(() => { api.minutes(slug, i.game).then(setM).catch(() => setErr(true)) }, [slug, i.game])
  const rows = m?.rows ?? []
  const top = rows.slice(0, 5), me = rows.find(r => r.me)
  const showMe = me && !top.includes(me)
  return (
    <div className="peek">
      {err && <div className="sub wrap">couldn't fetch the minutes.</div>}
      {!m && !err && <div className="peek-l">{[0, 1, 2].map(k => <div key={k} className="peek-r ghost"><span /><span /><span /></div>)}</div>}
      {m && rows.length === 0 && <div className="sub wrap">no one has filed {i.name} today. the floor is yours.</div>}
      {m && rows.length > 0 && (
        <div className="peek-l" role="table" aria-label={`${i.name} today`}>
          {[...top, ...(showMe ? [me] : [])].map((r, k) => (
            <div key={r.id ?? `${r.nickname}${k}`} className={`peek-r${r.me ? ' me' : ''}${showMe && r === me ? ' gap' : ''}`} role="row">
              <span className="peek-p">{m.ranked && r.place ? r.place : '·'}</span>
              <span className="peek-n"><Who slug={slug} name={r.nickname} av />{r.me && <em>you</em>}</span>
              <span className="peek-s">{headline(games[i.game], r.metrics, r.outcome)}</span>
            </div>
          ))}
        </div>
      )}
      <div className="peek-f">
        {m && m.not_in.length > 0 && <span className="sub">not in yet: <Whos slug={slug} names={m.not_in.slice(0, 4)} />{m.not_in.length > 4 ? ` +${m.not_in.length - 4}` : ''}</span>}
        <span className="peek-b">
          {onSkip && <button className="lnk" onClick={onSkip}>skip till reset</button>}
          <button className="more" onClick={() => go(`/b/${slug}/m/${i.game}`)}>the full minutes →</button>
        </span>
      </div>
    </div>
  )
}

/** The pasteboard: paste a share text, see what the clerk read, then save it or dismiss it.
 *  Saving files it everywhere; the cards then say what happened. */
export function Pasteboard({ board, shared, onFiled, back, onBackDone }:
  { board?: Board; shared?: string; onFiled: (games: string[]) => void; back?: { game: string; name: string } | null; onBackDone?: () => void }) {
  const { games, refreshMe } = useApp()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<{ text: string; source: 'paste' | 'share'; read: Filing } | null>(null)
  const [out, setOut] = useState<Filing | null>(null)
  const [err, setErr] = useState('')
  const [answered, setAnswered] = useState<Record<number, string>>({})
  const [held, setHeld] = useState<Held | null>(null)  // pasted while the server was out of reach
  const [shake, setShake] = useState(false)  // nothing readable: the pasteboard shakes its head
  const ta = useRef<HTMLTextAreaElement>(null)
  const sharedDone = useRef(false)

  const read = useCallback(async (t: string, source: 'paste' | 'share' = 'paste') => {
    if (!t.trim()) return
    setBusy(true); setErr(''); setOut(null); setAnswered({}); setHeld(null)
    try {
      const r = await api.preview(t)
      setDraft({ text: t, source, read: r }); setText('')
      if (!r.events.length && !r.unknown.length) { setShake(true); navigator.vibrate?.([10, 40, 10]); setTimeout(() => setShake(false), 400) }
    }
    catch (e) { if (e instanceof ApiError && e.away) { setHeld(hold(t, source)); setText('') } else setErr((e as Error).message) }
    finally { setBusy(false) }
  }, [])

  const save = async () => {
    if (!draft) return
    setBusy(true); setErr('')
    try {
      const f = await api.paste(draft.text, draft.source)
      setOut(f); setDraft(null)
      // a new game joins your agenda on this board, as "+ add a game" does
      const add = board ? f.events.filter(e => e.kind !== 'not_out_yet' && !board.you.agenda.includes(e.game)).map(e => e.game) : []
      for (const g of new Set(add)) await api.agenda(board!.slug, g, true).catch(() => {})
      if (add.length) refreshMe()
      onFiled(f.events.filter(e => e.kind === 'filed' || e.kind === 'merged').map(e => e.game))
    } catch (e) {
      if (e instanceof ApiError && e.away) { setHeld(hold(draft.text, draft.source)); setDraft(null) } else setErr((e as Error).message)
    } finally { setBusy(false) }
  }

  useEffect(() => {
    if (shared && !sharedDone.current) { sharedDone.current = true; read(shared, 'share'); history.replaceState(null, '', board ? `/b/${board.slug}` : '/desk') }
  }, [shared, read, board])

  const name = (g: string) => games[g]?.name ?? g
  const replace = async (rid: number, paste: number) => {
    try { await api.replace(rid, paste); setAnswered(a => ({ ...a, [rid]: 'replaced. stamped "amended".' })); onFiled([]) }
    catch (e) { setErr((e as Error).message) }
  }
  const minutes = (g: string) => board && <button className="lnk" style={{ fontSize: 12, alignSelf: 'flex-start' }} onClick={() => go(`/b/${board.slug}/m/${g}`)}>see how {board.name} did →</button>
  const worth = draft && (draft.read.unknown.length > 0 || draft.read.events.some(e => e.kind === 'filed' || e.kind === 'merged' || e.kind === 'conflict'))

  return (
    <div className={`pbw${shake ? ' shake' : ''}`}>
      {!draft && <>
        <label className={`pb${back && !out ? ' ask' : ''}`}>
          <Clip />
          <textarea ref={ta} rows={text.includes('\n') ? Math.min(8, text.split('\n').length) : 1} placeholder={back && !out ? `paste your ${back.name} result` : 'paste a result'} aria-label="paste a result"
            spellCheck={false} value={text} disabled={busy} className="keep"
            onChange={e => setText(e.target.value)}
            onPaste={e => { const t = e.clipboardData.getData('text'); if (t.trim()) { e.preventDefault(); read(t) } }} />
        </label>
        {text.trim() && <div className="pb-a"><button className="btn" onClick={() => read(text)} disabled={busy}>read it</button><button className="lnk" onClick={() => setText('')}>clear</button></div>}
        {!text && back && !out && (
          <div className="pb-a back" role="status">
            <span>back from <b>{back.name}</b>?</span>
            {navigator.clipboard?.readText && <button className="pill todo" onClick={async () => { try { read(await navigator.clipboard.readText()) } catch { ta.current?.focus() } }}>paste it</button>}
            <button className="lnk" onClick={onBackDone} aria-label="not now">not now</button>
          </div>
        )}
        {!text && !back && navigator.clipboard?.readText && !out && (
          <div className="pb-a"><button className="lnk" onClick={async () => { try { read(await navigator.clipboard.readText()) } catch { ta.current?.focus() } }}>paste from clipboard</button></div>
        )}
      </>}
      {err && <div className="err">{err}</div>}
      {held && (
        <div className="cards" style={{ marginTop: 8 }}>
          <div className="card quiet">
            <b>held on this phone</b>
            <small>boredroom can't be reached right now. it'll be read and filed by itself once it can, timed from now.</small>
            <div className="row-a"><button className="lnk" onClick={() => { unhold(held.id); setHeld(null) }}>don't send it</button>
              <button className="lnk" onClick={() => setHeld(null)}>ok</button></div>
          </div>
        </div>
      )}

      {draft && (
        <div className="cards">
          <div className="pb-h">the clerk read</div>
          {draft.read.events.map((e, k) => (
            <div className={`card${e.kind === 'filed' || e.kind === 'merged' ? '' : ' quiet'}`} key={k}>
              {e.kind === 'filed' && <><b>{name(e.game)} {e.puzzle}{e.metrics && Object.keys(e.metrics).length ? ` · ${headline(games[e.game], e.metrics, e.outcome ?? undefined)}` : e.outcome === 'failed' ? ' · failed' : ''}</b>
                <small>{e.late ? 'late · ' : ''}{e.confidence !== 'exact' ? `read as ${e.confidence} · ` : ''}new</small></>}
              {e.kind === 'merged' && <><b>more detail for {name(e.game)} {e.puzzle}</b><small>adds the {e.added.join(', ')}. the score stays.</small></>}
              {e.kind === 'duplicate' && <><b>{name(e.game)} {e.puzzle} is already in the minutes</b><small>nothing new here.</small></>}
              {e.kind === 'not_out_yet' && <><b>{name(e.game)} {e.puzzle} isn't out yet</b><small>file it once it's the current puzzle.</small></>}
              {e.kind === 'conflict' && <><b>{name(e.game)} {e.puzzle} is already filed, with a different result</b><small>save, and you'll pick which one to keep.</small></>}
            </div>
          ))}
          {draft.read.unknown.map((u, k) => (
            <div className="card quiet" key={`u${k}`}><b>we can't read {u.name} yet</b><small>{u.score ? `${u.score} · ` : ''}saving asks the clerk for a parser.</small></div>
          ))}
          {!draft.read.events.length && !draft.read.unknown.length && <div className="card quiet"><b>nothing readable in that</b><small>{draft.read.note || 'paste the share text the game gives you.'}</small></div>}
          <div className="row-a">
            {worth && <button className="btn" onClick={save} disabled={busy}>save to the minutes</button>}
            <button className={worth ? 'lnk' : 'btn ghost'} onClick={() => setDraft(null)} disabled={busy}>{worth ? 'dismiss' : 'ok'}</button>
          </div>
        </div>
      )}

      {out && (
        <div className="cards" style={{ marginTop: 8 }}>
          {out.events.map((e, k) => (
            <div className="card" key={k}>
              {e.kind === 'filed' && <><b>filed {name(e.game)} {e.puzzle}</b><small>{e.late ? 'filed late · ' : ''}{board ? `counts on every board with ${name(e.game)} on your agenda` : 'kept for you. it counts once you join a board that plays it.'}</small>{minutes(e.game)}</>}
              {e.kind === 'merged' && <><b>added the {e.added.join(', ')} to {name(e.game)} {e.puzzle}</b><small>same puzzle, more detail. nothing else changed.</small>{minutes(e.game)}</>}
              {e.kind === 'duplicate' && <><b>{name(e.game)} {e.puzzle} is already in the minutes</b><small>nothing new in that paste.</small></>}
              {e.kind === 'not_out_yet' && <><b>{name(e.game)} {e.puzzle} isn't out yet</b><small>file it once it's the current puzzle.</small></>}
              {e.kind === 'conflict' && e.result_id != null && (answered[e.result_id]
                ? <b>{answered[e.result_id]}</b>
                : <><b>you already filed {name(e.game)} {e.puzzle}, with a different result</b>
                    <div className="row-a"><button className="btn" onClick={() => replace(e.result_id!, out.paste_id)}>replace it</button>
                      <button className="lnk" onClick={() => setAnswered(a => ({ ...a, [e.result_id!]: 'kept the first one.' }))}>keep the first one</button></div></>)}
            </div>
          ))}
          {out.unknown.map((u, k) => (
            <div className="card" key={`u${k}`}>
              <b>we can't read {u.name} yet</b>
              <small>{u.score ? `${u.score} · ` : ''}the clerk has asked for a parser. it'll count once there is one.</small>
            </div>
          ))}
          <div className="row-a"><button className="lnk" onClick={() => setOut(null)}>done</button></div>
        </div>
      )}
    </div>
  )
}

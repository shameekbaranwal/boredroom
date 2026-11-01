import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api, type Game, type GridCell, type Period, type Review as R, type ReviewQuery, type Standing } from '../api'
import { dayLabel, fmtMetric, headline } from '../format'
import { go, query, usePath } from '../router'
import { Av, FxQuery, Ghost, Header, Nav, Tile, sendOn, useApp, useFresh, type Token } from '../ui'
import Boards from './Boards'

const PERIOD: Record<Period, string> = { today: 'today', week: 'this week', month: 'this month', all: 'all time' }
const TOP = 5  // standings shown before "all n"

/** "1", or "=1" when someone shares the place. */
const placeLabel = (rows: Standing[], s: Standing) =>
  s.place == null ? '–' : `${rows.filter(x => x.place === s.place).length > 1 ? '=' : ''}${s.place}`

/** The review (UX v8, screens 4–6). Everything on it is one query, written in the formula
 *  bar as =review(board, period, game, stat, vs) and kept in the url, so a view can be sent. */
export default function Review({ slug }: { slug: string }) {
  const { me, games, toast } = useApp()
  const path = usePath()
  const qs = query(path)
  const asked = qs.get('period') as Period | null
  const period: Period = asked && asked in PERIOD ? asked : 'today'
  // the grid is a second way to read the same query; it needs more than one day
  const q: ReviewQuery = { period, game: qs.get('game'), stat: qs.get('stat'), vs: qs.get('vs'), view: qs.get('view') === 'grid' && period !== 'today' ? 'grid' : null }
  const [r, setR] = useState<R | null>(null)
  const [err, setErr] = useState('')
  const [all, setAll] = useState(false)
  const [picker, setPicker] = useState(false)
  const board = me.boards.find(b => b.slug === slug)!
  const key = JSON.stringify(q)
  useEffect(() => { setErr(''); api.review(slug, q).then(setR).catch(e => setErr(e.message)) }, [slug, key])  // eslint-disable-line react-hooks/exhaustive-deps
  useFresh(() => { api.review(slug, q).then(setR).catch(() => {}) })

  const url = (x: ReviewQuery, s = slug) => {
    const p = new URLSearchParams()
    if (x.period !== 'today') p.set('period', x.period)
    for (const k of ['game', 'stat', 'vs', 'view'] as const) if (x[k]) p.set(k, x[k]!)
    const str = p.toString()
    return `/b/${s}/review${str ? `?${str}` : ''}`
  }
  // a new game changes which stats make sense, so the stat goes back to its default
  const set = (x: Partial<ReviewQuery>) => {
    setAll(false)
    const n = { ...q, ...('game' in x ? { stat: null } : {}), ...x }
    if (n.period === 'today') n.view = null  // one column isn't a grid
    go(url(n), true)
  }

  const name = (g: string) => games[g]?.name ?? g
  const metric = r?.game && r.metric ? games[r.game]?.metrics.find(m => m.name === r.metric) : undefined
  const STAT: Record<string, string> = {
    wins: 'daily wins', rate: 'win rate', days: 'days present', filed: 'puzzles filed',
    average: `average ${r?.metric ?? ''}`.trim(), best: 'best', played: 'plays', tenure: 'tenure', longest: 'longest tenure',
  }
  const tokens: Token[] = [
    { key: 'board', value: slug, options: me.boards.map(b => [b.slug, b.name]), onPick: s => go(url({ period: q.period }, s), true) },
    { key: 'period', value: q.period, options: (Object.keys(PERIOD) as Period[]).map(p => [p, PERIOD[p]]), onPick: p => set({ period: p as Period }) },
    { key: 'game', value: q.game ?? '', options: [['', 'all games'], ...(r?.ranked_games ?? (q.game ? [q.game] : [])).map(g => [g, name(g)] as [string, string])], onPick: g => set({ game: g || null }) },
    { key: 'stat', value: r?.stat ?? q.stat ?? '', options: r ? r.stats.map(s => [s, STAT[s]]) : [[q.stat ?? '', q.stat ?? '…']], onPick: s => set({ stat: s }) },
    { key: 'vs', value: q.vs ?? '', options: [['', 'no one'], ...(r?.members ?? (q.vs ? [q.vs] : [])).map(m => [m, m] as [string, string])], onPick: v => set({ vs: v || null }) },
    { key: 'view', value: q.view ?? 'list', options: [['list', 'standings'], ['grid', 'member × day grid']],
      onPick: v => set(v === 'grid' ? { view: 'grid', period: q.period === 'today' ? 'week' : q.period } : { view: null }) },
  ]
  const head = <>
    <Header title={`${board.name}.xlsx`} meta={q.game ? name(q.game) : 'review'} onTitle={() => setPicker(true)} />
    <FxQuery fn="review" tokens={tokens} />
  </>
  if (err) return <div className="app">{head}<div className="center err">{err}</div><Nav slug={slug} on="review" /></div>
  if (!r) return <div className="app">{head}<Ghost what="the review" /><Nav slug={slug} on="review" /></div>

  const rows = r.standings
  const mine = rows.findIndex(s => s.me)
  const shown = all ? rows : rows.filter((_, i) => i < TOP || i === mine)
  const longer = q.period !== 'today'
  const today = r.now.slice(0, 10)
  const avg = (v: number | null | undefined) => v == null ? '—' : fmtMetric(metric, Math.round(v * 10) / 10)
  const value = (s: Standing): [string, string] => {
    switch (r.stat) {
      case 'rate': return [`${Math.round(s.rate * 100)}%`, `${s.wins} of ${s.filed}`]
      case 'days': return [String(s.days), s.days === 1 ? 'day' : 'days']
      case 'filed': return [String(s.filed), 'filed']
      case 'average': return [avg(s.average), s.qualified ? `${s.played} played` : `${s.played} of ${r.min_plays} plays`]
      case 'best': return [s.best ? headline(games[r.game!], s.best) : '—', `${s.played} played`]
      case 'played': return [String(s.played), 'plays']
      case 'tenure': return [`${s.tenure}d`, s.at_risk ? 'at risk today' : 'in a row']
      case 'longest': return [`${s.longest}d`, s.tenure === s.longest && s.tenure ? 'and counting' : 'best run']
      default: return [String(s.wins), longer ? `of ${s.days} ${s.days === 1 ? 'day' : 'days'}` : s.wins === 1 ? 'win' : 'wins']
    }
  }
  const title = `${STAT[r.stat]}${r.game ? ` · ${name(r.game)}` : ''} · ${PERIOD[q.period]}`
  const h = r.h2h
  const share = () => {
    const top = rows.filter(s => s.place != null).slice(0, 10)
    const lines = top.length ? top.map(s => `${placeLabel(rows, s)}. ${s.nickname} · ${value(s).join(' ')}`) : ['nothing to report. the board is watching.']
    const vs = h ? `\n\n${board.nickname} vs ${r.vs}: ${h.you}–${h.them}${h.level ? ` (${h.level} level)` : ''}` : ''
    sendOn(`${board.name} · ${title}\n\n${lines.join('\n')}${vs}\n\n${location.origin}${url(q)}`, toast)
  }

  return (
    <div className="app">
      {head}
      <div className="bd">
        <div className="seg two" role="radiogroup" aria-label="period">
          {(['today', 'all'] as Period[]).map(p => (
            <button key={p} role="radio" aria-checked={q.period === p} className={q.period === p ? 'on' : ''} onClick={() => set({ period: p })}>{PERIOD[p]}</button>
          ))}
        </div>
        {(q.period === 'week' || q.period === 'month') && <div className="sub">{PERIOD[q.period]} · from the formula bar</div>}

        {r.game && <div className="stat-row">
          <div><b>{avg(rows[mine]?.average)}</b><small>your average</small></div>
          <div><b>{rows[mine]?.tenure ?? 0}d</b><small>your tenure{rows[mine]?.at_risk ? ' · at risk' : rows[mine]?.longest ? ` · best ${rows[mine].longest}d` : ''}</small></div>
          <div><b>{rows[mine]?.best ? headline(games[r.game], rows[mine].best!) : '—'}</b><small>your best</small></div>
          <div><b>{r.record ? headline(games[r.game], r.record.metrics) : '—'}</b><small>record{r.record ? ` · ${r.record.me ? 'you' : r.record.nickname}, ${dayLabel(r.record.day, today)}` : ''}</small></div>
        </div>}

        {h && <>
          <div className="sec rv-sec"><span>you vs {r.vs} · {r.game ? name(r.game) : 'every game'} · {PERIOD[q.period]}</span><button className="lnk" onClick={() => set({ vs: null })}>clear</button></div>
          <div className="h2h">
            <b className="score">{h.you}–{h.them}</b>
            <span>{h.you + h.them + h.level === 0 ? 'never met' : h.you === h.them ? 'level' : h.you > h.them ? 'you lead' : `${r.vs} leads`}{h.level ? ` · ${h.level} level` : ''}</span>
          </div>
        </>}

        <div className="sec rv-sec">
          <span>{title}</span>
          <span className="rv-acts">
            <button className="lnk" aria-pressed={!!q.view} onClick={() => set(q.view ? { view: null } : { view: 'grid', period: q.period === 'today' ? 'week' : q.period })}>
              {q.view ? 'as a list' : 'as a grid'}
            </button>
            <button className="lnk" onClick={share}>send to {board.name}</button>
          </span>
        </div>
        {q.view && r.grid ? <MemberGrid g={r.grid} game={r.game ? games[r.game] : undefined} vs={r.vs} today={r.grid.days[r.grid.days.length - 1]}
          onName={n => set({ vs: n === r.vs ? null : n })} onDay={d => r.game && go(`/b/${slug}/m/${r.game}/${d}`)} /> : <>
        {rows.length === 0 && <div className="sub wrap">nothing filed {q.period === 'today' ? 'yet today' : PERIOD[q.period]}. the minutes are empty.</div>}
        {shown.map((s, k) => {
          const [v, t2] = value(s)
          return (
            <Fragment key={s.nickname}>
              {!all && k === TOP && <div className="gap">⋯</div>}
              <button className={`wr${s.me ? ' me' : ''}${r.vs === s.nickname ? ' cmp' : ''}${s.qualified === false ? ' dim' : ''}`}
                onClick={() => set({ vs: s.me || r.vs === s.nickname ? null : s.nickname })}
                title={s.me ? undefined : `you vs ${s.nickname}`}>
                <span className="n">{placeLabel(rows, s)}</span>
                <Av name={s.nickname} />
                <span className="who">{s.nickname}</span>
                <b className="v">{v}</b>
                <span className="t2">{t2}</span>
              </button>
            </Fragment>
          )
        })}
        {rows.length > TOP && <button className="more" onClick={() => setAll(v => !v)}>{all ? `show top ${TOP}` : `all ${rows.length} →`}</button>}
        <div className="sub wrap rv-note">
          {r.stat === 'tenure' || r.stat === 'longest' ? 'tenure is days in a row with this game filed, over all time. it survives until the reset after a missed day. ' : r.stat === 'average' ? `ranked by average once you have ${r.min_plays}+ plays ${PERIOD[q.period]}. ` : r.stat === 'wins' || r.stat === 'rate' ? 'a daily win is first place in a puzzle at least two of you filed; ties all count. ' : ''}
          tap a name for a head-to-head.
        </div>
        </>}

        <div className="sec">{h ? `last 30 days · you vs ${r.vs}` : `your last 30 days${r.game ? ` · ${name(r.game)}` : ''}`}</div>
        <div className="strip-row">
          <div className={`strip${h ? '' : ' solo'}`} aria-label="last 30 days">{r.strip.map((c, i) => <i key={i} className={c} />)}</div>
          <div className={`key${h ? '' : ' solo'}`}>
            {h ? <><span><i className="on" />you won</span><span><i className="ls" />{r.vs} won</span><span><i className="lv" />level</span></>
              : <><span><i className="on" />took a #1</span><span><i className="ls" />played, no #1</span></>}
          </div>
        </div>

        {r.games && <>
          <div className="sec">item by item</div>
          {[...r.games].sort((a, b) => b.present - a.present).map(g => {
            const ld = g.leader
            const tag = !g.plays ? '' : !g.filed ? 'open' : g.ranked && g.place ? `#${g.place}` : '✓'
            return (
              <div key={g.game} className="it" onClick={() => go(`/b/${slug}/m/${g.game}`)} role="button" tabIndex={0}>
                <Tile game={g.game} name={g.name} />
                <div className="g">
                  <div className="nm">{g.name}</div>
                  <div className="sub">
                    {ld ? <>{ld.nickname ?? `${ld.tied} tied`} <b>{headline(games[g.game], ld.metrics)}</b></>
                      : g.present ? (g.ranked ? '—' : 'for fun') : 'no one yet'}
                    <span> · {g.present}/{g.players} present</span>
                  </div>
                </div>
                {tag && <span className={`pill ${tag === 'open' ? 'todo' : 'done'}`}>{tag}</span>}
              </div>
            )
          })}
        </>}

        {r.records && <>
          <div className="sec">{q.period === 'all' ? 'board records' : `best ${PERIOD[q.period]}`} <span className="sec-n">· tap one for the game's review</span></div>
          {r.records.length === 0 && <div className="sub wrap">no records yet.</div>}
          {r.records.map(x => (
            <div key={x.game} className="it" onClick={() => set({ game: x.game })} role="button" tabIndex={0}>
              <Tile game={x.game} name={x.name} />
              <div className="g">
                <div className="nm">{x.name}</div>
                <div className="sub"><span className="who-s"><Av name={x.nickname} />{x.me ? 'you' : x.nickname}</span> · {dayLabel(x.day, today)}</div>
              </div>
              <b className="rec">{headline(games[x.game], x.metrics)}</b>
            </div>
          ))}
        </>}
        {r.game && <button className="more" onClick={() => go(`/b/${slug}/m/${r.game}`)}>today's {name(r.game)} minutes →</button>}
      </div>
      <Nav slug={slug} on="review" temp={r.game ? name(r.game) : undefined} />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
    </div>
  )
}

const WD = ['su', 'mo', 'tu', 'we', 'th', 'fr', 'sa']

/** A cell's short form: the first metric the game ranks by, without its "/1000". */
function compact(game: Game | undefined, c: Extract<GridCell, { m: unknown }>): string {
  if (c.o === 'failed') return '✗'
  const name = game?.ranker[0] ?? Object.keys(c.m)[0]
  const v = c.m[name]
  if (v == null) return '✓'
  const m = game?.metrics.find(x => x.name === name)
  return m?.kind === 'duration' ? fmtMetric(m, v) : Number.isInteger(v) ? String(v) : v.toFixed(1)
}

/** The review's second view: members down the side, days across (UX-NOTES §1). A week fits a
 *  phone; a month scrolls sideways inside its own box, names pinned, opening on today. */
function MemberGrid({ g, game, vs, today, onName, onDay }: {
  g: NonNullable<R['grid']>; game?: Game; vs: string | null; today: string; onName: (n: string) => void; onDay: (d: string) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => { if (box.current) box.current.scrollLeft = box.current.scrollWidth }, [g.days.length])
  const cols = { ['--n' as string]: g.days.length }
  return <>
    <div className="mg-w"><div className={`mg${g.days.length > 7 ? ' long' : ''}`} ref={box} role="table" aria-label="member by day">
      <div className="mg-r mg-h" role="row" style={cols}>
        <span className="mg-n" role="columnheader" />
        {g.days.map(d => {
          const dt = new Date(d + 'T00:00:00')
          return (
            <button key={d} role="columnheader" className={`mg-d${d === today ? ' now' : ''}`} disabled={!game}
              title={game ? `${game.name}, ${dayLabel(d, today)}` : dayLabel(d, today)} onClick={() => onDay(d)}>
              <small>{WD[dt.getDay()]}</small>{dt.getDate()}
            </button>
          )
        })}
        <span className="mg-t" role="columnheader" title={game ? 'times #1' : 'daily wins'}>Σ</span>
      </div>
      {g.rows.map(r => (
        <div key={r.nickname} role="row" style={cols}
          className={`mg-r${r.me ? ' me' : ''}${vs && (r.me || r.nickname === vs) ? ' cmp' : ''}${r.ghost ? ' ghost' : ''}`}>
          <button className="mg-n" role="rowheader" onClick={() => !r.me && onName(r.nickname)} title={r.me ? undefined : `you vs ${r.nickname}`}>
            <Av name={r.nickname} /><span>{r.nickname}</span>
          </button>
          {r.cells.map((c, i) => {
            const d = g.days[i]
            if (!c) return <span key={d} role="cell" className="mg-c" />
            if ('v' in c) return <span key={d} role="cell" className={`mg-c ${c.v ? 'win' : 'tint'}`}
              title={`${c.v} daily win${c.v === 1 ? '' : 's'}, ${c.f} filed · ${dayLabel(d, today)}`}>{c.v || ''}</span>
            if (c.k === 'off') return <span key={d} role="cell" className="mg-c off" title="hadn't taken it up yet" />
            return <span key={d} role="cell" className={`mg-c ${c.k}${c.late ? ' late' : ''}`}
              title={`${headline(game, c.m, c.o)} · ${dayLabel(d, today)}${c.late ? ' · filed late' : ''}`}>{compact(game, c)}</span>
          })}
          <b className="mg-t" role="cell">{r.total || ''}</b>
        </div>
      ))}
    </div></div>
    <div className="key mg-key">
      {game ? <><span><i className="top" />#1</span><span><i className="miss" />missed</span><span><i className="off" />not taken up yet</span></>
        : <><span><i className="win" />daily wins</span><span><i className="tint" />filed, no win</span></>}
    </div>
    <div className="sub wrap rv-note">
      {g.absent > 0 && `+${g.absent} absent ${g.days.length > 7 ? 'all month' : 'all week'} · `}tap a name for a head-to-head{game ? ', a day for its minutes' : ''}.
    </div>
  </>
}

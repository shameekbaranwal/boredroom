import { Fragment, useEffect, useState } from 'react'
import { api, type Period, type Review as R, type ReviewQuery, type Standing } from '../api'
import { dayLabel, fmtMetric, headline, weekLabel } from '../format'
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
  const q: ReviewQuery = { period: asked && asked in PERIOD ? asked : 'today', game: qs.get('game'), stat: qs.get('stat'), vs: qs.get('vs') }
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
    for (const k of ['game', 'stat', 'vs'] as const) if (x[k]) p.set(k, x[k]!)
    const str = p.toString()
    return `/b/${s}/review${str ? `?${str}` : ''}`
  }
  // a new game changes which stats make sense, so the stat goes back to its default
  const set = (x: Partial<ReviewQuery>) => { setAll(false); go(url({ ...q, ...('game' in x ? { stat: null } : {}), ...x }), true) }

  const name = (g: string) => games[g]?.name ?? g
  // a weekly game on its own has no "today": its puzzle is this week's, and it counts in weeks
  const wk = !!(q.game && games[q.game]?.weekly)
  const per = (p: Period) => (wk && p === 'today' ? 'this week' : PERIOD[p])
  const when = (g: string, d: string, today: string) => (games[g]?.weekly ? weekLabel : dayLabel)(d, today)
  const metric = r?.game && r.metric ? games[r.game]?.metrics.find(m => m.name === r.metric) : undefined
  const STAT: Record<string, string> = {
    wins: wk ? 'weekly wins' : 'daily wins', rate: 'win rate', days: wk ? 'weeks present' : 'days present', filed: 'puzzles filed',
    average: `average ${r?.metric ?? ''}`.trim(), best: 'best', played: 'plays', tenure: 'tenure', longest: 'longest tenure',
  }
  const tokens: Token[] = [
    { key: 'board', value: slug, options: me.boards.map(b => [b.slug, b.name]), onPick: s => go(url({ period: q.period }, s), true) },
    { key: 'period', value: q.period, options: (Object.keys(PERIOD) as Period[]).filter(p => !(wk && p === 'week')).map(p => [p, per(p)]), onPick: p => set({ period: p as Period }) },
    { key: 'game', value: q.game ?? '', options: [['', 'all games'], ...(r?.ranked_games ?? (q.game ? [q.game] : [])).map(g => [g, name(g)] as [string, string])], onPick: g => set({ game: g || null }) },
    { key: 'stat', value: r?.stat ?? q.stat ?? '', options: r ? r.stats.map(s => [s, STAT[s]]) : [[q.stat ?? '', q.stat ?? '…']], onPick: s => set({ stat: s }) },
    { key: 'vs', value: q.vs ?? '', options: [['', 'no one'], ...(r?.members ?? (q.vs ? [q.vs] : [])).map(m => [m, m] as [string, string])], onPick: v => set({ vs: v || null }) },
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
      case 'tenure': return [`${s.tenure}${wk ? 'w' : 'd'}`, s.at_risk ? (wk ? 'at risk this week' : 'at risk today') : 'in a row']
      case 'longest': return [`${s.longest}${wk ? 'w' : 'd'}`, s.tenure === s.longest && s.tenure ? 'and counting' : 'best run']
      default: return [String(s.wins), longer ? `of ${s.days} ${wk ? (s.days === 1 ? 'week' : 'weeks') : s.days === 1 ? 'day' : 'days'}` : s.wins === 1 ? 'win' : 'wins']
    }
  }
  const title = `${STAT[r.stat]}${r.game ? ` · ${name(r.game)}` : ''} · ${per(q.period)}`
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
            <button key={p} role="radio" aria-checked={q.period === p} className={q.period === p ? 'on' : ''} onClick={() => set({ period: p })}>{per(p)}</button>
          ))}
        </div>
        {(q.period === 'week' || q.period === 'month') && <div className="sub">{per(q.period)} · from the formula bar</div>}

        {r.game && <div className="stat-row">
          <div><b>{avg(rows[mine]?.average)}</b><small>your average</small></div>
          <div><b>{rows[mine]?.tenure ?? 0}{wk ? 'w' : 'd'}</b><small>your tenure{rows[mine]?.at_risk ? ' · at risk' : rows[mine]?.longest ? ` · best ${rows[mine].longest}${wk ? 'w' : 'd'}` : ''}</small></div>
          <div><b>{rows[mine]?.best ? headline(games[r.game], rows[mine].best!) : '—'}</b><small>your best</small></div>
          <div><b>{r.record ? headline(games[r.game], r.record.metrics) : '—'}</b><small>record{r.record ? ` · ${r.record.me ? 'you' : r.record.nickname}, ${when(r.game, r.record.day, today)}` : ''}</small></div>
        </div>}

        {h && <>
          <div className="sec rv-sec"><span>you vs {r.vs} · {r.game ? name(r.game) : 'every game'} · {per(q.period)}</span><button className="lnk" onClick={() => set({ vs: null })}>clear</button></div>
          <div className="h2h">
            <b className="score">{h.you}–{h.them}</b>
            <span>{h.you + h.them + h.level === 0 ? 'never met' : h.you === h.them ? 'level' : h.you > h.them ? 'you lead' : `${r.vs} leads`}{h.level ? ` · ${h.level} level` : ''}</span>
          </div>
        </>}

        <div className="sec rv-sec"><span>{title}</span><button className="lnk" onClick={share}>send to {board.name}</button></div>
        {rows.length === 0 && <div className="sub wrap">nothing filed {q.period === 'today' ? (wk ? 'yet this week' : 'yet today') : per(q.period)}. the minutes are empty.</div>}
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
          {r.stat === 'tenure' || r.stat === 'longest' ? `tenure is ${wk ? 'weeks' : 'days'} in a row with this game filed, over all time. it survives until the reset after a missed ${wk ? 'week' : 'day'}. ` : r.stat === 'average' ? `ranked by average once you have ${r.min_plays}+ plays ${per(q.period)}. ` : r.stat === 'wins' || r.stat === 'rate' ? `a ${wk ? 'weekly' : 'daily'} win is first place in a puzzle at least two of you filed; ties all count. ` : ''}
          tap a name for a head-to-head.
        </div>

        <div className="sec">{h ? `last 30 ${wk ? 'weeks' : 'days'} · you vs ${r.vs}` : `your last 30 ${wk ? 'weeks' : 'days'}${r.game ? ` · ${name(r.game)}` : ''}`}</div>
        <div className="strip-row">
          <div className={`strip${h ? '' : ' solo'}`} aria-label={`last 30 ${wk ? 'weeks' : 'days'}`}>{r.strip.map((c, i) => <i key={i} className={c} />)}</div>
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
          <div className="sec">{q.period === 'all' ? 'board records' : `best ${per(q.period)}`} <span className="sec-n">· tap one for the game's review</span></div>
          {r.records.length === 0 && <div className="sub wrap">no records yet.</div>}
          {r.records.map(x => (
            <div key={x.game} className="it" onClick={() => set({ game: x.game })} role="button" tabIndex={0}>
              <Tile game={x.game} name={x.name} />
              <div className="g">
                <div className="nm">{x.name}</div>
                <div className="sub"><span className="who-s"><Av name={x.nickname} />{x.me ? 'you' : x.nickname}</span> · {when(x.game, x.day, today)}</div>
              </div>
              <b className="rec">{headline(games[x.game], x.metrics)}</b>
            </div>
          ))}
        </>}
        {r.game && <button className="more" onClick={() => go(`/b/${slug}/m/${r.game}`)}>{wk ? "this week's" : "today's"} {name(r.game)} minutes →</button>}
      </div>
      <Nav slug={slug} on="review" temp={r.game ? name(r.game) : undefined} />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
    </div>
  )
}

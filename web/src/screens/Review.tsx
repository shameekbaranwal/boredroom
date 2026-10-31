import { Fragment, useEffect, useState } from 'react'
import { api, type Period, type Review as R, type Standing } from '../api'
import { dayLabel, headline } from '../format'
import { go, query, usePath } from '../router'
import { Av, Header, Loading, Nav, Tile, sendOn, useApp } from '../ui'
import Boards from './Boards'

const PERIOD: Record<Period, string> = { today: 'today', week: 'this week', month: 'this month', all: 'all time' }
const TOP = 5  // standings shown before "all n"

/** "1", or "=1" when someone shares the place. */
const placeLabel = (rows: Standing[], s: Standing) => `${rows.filter(x => x.place === s.place).length > 1 ? '=' : ''}${s.place}`

/** The review (UX v8, screens 4 and 5): today and all time up front, week and month from
 *  the formula bar. Daily wins first, then each game's leader today, or the board's records. */
export default function Review({ slug }: { slug: string }) {
  const { me, games, toast } = useApp()
  const path = usePath()
  const asked = query(path).get('period') as Period | null
  const period: Period = asked && asked in PERIOD ? asked : 'today'
  const [r, setR] = useState<R | null>(null)
  const [err, setErr] = useState('')
  const [all, setAll] = useState(false)
  const [picker, setPicker] = useState(false)
  const board = me.boards.find(b => b.slug === slug)!
  useEffect(() => { setR(null); setErr(''); api.review(slug, period).then(setR).catch(e => setErr(e.message)) }, [slug, period])
  const show = (p: Period) => { setAll(false); go(`/b/${slug}/review${p === 'today' ? '' : `?period=${p}`}`, true) }

  const fx = (
    <div className="fx keep">
      <i>fx</i>=review( board:<b>"{board.name}"</b>, period:
      <select className="fx-sel" aria-label="period" value={period} onChange={e => show(e.target.value as Period)}>
        {(Object.keys(PERIOD) as Period[]).map(p => <option key={p} value={p}>"{PERIOD[p]}"</option>)}
      </select> )
    </div>
  )
  const head = <Header title={`${board.name}.xlsx`} meta="review" onTitle={() => setPicker(true)} />
  if (err) return <div className="app">{head}{fx}<div className="center err">{err}</div><Nav slug={slug} on="review" /></div>
  if (!r) return <div className="app">{head}{fx}<Loading what="the review" /><Nav slug={slug} on="review" /></div>

  const rows = r.standings
  const mine = rows.findIndex(s => s.me)
  const shown = all ? rows : rows.filter((_, i) => i < TOP || i === mine)
  const longer = period !== 'today'
  const today = r.now.slice(0, 10)
  const share = () => {
    const top = rows.filter(s => s.wins > 0).slice(0, 10)
    const lines = top.length
      ? top.map(s => `${placeLabel(rows, s)}. ${s.nickname} · ${s.wins} ${s.wins === 1 ? 'win' : 'wins'}${longer ? ` of ${s.days} days` : ''}`)
      : ['no daily wins yet. the board is watching.']
    sendOn(`${board.name} · daily wins · ${PERIOD[period]}\n\n${lines.join('\n')}\n\n${location.origin}/b/${slug}/review${longer ? `?period=${period}` : ''}`, toast)
  }

  return (
    <div className="app">
      {head}
      {fx}
      <div className="bd">
        <div className="seg two plain-seg" role="radiogroup" aria-label="period">
          <button role="radio" aria-checked={period === 'today'} className={period === 'today' ? 'on' : ''} onClick={() => show('today')}>today</button>
          <button role="radio" aria-checked={period === 'all'} className={period === 'all' ? 'on' : ''} onClick={() => show('all')}>all time</button>
        </div>
        {(period === 'week' || period === 'month') && <div className="sub">{PERIOD[period]} · from the formula bar</div>}

        <div className="sec rv-sec"><span>daily wins · {PERIOD[period]}</span><button className="lnk" onClick={share}>send to {board.name}</button></div>
        {rows.length === 0 && <div className="sub wrap">nothing filed {period === 'today' ? 'yet today' : PERIOD[period]}. the minutes are empty.</div>}
        {shown.map((s, k) => <Fragment key={s.nickname}>
          {!all && k === TOP && <div className="gap">⋯</div>}
          <div className={`wr${s.me ? ' me' : ''}`}>
            <span className="n">{s.wins ? placeLabel(rows, s) : '–'}</span>
            <Av name={s.nickname} />
            <span className="who">{s.me ? `${s.nickname} (you)` : s.nickname}</span>
            <b className="v">{s.wins}</b>
            <span className="t2">{longer ? `of ${s.days} ${s.days === 1 ? 'day' : 'days'}` : s.wins === 1 ? 'win' : 'wins'}</span>
          </div>
        </Fragment>)}
        {rows.length > TOP && <button className="more" onClick={() => setAll(v => !v)}>{all ? `show top ${TOP}` : `all ${rows.length} →`}</button>}
        <div className="sub wrap rv-note">a daily win is first place in a puzzle at least two of you filed. ties all count.</div>

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
          <div className="sec">{period === 'all' ? 'board records' : `best ${PERIOD[period]}`}</div>
          {r.records.length === 0 && <div className="sub wrap">no records yet.</div>}
          {r.records.map(x => (
            <div key={x.game} className="it" onClick={() => go(`/b/${slug}/m/${x.game}/${x.day}`)} role="button" tabIndex={0}>
              <Tile game={x.game} name={x.name} />
              <div className="g">
                <div className="nm">{x.name}</div>
                <div className="sub"><span className="who-s"><Av name={x.nickname} />{x.me ? 'you' : x.nickname}</span> · {dayLabel(x.day, today)}</div>
              </div>
              <b className="rec">{headline(games[x.game], x.metrics)}</b>
            </div>
          ))}
        </>}
      </div>
      <Nav slug={slug} on="review" />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
    </div>
  )
}

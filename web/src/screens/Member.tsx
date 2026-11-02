import { useEffect, useState } from 'react'
import { api, type MemberPage } from '../api'
import { dayLabel, headline, weekLabel } from '../format'
import { go } from '../router'
import { MemoRow } from '../memos'
import { Av, Fx, Ghost, Header, Nav, Tile, Trouble, useApp, useFresh } from '../ui'

/** A member's page: what they play on this board and how it's going. Their name in the
 *  review, the minutes or a memo opens it; the head-to-head is one tap further. */
export default function Member({ slug, nickname }: { slug: string; nickname: string }) {
  const { me, games } = useApp()
  const [p, setP] = useState<MemberPage | null>(null)
  const [err, setErr] = useState('')
  const load = () => api.member(slug, nickname).then(x => { setP(x); setErr('') }).catch(e => setErr(e.message))
  useEffect(() => { setP(null); load() }, [slug, nickname])  // eslint-disable-line react-hooks/exhaustive-deps
  useFresh(load)

  const board = me.boards.find(b => b.slug === slug)
  const head = <>
    <Header title={`${board?.name ?? slug}.xlsx`} meta="member" back={`/b/${slug}/review`} />
    <Fx fn="member" args={[['board', board?.name ?? slug], ['who', nickname]]} />
  </>
  if (err) return <div className="app">{head}<Trouble err={err} retry={load} /><Nav slug={slug} on="review" /></div>
  if (!p) return <div className="app">{head}<Ghost what={`${nickname}'s activity`} /><Nav slug={slug} on="review" /></div>

  const who = p.me ? 'you' : p.nickname
  const since = new Date(p.joined_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).toLowerCase()
  const when = (weekly: boolean, d: string) => (weekly ? weekLabel : dayLabel)(d, p.today)
  const unit = (weekly: boolean) => (weekly ? 'w' : 'd')
  const ordinal = (place: string) => {
    const n = parseInt(place.replace('=', ''), 10)
    const th = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'
    return `${place.startsWith('=') ? 'joint ' : ''}${n}${th}`
  }
  const cell = (c: number) => (!c ? '' : c >= p.daily ? 'on' : 'ls')

  return (
    <div className="app">
      {head}
      <div className="bd">
        <div className="mb-h">
          <Av name={p.nickname} />
          <div className="g">
            <div className="nm">{p.nickname}{p.me && <span className="sub"> · you</span>}</div>
            <div className="sub">{p.role === 'chair' ? 'the chair · ' : ''}on {board?.name} since {since} · {p.games.length} game{p.games.length === 1 ? '' : 's'} on the agenda</div>
          </div>
          {!p.me && <button className="pill todo" onClick={() => go(`/b/${slug}/review?period=all&vs=${encodeURIComponent(p.nickname)}`)}>you vs {p.nickname} →</button>}
        </div>

        <div className="stat-row">
          <div><b>{p.present}/7</b><small>days in, this week</small></div>
          <div><b>{p.wins}</b><small>wins, last 30 puzzles</small></div>
          <div><b>{p.games.reduce((n, g) => Math.max(n, g.weekly ? 0 : g.tenure), 0)}d</b><small>longest running tenure</small></div>
        </div>

        <div className="sec">last 30 days</div>
        <div className="strip-row">
          <div className="strip solo" aria-label="last 30 days">{p.strip.map((c, i) => <i key={i} className={cell(c)} title={`${c} filed`} />)}</div>
          <div className="key solo"><span><i className="on" />every daily game</span><span><i className="ls" />some</span></div>
        </div>

        <div className="sec">game by game</div>
        {p.games.length === 0 && <div className="sub wrap">nothing on {who === 'you' ? 'your' : `${who}'s`} agenda here yet.</div>}
        {p.games.map(g => (
          <div key={g.game} className="it" role="button" tabIndex={0} onClick={() => go(`/b/${slug}/m/${g.game}`)}>
            <Tile game={g.game} name={g.name} />
            <div className="g">
              <div className="nm">{g.name}</div>
              <div className="sub">
                {[g.best && `best ${headline(games[g.game], g.best)}`,
                  g.average != null && `avg ${headline(games[g.game], { [games[g.game]?.ranker[0] ?? '']: g.average })}`,
                  g.ranked && `${g.wins} win${g.wins === 1 ? '' : 's'} in ${g.played}`,
                  !g.ranked && `${g.played} in the last 30`,
                  g.last ? `last ${when(g.weekly, g.last)}` : 'never filed',
                ].filter(Boolean).join(' · ')}
              </div>
            </div>
            {g.tenure > 0 && <span className={`pill ${g.at_risk ? 'todo' : 'done'}`} title={`best run ${g.longest}${unit(g.weekly)}`}>
              {g.tenure}{unit(g.weekly)}{g.at_risk ? ' · at risk' : ''}</span>}
          </div>
        ))}

        <div className="sec">lately</div>
        {p.recent.length === 0 && <div className="sub wrap">nothing filed in the last 30 days.</div>}
        {p.recent.map((r, i) => (
          <div key={i} className="it" role="button" tabIndex={0} onClick={() => go(`/b/${slug}/m/${r.game}/${r.day}`)}>
            <Tile game={r.game} name={r.name} />
            <div className="g">
              <div className="nm">{r.name} <span className="sub">{when(r.weekly, r.day)}</span></div>
              <div className="sub">
                {r.place ? `${ordinal(r.place)} of ${r.of}` : r.of > 1 ? `with ${r.of - 1} other${r.of > 2 ? 's' : ''}` : 'alone'}
                {r.highlights.length > 0 && <> · {r.highlights.join(', ')}</>}
                {r.late && ' · filed late'}
              </div>
            </div>
            <b className="mb-v">{headline(games[r.game], r.metrics, r.outcome)}</b>
          </div>
        ))}

        {p.memos.length > 0 && <>
          <div className="sec">memos about {who}</div>
          {p.memos.map(m => <MemoRow key={m.id} m={m} game={m.game ? games[m.game] : undefined} />)}
        </>}
      </div>
      <Nav slug={slug} on="review" />
    </div>
  )
}

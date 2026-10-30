import { useEffect, useState } from 'react'
import { api, type Minutes as M, type Row } from '../api'
import { dayLabel, fieldText, headline, isGrid, left, shiftDay } from '../format'
import { go } from '../router'
import { Av, Fx, Header, Loading, Nav, sendOn, useApp, useNow } from '../ui'

export default function Minutes({ slug, game, day }: { slug: string; game: string; day?: string }) {
  const { games, toast } = useApp()
  const [m, setM] = useState<M | null>(null)
  const [err, setErr] = useState('')
  const [nudge, setNudge] = useState(false)
  const now = useNow()
  const [today, setToday] = useState<string | null>(null)

  useEffect(() => {
    setM(null)
    api.minutes(slug, game, day).then(x => { setM(x); if (x.current) setToday(x.day) }).catch(e => setErr(e.message))
  }, [slug, game, day])
  useEffect(() => { if (!today) api.minutes(slug, game).then(x => setToday(x.day)).catch(() => {}) }, [slug, game, today])

  const G = games[game]
  const title = G?.name ?? game
  if (err) return <div className="app"><Header title={`${slug}.xlsx`} back={`/b/${slug}`} /><div className="center err">{err}</div></div>
  if (!m) return <div className="app"><Header title={`${slug}.xlsx`} meta="minutes" back={`/b/${slug}`} /><Loading /></div>

  const label = today ? dayLabel(m.day, today) : m.day
  const prev = shiftDay(m.day, -1), next = shiftDay(m.day, 1)
  const mine = m.rows.find(r => r.me)
  const lock = m.open ? 'you filed · details are open'
    : nudge ? `file ${title} first. no peeking.`
    : 'scores are public · details unlock when you file'

  return (
    <div className="app">
      <Header title={`${slug}.xlsx`} meta="minutes" back={`/b/${slug}`} />
      <Fx fn="minutes" args={[['game', title], ['puzzle', label]]} />
      <div className="bd">
        <div className="seg">
          <button onClick={() => go(`/b/${slug}/m/${game}/${prev}`)}>‹ {today ? dayLabel(prev, today) : prev}</button>
          <button className="on">{label}</button>
          <button disabled={m.current} onClick={() => go(next === today ? `/b/${slug}/m/${game}` : `/b/${slug}/m/${game}/${next}`)}>{m.current ? '·' : `${today ? dayLabel(next, today) : next} ›`}</button>
        </div>
        <div className="sub wrap">
          {m.rows.length} of {m.rows.length + m.not_in.length} present
          {m.resets_at && <> · resets in {left(m.resets_at, now)}</>}
        </div>
        <div className={`lock${nudge ? ' err' : ''}`}>{lock}</div>
        {m.rows.map((r, i) => <MinuteRow key={i} r={r} open={m.open} onNudge={() => setNudge(true)} />)}
        {m.rows.length === 0 && <div className="sub wrap">no one has filed this puzzle.</div>}
        {m.not_in.length > 0 && <div className="absent">not in yet: {m.not_in.join(', ')}</div>}
        {mine && (
          <div className="row-a">
            {mine.forward && <button className="btn" onClick={() => sendOn(mine.forward!, toast)}>send on</button>}
            <button className="lnk" onClick={async () => {
              if (!mine.id) return
              await api.withdraw(mine.id); toast(`withdrew your ${title}`); setM(null)
              api.minutes(slug, game, day).then(setM)
            }}>withdraw yours</button>
          </div>
        )}
      </div>
      <Nav slug={slug} on={null} temp={`${title} · ${label}`} />
    </div>
  )

  function MinuteRow({ r, open, onNudge }: { r: Row; open: boolean; onNudge: () => void }) {
    const details = r.fields.filter(f => f.name !== 'mode')
    return (
      <div className="mr">
        <div className="mrow">
          <span className={`who${r.me ? ' me' : ''}`}>
            <span className="rn">{r.place || '·'}</span><Av name={r.nickname} />{r.nickname}
            {r.highlights.map(h => <span key={h} className="chip badge">{h}</span>)}
            {r.late && <span className="stamp">late</span>}
            {r.amended && <span className="stamp">amended</span>}
          </span>
          <span className="mv">{headline(G, r.metrics, r.outcome)}</span>
        </div>
        {details.map(f => isGrid(f)
          ? <div key={f.name} className="grid keep">{fieldText(f)}</div>
          : <div key={f.name} className="det"><span className="keep">{f.name}: {fieldText(f)}</span></div>)}
        {!open && r.hidden > 0 && <button className="lnk det" style={{ textAlign: 'left' }} onClick={onNudge}>{r.hidden} detail{r.hidden > 1 ? 's' : ''} hidden</button>}
        {r.comment && <div className="det keep">“{r.comment}”</div>}
      </div>
    )
  }
}

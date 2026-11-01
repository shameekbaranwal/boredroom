import { useCallback, useEffect, useState } from 'react'
import { api, type Meeting as M } from '../api'
import { dayLabel, shiftDay } from '../format'
import { go } from '../router'
import { Fx, Ghost, Header, Nav, sendOn, useApp, useFresh } from '../ui'
import { MemoRow, meetingText } from '../memos'

const UPFRONT = 6  // memos shown before "more"

/** The daily bored meeting: every memo the board had that day, the biggest news first. */
export default function Meeting({ slug, day }: { slug: string; day?: string }) {
  const { me, games, toast } = useApp()
  const [m, setM] = useState<M | null>(null)
  const [err, setErr] = useState('')
  const [all, setAll] = useState(false)
  const load = useCallback(() => { api.meeting(slug, day).then(setM).catch(e => setErr(e.message)) }, [slug, day])
  useEffect(() => { setM(null); setAll(false); load() }, [load])
  useFresh(load)
  const boardName = me.boards.find(b => b.slug === slug)?.name ?? slug
  const at = (d: string) => go(`/b/${slug}/meeting${m && d !== m.today ? `?day=${d}` : ''}`, true)
  const label = m ? dayLabel(m.day, m.today) : day ?? 'today'
  const head = <>
    <Header title={`${boardName}.xlsx`} meta="meeting" />
    <Fx fn="meeting" args={[['board', boardName], ['day', label]]} />
  </>
  if (err) return <div className="app">{head}<div className="center err">{err}</div><Nav slug={slug} on="meeting" /></div>
  if (!m) return <div className="app">{head}<Ghost what="the meeting" /><Nav slug={slug} on="meeting" /></div>

  const prev = shiftDay(m.day, -1), next = shiftDay(m.day, 1), current = m.day >= m.today
  const long = new Date(m.day + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }).toLowerCase()
  return (
    <div className="app">
      {head}
      <div className="bd">
        <div className="seg">
          <button onClick={() => at(prev)}>‹ {dayLabel(prev, m.today)}</button>
          <button className="on">{label}</button>
          <button disabled={current} onClick={() => at(next)}>{current ? '·' : `${dayLabel(next, m.today)} ›`}</button>
        </div>
        <div className="ph-sec"><span>the daily bored meeting · {long}</span>{m.memos.length > 0 && <span>{m.memos.length} item{m.memos.length > 1 ? 's' : ''}</span>}</div>
        {(all ? m.memos : m.memos.slice(0, UPFRONT)).map(x => <MemoRow key={x.id} m={x} game={x.game ? games[x.game] : undefined} />)}
        {!all && m.memos.length > UPFRONT && <button className="more" onClick={() => setAll(true)}>{m.memos.length - UPFRONT} more on the record →</button>}
        {m.memos.length === 0 && <>
          <div className="sub wrap">no memos {m.day === m.today ? 'today' : 'that day'}. the board had a quiet one.</div>
          {m.earlier && m.earlier < m.day && <button className="more" onClick={() => at(m.earlier!)}>the last meeting, {dayLabel(m.earlier, m.today)} →</button>}
        </>}
        {m.memos.length > 0 && (
          <div className="row-a">
            <button className="btn" onClick={() => sendOn(meetingText(boardName, long, m.memos, games), toast)}>send to {boardName}</button>
          </div>
        )}
      </div>
      <Nav slug={slug} on="meeting" />
    </div>
  )
}

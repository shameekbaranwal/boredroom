import { useEffect, useState } from 'react'
import { api, type Release, type Reply } from '../api'
import { go } from '../router'
import { Fx, Ghost, Header, Nav, Trouble, useApp } from '../ui'

const LAST = 'boredroom.board'
const lastBoard = () => { try { return localStorage.getItem(LAST) } catch { return null } }

/** The day a release went out, the way the minutes say a day: "3 nov". */
export const releaseDay = (id: string) =>
  new Date(id.slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).toLowerCase()  // "2026-11-04-2" is a second that day

/** What's new: every release, newest first. Opening it reads them all. A release that
 *  answered one of your notes shows your note and the answer under it, to you alone. */
export default function News() {
  const { me, refreshMe } = useApp()
  const [rs, setRs] = useState<Release[] | null>(null)
  const [replies, setReplies] = useState<Reply[]>([])
  const [err, setErr] = useState('')
  const load = () => api.news().then(x => {
    setRs(x.releases); setReplies(x.replies ?? []); setErr('')
    if (x.releases[0] && x.releases[0].id !== x.seen) api.newsSeen(x.releases[0].id).then(refreshMe).catch(() => {})
  }).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  // opened from an answer's push or card: straight to its release
  useEffect(() => {
    const id = decodeURIComponent(location.hash.slice(1))
    if (rs && id) document.getElementById(id)?.scrollIntoView({ block: 'start' })
  }, [rs])
  const slug = me.boards.find(b => b.slug === lastBoard())?.slug ?? me.boards[0]?.slug
  return (
    <div className="app">
      <Header title="boredroom.xlsx" meta="what's new" back="/me" />
      <Fx fn="releases" args={[['newest', 'first']]} />
      {err ? <Trouble err={err} retry={load} /> : !rs ? <Ghost what="what's new" rows={4} /> : (
        <div className="bd">
          {rs.map((r, k) => (
            <div key={r.id} id={r.id} className={`rel${k === 0 ? ' latest' : ''}`}>
              <div className="rel-h"><b>{r.title}</b><span className="rel-d">{releaseDay(r.id)}</span></div>
              <ul>{r.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
              {replies.filter(x => x.release === r.id).map((x, i) => (
                <div key={i} className="rel-you">
                  <div className="rel-you-h">for you · re: your {x.kind === 'bug' ? 'bug report' : 'idea'}</div>
                  <blockquote>{x.text}</blockquote>
                  <p>{x.reply}</p>
                  <div className="rel-you-s">— the developer</div>
                </div>
              ))}
            </div>
          ))}
          <button className="go" onClick={() => go('/feedback')}><span className="k">found a bug, or want something?</span><span className="v">send a note</span></button>
        </div>
      )}
      <Nav slug={slug} on="you" temp="what's new" />
    </div>
  )
}

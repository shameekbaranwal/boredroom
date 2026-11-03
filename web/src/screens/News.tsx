import { useEffect, useState } from 'react'
import { api, type Release } from '../api'
import { go } from '../router'
import { Fx, Ghost, Header, Nav, Trouble, useApp } from '../ui'

const LAST = 'boredroom.board'
const lastBoard = () => { try { return localStorage.getItem(LAST) } catch { return null } }

/** The day a release went out, the way the minutes say a day: "3 nov". */
export const releaseDay = (id: string) =>
  new Date(id + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).toLowerCase()

/** What's new: every release, newest first. Opening it reads them all. */
export default function News() {
  const { me, refreshMe } = useApp()
  const [rs, setRs] = useState<Release[] | null>(null)
  const [err, setErr] = useState('')
  const load = () => api.news().then(x => {
    setRs(x.releases); setErr('')
    if (x.releases[0] && x.releases[0].id !== x.seen) api.newsSeen(x.releases[0].id).then(refreshMe).catch(() => {})
  }).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  const slug = me.boards.find(b => b.slug === lastBoard())?.slug ?? me.boards[0]?.slug
  return (
    <div className="app">
      <Header title="boredroom.xlsx" meta="what's new" back="/me" />
      <Fx fn="releases" args={[['newest', 'first']]} />
      {err ? <Trouble err={err} retry={load} /> : !rs ? <Ghost what="what's new" rows={4} /> : (
        <div className="bd">
          {rs.map((r, k) => (
            <div key={r.id} className={`rel${k === 0 ? ' latest' : ''}`}>
              <div className="rel-h"><b>{r.title}</b><span className="rel-d">{releaseDay(r.id)}</span></div>
              <ul>{r.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </div>
          ))}
          <button className="go" onClick={() => go('/feedback')}><span className="k">found a bug, or want something?</span><span className="v">send a note</span></button>
        </div>
      )}
      <Nav slug={slug} on="you" temp="what's new" />
    </div>
  )
}

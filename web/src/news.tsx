import { api } from './api'
import { go } from './router'
import { useApp } from './ui'

/** The agenda's card while a release is news to you: its title and first line, then
 *  "read it" (the whole page) or "noted" (gone till the next release). */
export function NewsMemo() {
  const { me, refreshMe } = useApp()
  const r = me.news
  if (!r) return null
  const done = () => api.newsSeen(r.id).then(refreshMe).catch(() => {})
  return (
    <div className="memo">
      <div className="memo-h"><span>memo</span><span>from: the developer</span><span>re: what's new</span></div>
      <b>{r.title}</b>
      {r.notes[0] && <small>{r.notes[0]}{r.notes.length > 1 ? ` and ${r.notes.length - 1} more.` : ''}</small>}
      <div className="row-a">
        <button className="btn" onClick={() => go('/news')}>read it</button>
        <button className="lnk" onClick={done}>noted</button>
      </div>
    </div>
  )
}

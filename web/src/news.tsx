import { api } from './api'
import { go } from './router'
import { releaseDay } from './screens/News'
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
      <small>{r.notes.length} {r.notes.length === 1 ? 'change' : 'changes'}, out {releaseDay(r.id)}. any time from the "you" tab, on its "everywhere" sheet.</small>
      <div className="row-a">
        <button className="btn" onClick={() => go('/news')}>read it</button>
        <button className="lnk" onClick={done}>noted</button>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api, type Note } from '../api'
import { Fx, Header, Nav, useApp } from '../ui'
import { releaseDay } from './News'

const LAST = 'boredroom.board'
const lastBoard = () => { try { return localStorage.getItem(LAST) } catch { return null } }

/** A note to the developer: a bug or an idea, and the ones you've sent. */
export default function Feedback() {
  const { me, toast } = useApp()
  const [kind, setKind] = useState<Note['kind']>('bug')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [notes, setNotes] = useState<Note[] | null>(null)
  useEffect(() => { api.notes().then(setNotes).catch(() => setNotes([])) }, [])
  const slug = me.boards.find(b => b.slug === lastBoard())?.slug ?? me.boards[0]?.slug ?? null
  const send = async () => {
    if (!text.trim() || busy) return
    setBusy(true)
    try { setNotes(await api.sendNote(kind, text, slug)); setText(''); toast('sent. the developer reads every one.') }
    catch (e) { toast((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="app">
      <Header title="boredroom.xlsx" meta="a note" back="/me" />
      <Fx fn="note" args={[['to', 'the developer'], ['about', kind === 'bug' ? 'a bug' : 'an idea']]} />
      <div className="bd">
        <div className="seg two" role="radiogroup" aria-label="what kind of note">
          {(['bug', 'idea'] as const).map(k => (
            <button key={k} role="radio" aria-checked={kind === k} className={kind === k ? 'on' : ''} onClick={() => setKind(k)}>
              {k === 'bug' ? 'something broke' : 'an idea'}
            </button>
          ))}
        </div>
        <label className="note-w">
          <textarea className="keep" rows={5} maxLength={2000} value={text} onChange={e => setText(e.target.value)} aria-label="your note"
            placeholder={kind === 'bug' ? 'what happened, and what you expected. which game or screen?' : 'what would make boredroom better for you?'} />
          <small className="muted">{text.length > 1800 ? `${2000 - text.length} left · ` : ''}the developer sees your username{slug ? `, the board you were last on` : ''} and your browser, nothing else.</small>
        </label>
        <div className="row-a"><button className="btn" onClick={send} disabled={!text.trim() || busy}>{busy ? 'sending…' : 'send'}</button></div>

        {notes && notes.length > 0 && <>
          <div className="sec">your notes</div>
          {notes.map(n => (
            <div key={n.id} className="note">
              <small className="muted">{n.kind === 'bug' ? 'bug' : 'idea'} · {releaseDay(n.sent_at.slice(0, 10))}{n.board ? ` · from ${n.board}` : ''}</small>
              <div className="keep">{n.text}</div>
            </div>
          ))}
        </>}
      </div>
      <Nav slug={slug ?? undefined} on="you" temp="a note" />
    </div>
  )
}

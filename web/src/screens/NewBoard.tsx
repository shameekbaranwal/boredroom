import { useState } from 'react'
import { api } from '../api'
import { go } from '../router'
import { useApp } from '../ui'
import { Room } from './SignIn'

export default function NewBoard() {
  const { me, refreshMe, signOut } = useApp()
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const make = async () => {
    try { const b = await api.newBoard(name); await refreshMe(); go(`/b/${b.slug}/you?welcome=1`, true) } catch (e) { setErr((e as Error).message) }
  }
  return (
    <div className="signin">
      <Room top="a new board" big={name.trim().toLowerCase() || 'untitled'} bottom={`chaired by ${me.username}`} />
      <section className="pitch">
        <h1>convene a new board.</h1>
        <p>name it, then send its invite to your friends. it's three words, easy to say out loud.</p>
        <div className="acts">
          <div className="field">
            <label htmlFor="n">board name</label>
            <input id="n" className="input" value={name} onChange={e => setName(e.target.value)} placeholder="soup" autoFocus onKeyDown={e => e.key === 'Enter' && make()} />
          </div>
          <button className="btn wide" onClick={make} disabled={!name.trim()}>start the board</button>
          <button className="alt" onClick={() => go('/')}>← back</button>
          {err && <div className="err">{err}</div>}
          <div className="fine"><span>{me.username}</span><span>·</span><button className="lnk" onClick={signOut}>sign out</button></div>
        </div>
      </section>
    </div>
  )
}

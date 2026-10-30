import { useState } from 'react'
import { api } from '../api'
import { go } from '../router'
import { useApp } from '../ui'

export default function NewBoard() {
  const { me, refreshMe } = useApp()
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const make = async () => {
    try { const b = await api.newBoard(name); await refreshMe(); go(`/b/${b.slug}/you?welcome=1`, true) } catch (e) { setErr((e as Error).message) }
  }
  return (
    <div className="app">
      <div className="hd">{me.boards.length > 0 && <button className="back" onClick={() => history.back()} aria-label="back">‹</button>}<span className="t">new board.xlsx</span></div>
      <div className="center">
        <div className="big">{me.boards.length ? 'convene a new board' : `welcome, ${me.username}. you're not on a board yet.`}</div>
        <div className="muted">ask a friend for their board's invite link, or start one and send yours.</div>
        <div className="field">
          <label htmlFor="n">board name</label>
          <input id="n" className="input" value={name} onChange={e => setName(e.target.value)} placeholder="soup" onKeyDown={e => e.key === 'Enter' && make()} />
        </div>
        <button className="btn wide" onClick={make} disabled={!name.trim()}>start the board</button>
        {err && <div className="err">{err}</div>}
      </div>
    </div>
  )
}

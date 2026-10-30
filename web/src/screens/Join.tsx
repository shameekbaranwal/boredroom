import { useEffect, useState } from 'react'
import { api, type Invite } from '../api'
import { go } from '../router'
import { useApp } from '../ui'

export default function Join({ code }: { code: string }) {
  const { me, refreshMe } = useApp()
  const [inv, setInv] = useState<Invite | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.invite(code).then(setInv).catch(e => setErr(e.message)) }, [code])
  const already = inv && me.boards.some(b => b.slug === inv.slug)
  const join = async () => {
    try { const b = await api.join(code); await refreshMe(); go(`/b/${b.slug}/you?welcome=1`, true) } catch (e) { setErr((e as Error).message) }
  }
  return (
    <div className="app">
      <div className="hd"><span className="t">invitation.xlsx</span></div>
      <div className="center">
        {err && <div className="err">{err}</div>}
        {inv && <>
          <div className="big">{inv.chair ?? 'someone'} invited you to the {inv.name} board</div>
          <div className="muted">{inv.members} board members{inv.library.length ? ` · ${inv.library.join(', ')}` : ''}</div>
          {already
            ? <button className="btn wide" onClick={() => go(`/b/${inv.slug}`)}>you're on it · open {inv.name}</button>
            : <button className="btn wide" onClick={join}>join as {me.username}</button>}
        </>}
      </div>
    </div>
  )
}

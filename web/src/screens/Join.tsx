import { useEffect, useState } from 'react'
import { api, type Invite } from '../api'
import { go } from '../router'
import { useApp } from '../ui'
import { Room } from './SignIn'

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
    <div className="signin">
      <Room top="the agenda" big={inv?.name ?? '…'} bottom={inv ? `${inv.members} members` : 'checking the invite'} />
      <section className="pitch">
        {err && <><h1>that invite doesn't work.</h1><p>{err}. ask for a fresh link.</p></>}
        {inv && <>
          <h1>{inv.chair ?? 'someone'} saved you a seat on {inv.name}.</h1>
          <p>{inv.members} members{inv.library.length ? `, playing ${inv.library.slice(0, 4).join(', ')}${inv.library.length > 4 ? ` and ${inv.library.length - 4} more` : ''}` : ''}.</p>
          <div className="acts">
            {already
              ? <button className="btn wide" onClick={() => go(`/b/${inv.slug}`)}>you're on it · open {inv.name}</button>
              : <button className="btn wide" onClick={join}>join as {me.username}</button>}
          </div>
        </>}
      </section>
    </div>
  )
}

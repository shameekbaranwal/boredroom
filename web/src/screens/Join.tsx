import { useEffect, useState } from 'react'
import { api, type Board, type Invite } from '../api'
import { go } from '../router'
import { useApp } from '../ui'
import { Chat, Choice, MailCard } from './SignIn'
import { JoinByCode } from './Desk'

/** An invite, opened while signed in: straight to the board if you're on it already;
 *  otherwise join (or not), then claim an imported seat if one of them is you. */
export default function Join({ code }: { code: string }) {
  const { me, refreshMe, toast } = useApp()
  const [inv, setInv] = useState<Invite | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [pick, setPick] = useState<'join' | 'later'>('join')
  const [joined, setJoined] = useState<Board | null>(null)
  useEffect(() => { api.invite(code).then(setInv).catch(e => setErr(e.message)) }, [code])
  const member = inv && me.boards.some(b => b.slug === inv.slug)
  useEffect(() => { if (member) go(`/b/${inv!.slug}`, true) }, [member, inv])

  const join = async () => {
    setBusy(true); setErr('')
    try {
      const b = await api.join(code)
      await refreshMe()
      if (b.members.some(m => m.kind === 'placeholder')) setJoined(b)
      else go(`/b/${b.slug}/you?welcome=1`, true)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const claim = async (username: string, nickname: string) => {
    setBusy(true)
    try {
      const r = await api.claim(joined!.slug, username)
      await refreshMe(); toast(`welcome back, ${nickname}. ${r.moved} results are yours now.`)
      go(`/b/${joined!.slug}`, true)
    } catch (e) { setErr((e as Error).message); setBusy(false) }
  }

  if (err && !inv) return (
    <MailCard>
      <h1>that invite doesn't work.</h1>
      <p className="mc-pitch">{err}. check the words, or ask for a fresh invite.</p>
      <JoinByCode />
      <button className="alt" onClick={() => go('/')}>not now →</button>
    </MailCard>
  )
  if (!inv || member) return <MailCard><p className="mc-pitch">checking the invite…</p></MailCard>

  if (joined) {
    const seats = joined.members.filter(m => m.kind === 'placeholder')
    return (
      <MailCard>
        <p className="mc-kick">you're on <b>{joined.name}</b> as {me.username}</p>
        <h1>were you here before boredroom?</h1>
        <p className="mc-pitch">{joined.name} brought its chat history along. if one of these is you, claim it and its scores are yours.</p>
        <div className="mc-reply" role="group" aria-label="imported seats">
          {seats.map(s => (
            <Choice key={s.username} on={false} title={s.nickname} sub={`${s.games} games on the agenda`} onPick={() => claim(s.username, s.nickname)}>
              <button className="btn" disabled={busy} onClick={() => claim(s.username, s.nickname)}>that's me</button>
            </Choice>
          ))}
          <Choice on faint title="none of these, i'm new" onPick={() => go(`/b/${joined.slug}/you?welcome=1`, true)} />
        </div>
        {err && <div className="err">{err}</div>}
      </MailCard>
    )
  }

  return (
    <MailCard>
      <p className="mc-kick"><b>{inv.inviter ?? inv.chair ?? 'someone'}</b> saved you a seat on <b>{inv.name}</b> · {inv.members} {inv.members === 1 ? 'member' : 'members'}</p>
      <h1>there's an empty chair at {inv.name}'s table.</h1>
      <Chat />
      <p className="mc-pitch">
        {inv.library.length ? `${inv.name} plays ${inv.library.slice(0, 4).join(', ')}${inv.library.length > 4 ? ` and ${inv.library.length - 4} more` : ''}. ` : ''}
        your results so far come with you.
      </p>
      <div className="mc-reply" role="radiogroup" aria-label="reply with one">
        <small>reply with one</small>
        <Choice on={pick === 'join'} title={`take the seat as ${me.username}`} sub="you can change your name on the board after" onPick={() => setPick('join')}>
          <button className="btn" onClick={join} disabled={busy}>join {inv.name}</button>
        </Choice>
        <Choice on={pick === 'later'} faint title="not now" onPick={() => go('/')} />
      </div>
      {err && <div className="err">{err}</div>}
    </MailCard>
  )
}

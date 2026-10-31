import { useEffect, useState } from 'react'
import { api, type Invite } from '../api'
import { go } from '../router'
import { useApp } from '../ui'
import { Chat, Choice, MailCard, arrivedFor } from './SignIn'
import { JoinByCode } from './Desk'

const SHOWN = 5  // imported seats listed before "n more"

/** An invite, opened while signed in: straight to the board if you're on it already;
 *  otherwise one page to take a new seat, or claim an imported one, or not now. */
export default function Join({ code }: { code: string }) {
  const { me, refreshMe, toast } = useApp()
  const [inv, setInv] = useState<Invite | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [pick, setPick] = useState('')  // '' is a new seat; else the imported seat's username
  const [all, setAll] = useState(false)
  const [arrived] = useState(() => arrivedFor(code))
  useEffect(() => { api.invite(code).then(setInv).catch(e => setErr(e.message)) }, [code])
  const member = inv && me.boards.some(b => b.slug === inv.slug)
  useEffect(() => { if (member) go(`/b/${inv!.slug}`, true) }, [member, inv])

  const join = async () => {
    setBusy(true); setErr('')
    try {
      const b = await api.join(code, pick || undefined)
      try { sessionStorage.removeItem('boredroom.arrived') } catch { /* fine */ }
      await refreshMe()
      if (pick) { toast(`welcome back, ${b.you.nickname}. your history on ${b.name} is yours now.`); go(`/b/${b.slug}`, true) }
      else go(`/b/${b.slug}/you?welcome=1`, true)
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

  const seats = inv.seats
  const shown = all || seats.length <= SHOWN + 1 ? seats : seats.slice(0, SHOWN)
  const go_ = (label: string) => <button className="btn" onClick={join} disabled={busy}>{label}</button>

  return (
    <MailCard>
      {arrived && seats.length
        ? <>
            <p className="mc-kick">signed in as <b>{me.username}</b>. one more thing.</p>
            <h1>were you in {inv.name}'s group chat before boredroom?</h1>
            <p className="mc-pitch">{inv.name} brought its chat history along. if one of these seats is you, claim it and its scores come with it.</p>
          </>
        : <>
            <p className="mc-kick"><b>{inv.inviter ?? inv.chair ?? 'someone'}</b> saved you a seat on <b>{inv.name}</b> · {inv.members} {inv.members === 1 ? 'member' : 'members'}</p>
            <h1>there's an empty seat at {inv.name}'s table.</h1>
            <Chat />
            <p className="mc-pitch">
              {inv.library.length ? `${inv.name} plays ${inv.library.slice(0, 4).join(', ')}${inv.library.length > 4 ? ` and ${inv.library.length - 4} more` : ''}. ` : ''}
              your results so far come with you.
            </p>
          </>}
      <div className="mc-reply" role="radiogroup" aria-label="reply with one">
        <small>reply with one</small>
        <Choice on={pick === ''} title={`a new seat, as ${me.username}`} sub="you can change your name on the board after" onPick={() => setPick('')}>
          {pick === '' && go_(`join ${inv.name}`)}
        </Choice>
        {seats.length > 0 && <small className="mc-or">or claim your seat from the chat history</small>}
        {shown.map(s => (
          <Choice key={s.username} on={pick === s.username} title={`i'm ${s.nickname}`} sub={`${s.results} ${s.results === 1 ? 'result' : 'results'} filed from the chat`} onPick={() => setPick(s.username)}>
            {pick === s.username && go_("that's me")}
          </Choice>
        ))}
        {shown.length < seats.length && <button className="alt mc-more" onClick={() => setAll(true)}>{seats.length - shown.length} more seats from the chat ↓</button>}
        <Choice on={false} faint title="not now" onPick={() => go('/')} />
      </div>
      {err && <div className="err">{err}</div>}
    </MailCard>
  )
}

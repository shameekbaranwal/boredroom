import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, setToken, type Leaving } from '../api'
import { Fx, Header, Nav, useApp } from '../ui'
import { setPref, useTheme, type Pref } from '../theme'
import { GoogleButton } from './SignIn'
import { InstallMemo, standalone } from '../install'

/** Settings that belong to the person rather than a board: timezone, appearance,
 *  the account, and signing out. On every board's "you" screen, and on /me. */
export function Personal({ guestOnly = false, deleting = false }: { guestOnly?: boolean; deleting?: boolean }) {
  const { me, refreshMe, toast, signOut } = useApp()
  const [theme] = useTheme()
  const [tz, setTz] = useState(me.tz)
  const [user, setUser] = useState(me.username)
  const saveUser = async () => {
    const v = user.trim().toLowerCase()
    if (!v || v === me.username) { setUser(me.username); return }
    try { await api.updateMe({ username: v }); await refreshMe(); toast(`you're ${v} now. your names on boards stay as they are.`) }
    catch (e) { toast((e as Error).message); setUser(me.username) }
  }

  const deviceTz = Intl.DateTimeFormat().resolvedOptions().timeZone
  const browserTz = OLD_ZONES[deviceTz] ?? deviceTz
  // chrome lists some zones by their old names (asia/calcutta); show the current ones
  const zones = useMemo(() => {
    const all = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.('timeZone') ?? []
    const fixed = all.map(z => OLD_ZONES[z] ?? z)
    return fixed.includes(me.tz) ? fixed : [me.tz, ...fixed]
  }, [me.tz])
  const saveTz = async (v: string) => {
    setTz(v)
    try { await api.updateMe({ tz: v }); refreshMe(); toast(`timezone set to ${v}`) } catch (e) { toast((e as Error).message) }
  }

  // a guest's seat lives on this one device; signing in is what keeps it
  const guestCard = me.kind === 'guest' && (
    <div className="card guest-card">
      <b>you're a guest, as {me.username}, on this device only.</b>
      <small>sign in with google to keep your seat and scores on every device. nothing you've filed is lost.</small>
      <GoogleButton onToken={t => { setToken(t); refreshMe(); toast('signed in. your guest seat is now your account.') }} onError={m => toast(m)} />
    </div>
  )
  if (guestOnly) return guestCard || null

  return <>
    <div className="field">
      <label htmlFor="user">username <span className="muted">· yours alone across boredroom; boards can call you something else</span></label>
      <input id="user" className="input keep" value={user} onChange={e => setUser(e.target.value)} onBlur={saveUser}
        onKeyDown={e => e.key === 'Enter' && saveUser()} autoCapitalize="none" autoComplete="off" spellCheck={false} />
    </div>
    <div className="field">
      <label htmlFor="tz">timezone {tz !== browserTz && <span className="muted">(this device says {browserTz})</span>}</label>
      {zones.length
        ? <select id="tz" className="input" value={tz} onChange={e => saveTz(e.target.value)}>{zones.map(z => <option key={z} value={z}>{z}</option>)}</select>
        : <input id="tz" className="input" value={tz} onChange={e => setTz(e.target.value)} onBlur={() => saveTz(tz)} />}
    </div>
    <div className="field">
      <label>appearance</label>
      <div className="seg" role="radiogroup" aria-label="appearance">
        {(['system', 'light', 'dark'] as Pref[]).map(p => (
          <button key={p} role="radio" aria-checked={theme === p} className={theme === p ? 'on' : ''} onClick={() => setPref(p)}>
            {p === 'system' ? 'like this device' : p}
          </button>
        ))}
      </div>
    </div>
    {me.kind === 'account'
      ? <div className="mrow"><span>signed in as {me.username}{me.email && <span className="muted keep"> · {me.email}</span>}</span><span className="chip">google</span></div>
      : guestCard}
    {standalone() ? <div className="mrow"><span>boredroom is on this device's home screen</span><span className="chip">installed</span></div> : <InstallMemo always />}
    <div><button className="lnk" onClick={signOut}>sign out</button></div>
    <DeleteAccount open={deleting} />
  </>
}

/** A motion that can't be taken back: a quiet red row that opens in place into what will
 *  happen, a yes and a no. Esc or "no" folds it again. */
export function Motion({ label, heading, children, yes, no, busy, err, ready = true, onYes, foot, open: start = false }: {
  label: string; heading: string; children: ReactNode; yes: string; no: string; busy: boolean; err: string
  ready?: boolean; onYes: () => void; foot?: ReactNode; open?: boolean
}) {
  const [open, setOpen] = useState(start)
  const row = useRef<HTMLButtonElement>(null)
  const head = useRef<HTMLHeadingElement>(null)
  useEffect(() => { if (open) head.current?.focus() }, [open])
  const close = () => { setOpen(false); setTimeout(() => row.current?.focus(), 0) }
  if (!open) return <div><button ref={row} className="lnk bad" onClick={() => setOpen(true)}>{label}</button></div>
  return (
    <div className="motion" onKeyDown={e => e.key === 'Escape' && !busy && close()}>
      <h3 ref={head} tabIndex={-1}>{heading}</h3>
      {children}
      <div className="row-a">
        <button className="btn danger" disabled={busy || !ready} onClick={onYes}>{yes}</button>
        <button className="lnk" disabled={busy} onClick={close}>{no}</button>
      </div>
      {err && <small className="err">{err}</small>}
      {foot}
    </div>
  )
}

const names = (xs: Leaving[]) => xs.map(x => x.name).join(', ')

/** Deleting the account: every board, said out loud first, and the username typed back. */
function DeleteAccount({ open }: { open: boolean }) {
  const { me, refreshMe, toast } = useApp()
  const [boards, setBoards] = useState<Leaving[] | null>(null)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  useEffect(() => { api.leaving().then(setBoards).catch(() => setBoards([])) }, [])
  const go = async () => {
    setBusy(true); setErr('')
    try {
      await api.closeAccount(me.username)
      setToken(null)
      toast('account deleted. the board thanks you for your service.')
      history.replaceState(null, '', '/')
      await refreshMe().catch(() => {})
    } catch (e) { setErr((e as Error).message); setBusy(false) }
  }
  const bs = boards ?? []
  const claimed = bs.filter(x => x.claimed), chaired = bs.filter(x => x.chair && !x.alone), alone = bs.filter(x => x.alone)
  return (
    <Motion key={String(open)} open={open} label="delete your account" heading={`motion to wind up ${me.username}`}
      yes={busy ? 'deleting…' : 'delete everything'} no="no, keep me" busy={busy} err={err}
      ready={typed.trim().toLowerCase() === me.username} onYes={go}>
      {bs.length > 0 && <p>you leave every board you're on: {names(bs)}.</p>}
      <p>the results you filed are struck from every board's minutes.</p>
      {claimed.length > 0 && <p>seats you claimed go back to being unclaimed, imported history and all, on {names(claimed)}.</p>}
      {chaired.length > 0 && <p>you hold the chair on {names(chaired)}. {chaired.length === 1 ? 'it passes' : 'each passes'} to {chaired.map(x => x.heir).join(', ')}.</p>}
      {alone.length > 0 && <p>{names(alone)} {alone.length === 1 ? 'has' : 'have'} no other members and will be dissolved.</p>}
      <p className="muted">{me.kind === 'account' ? 'signing in with google again starts a fresh account.' : 'this device forgets you.'}</p>
      <div className="field">
        <label htmlFor="confirm">type <b className="keep">{me.username}</b> to confirm</label>
        <input id="confirm" className="input keep" value={typed} onChange={e => setTyped(e.target.value)} autoCapitalize="none" autoComplete="off" spellCheck={false} />
      </div>
    </Motion>
  )
}

/** "you" when you're not on a board yet. */
export default function MeScreen() {
  const { me } = useApp()
  return (
    <div className="app">
      <Header title="you.xlsx" meta={me.username} />
      <Fx fn="seat" args={[['boards', 'none yet']]} />
      <div className="bd"><div className="sec">you</div><Personal /></div>
      <Nav on="you" />
    </div>
  )
}

const OLD_ZONES: Record<string, string> = { 'Asia/Calcutta': 'Asia/Kolkata', 'Asia/Saigon': 'Asia/Ho_Chi_Minh', 'Asia/Katmandu': 'Asia/Kathmandu', 'Asia/Rangoon': 'Asia/Yangon', 'Europe/Kiev': 'Europe/Kyiv' }

import { useMemo, useState } from 'react'
import { api, setToken } from '../api'
import { Fx, Header, Nav, useApp } from '../ui'
import { setPref, useTheme, type Pref } from '../theme'
import { GoogleButton } from './SignIn'
import { InstallMemo, standalone } from '../install'

/** Settings that belong to the person rather than a board: timezone, appearance,
 *  the account, and signing out. On every board's "you" screen, and on /me. */
export function Personal({ guestOnly = false }: { guestOnly?: boolean }) {
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
  </>
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

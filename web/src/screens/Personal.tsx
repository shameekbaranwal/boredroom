import { useMemo, useState } from 'react'
import { api, setToken } from '../api'
import { Fx, Header, Nav, useApp } from '../ui'
import { setPref, useTheme, type Pref } from '../theme'
import { GoogleButton } from './SignIn'

/** Settings that belong to the person rather than a board: timezone, appearance,
 *  the account, and signing out. On every board's "you" screen, and on /me. */
export function Personal() {
  const { me, refreshMe, toast, signOut } = useApp()
  const [theme] = useTheme()
  const [tz, setTz] = useState(me.tz)

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

  return <>
    <div className="sec">you</div>
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
    <div className="mrow">
      <span>{me.kind === 'account' ? <>signed in{me.email && <span className="muted keep"> · {me.email}</span>}</> : 'guest seat on this device'}</span>
      <span className={`chip${me.kind === 'guest' ? ' seat' : ''}`}>{me.kind === 'account' ? 'signed in' : 'guest seat'}</span>
    </div>
    {me.kind === 'guest' && (
      <div className="field">
        <label>keep this seat: sign in with google</label>
        <GoogleButton onToken={t => { setToken(t); refreshMe(); toast('signed in. your guest seat is now your account.') }} onError={m => toast(m)} />
      </div>
    )}
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
      <div className="bd"><Personal /></div>
      <Nav on="you" />
    </div>
  )
}

const OLD_ZONES: Record<string, string> = { 'Asia/Calcutta': 'Asia/Kolkata', 'Asia/Saigon': 'Asia/Ho_Chi_Minh', 'Asia/Katmandu': 'Asia/Kathmandu', 'Asia/Rangoon': 'Asia/Yangon', 'Europe/Kiev': 'Europe/Kyiv' }

import { useEffect, useRef, useState } from 'react'
import { api, setToken, type Invite } from '../api'

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void }) => void
      renderButton: (el: HTMLElement, o: Record<string, unknown>) => void
    } } }
  }
}

let gsi: Promise<void> | null = null
function loadGsi(): Promise<void> {
  gsi ??= new Promise((ok, fail) => {
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.async = true
    s.onload = () => ok()
    s.onerror = () => { gsi = null; fail(new Error("google sign-in didn't load")) }
    document.head.appendChild(s)
  })
  return gsi
}

/** Google's button. Signed in as a guest, signing in turns the seat into the account. */
export function GoogleButton({ onToken, onError }: { onToken: (t: string) => void; onError: (m: string) => void }) {
  const el = useRef<HTMLDivElement>(null)
  const [off, setOff] = useState(false)
  useEffect(() => {
    let live = true
    api.config().then(async c => {
      if (!c.google_client_id) { if (live) setOff(true); return }
      await loadGsi()
      if (!live || !el.current || !window.google) return
      window.google.accounts.id.initialize({
        client_id: c.google_client_id,
        callback: r => api.google(r.credential).then(x => onToken(x.token)).catch(e => onError(e.message)),
      })
      const dark = matchMedia('(prefers-color-scheme: dark)').matches
      window.google.accounts.id.renderButton(el.current, { theme: dark ? 'filled_black' : 'outline', size: 'large', text: 'continue_with', width: 280 })
    }).catch(e => live && onError(e.message))
    return () => { live = false }
  }, [onToken, onError])
  if (off) return <div className="muted">google sign-in isn't set up on this server.</div>
  return <div ref={el} className="keep" style={{ minHeight: 44 }} />
}

export default function SignIn({ invite, onSignedIn }: { invite?: Invite | null; onSignedIn: () => void }) {
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const done = (t: string) => { setToken(t); onSignedIn() }
  const guest = async () => {
    setBusy(true); setErr('')
    try { done((await api.guest(name.trim() || undefined)).token) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="app">
      <div className="hd"><span className="t">boredroom.xlsx</span><span className="m">sign in</span></div>
      <div className="center">
        {invite
          ? <><div className="big">{invite.chair ?? 'someone'} invited you to the {invite.name} board</div>
              <div className="muted">{invite.members} board members{invite.library.length ? ` · ${invite.library.slice(0, 3).join(', ')}${invite.library.length > 3 ? ` and ${invite.library.length - 3} more` : ''}` : ''}</div></>
          : <><div className="big">the minutes of your friends' daily puzzles.</div>
              <div className="muted">paste your result like you always do. the board keeps the standings.</div></>}
        <GoogleButton onToken={done} onError={setErr} />
        <div className="field">
          <label htmlFor="g">or take a guest seat</label>
          <input id="g" className="input" placeholder="pick a username" value={name} onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && guest()} autoCapitalize="none" autoComplete="off" spellCheck={false} />
          <button className="btn ghost" onClick={guest} disabled={busy}>continue as a guest</button>
          <span className="muted" style={{ fontSize: 13 }}>a guest seat lives on this device. sign in with google later to keep it.</span>
        </div>
        {err && <div className="err">{err}</div>}
        <div className="muted" style={{ fontSize: 13 }}><a href="/privacy">privacy</a> · <a href="/terms">terms</a></div>
      </div>
    </div>
  )
}

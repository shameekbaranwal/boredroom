import { useEffect, useRef, useState } from 'react'
import { api, setToken, type Invite } from '../api'
import { ThemeToggle, Wordmark } from '../brand'
import { useTheme } from '../theme'

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

/** Google's own button, drawn by Google: full width (it caps at 400 px), pill-shaped,
 *  and redrawn in Google's dark style when the page is dark. Signed in as a guest,
 *  signing in turns the seat into the account. */
export function GoogleButton({ onToken, onError }: { onToken: (t: string) => void; onError: (m: string) => void }) {
  const el = useRef<HTMLDivElement>(null)
  const [, shown] = useTheme()
  const [clientId, setClientId] = useState<string | null | undefined>(undefined)
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const cb = useRef({ onToken, onError })
  cb.current = { onToken, onError }

  // google draws the button at a fixed pixel width, so redraw it when its box resizes
  useEffect(() => {
    if (!box.current) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width / 10) * 10))
    ro.observe(box.current)
    return () => ro.disconnect()
  }, [])

  useEffect(() => { api.config().then(c => setClientId(c.google_client_id)).catch(e => cb.current.onError(e.message)) }, [])
  useEffect(() => {
    if (!clientId || !width) return
    let live = true
    loadGsi().then(() => {
      if (!live || !el.current || !window.google) return
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: r => api.google(r.credential).then(x => cb.current.onToken(x.token)).catch(e => cb.current.onError(e.message)),
      })
      // draw the new button in a fresh layer on top, and drop the old one once google's
      // frame has loaded; clearing first made the button collapse and jump
      const host = el.current
      const layer = document.createElement('div')
      layer.className = 'glayer'
      host.appendChild(layer)
      window.google.accounts.id.renderButton(layer, {
        theme: shown === 'dark' ? 'filled_black' : 'outline', size: 'large', shape: 'pill',
        text: 'continue_with', logo_alignment: 'center', width: Math.max(200, Math.min(400, width)),
      })
      setTimeout(() => { if (live) for (const old of [...host.children]) if (old !== layer) old.remove() }, 700)
    }).catch(e => live && cb.current.onError(e.message))
    return () => { live = false }
  }, [clientId, shown, width])

  if (clientId === null) return <div className="muted">google sign-in isn't set up on this server.</div>
  return <div className="gbtn keep" ref={box}><div ref={el} /></div>
}

// the board around the table, clockwise from the top left; the ninth seat is yours
const SEATS: [string, number, number][] = [
  ['alice', 30, 19.3], ['bob', 50, 16.7], ['charlie', 70, 19.3], ['dave', 89.1, 40],
  ['ellie', 89.1, 60.7], ['felix', 70, 81.3], ['grace', 50, 84], ['hal', 30, 81.3], ['you?', 10.3, 50],
]

export default function SignIn({ invite, onSignedIn }: { invite?: Invite | null; onSignedIn: () => void }) {
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [guestOpen, setGuestOpen] = useState(false)
  const [games, setGames] = useState<number | null>(null)
  useEffect(() => { api.games().then(g => setGames(g.length)).catch(() => {}) }, [])

  const done = (t: string) => { setToken(t); onSignedIn() }
  const guest = async () => {
    setBusy(true); setErr('')
    try { done((await api.guest(name.trim() || undefined)).token) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="signin">
      <Room top={invite ? "the agenda" : "today's agenda"} big={invite ? invite.name : games ? `${games} puzzles` : 'the puzzles'} bottom={invite ? `${invite.members} members` : 'the board is in session'} />
      <section className="pitch">
        {invite
          ? <><h1>{invite.chair ?? 'someone'} saved you a seat on {invite.name}.</h1>
              <p>{invite.members} members{invite.library.length ? `, playing ${invite.library.slice(0, 3).join(', ')}${invite.library.length > 3 ? ` and ${invite.library.length - 3} more` : ''}` : ''}. sign in to take your seat.</p></>
          : <><h1>there's an empty chair at your friends' table.</h1>
              <p>paste your daily puzzles like you always do. boredroom keeps the minutes, the scores, and the receipts.</p></>}
        <div className="acts">
          <GoogleButton onToken={done} onError={setErr} />
          {!guestOpen
            ? <button className="alt" onClick={() => setGuestOpen(true)}>or take a guest seat →</button>
            : <>
                <div className="guest">
                  <label htmlFor="g" className="sr">username</label>
                  <input id="g" className="input" placeholder="pick a username" value={name} autoFocus
                    onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && guest()}
                    autoCapitalize="none" autoComplete="off" spellCheck={false} />
                  <button className="btn" onClick={guest} disabled={busy}>join</button>
                </div>
                <span className="muted" style={{ fontSize: 13 }}>a guest seat lives on this device. sign in with google later to keep it.</span>
              </>}
          {err && <div className="err">{err}</div>}
          <div className="fine"><a href="/privacy">privacy</a><span>·</span><a href="/terms">terms</a></div>
        </div>
      </section>
    </div>
  )
}

/** The green room with the table and its seats: the left half of the welcome pages. */
export function Room({ top, big, bottom }: { top: string; big: string; bottom: string }) {
  return (
    <section className="room" aria-label="the boardroom">
      <div className="room-top">
        <Wordmark onRoom />
        <ThemeToggle />
      </div>
      <div className="table-wrap" aria-hidden="true">
        <div className="table-top"><small>{top}</small><b>{big}</b><small>{bottom}</small></div>
        {SEATS.map(([n, x, y], i) => (
          <span key={n} className={`seat${n === 'you?' ? ' you' : ''}`} style={{ left: `${x}%`, top: `${y}%`, ['--i' as string]: i }}>{n}</span>
        ))}
      </div>
    </section>
  )
}

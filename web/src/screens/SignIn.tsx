import { useUsernameCheck } from '../username'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api, setToken, type Invite, type SignedIn } from '../api'
import { TableMark, ThemeToggle, Wordmark } from '../brand'
import { hue } from '../format'
import { go } from '../router'

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

/** Google's own button, drawn by Google: full width (it caps at 400 px) and pill-shaped.
 *  Both of Google's styles are drawn up front and the stylesheet shows the one that matches
 *  the page, so a theme change never redraws Google's frames. Signed in as a guest,
 *  signing in turns the seat into the account. */
export function GoogleButton({ onToken, onError }: { onToken: (t: string, signed: SignedIn) => void; onError: (m: string) => void }) {
  const el = useRef<HTMLDivElement>(null)
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
      const gid = window.google.accounts.id
      gid.initialize({
        client_id: clientId,
        callback: r => api.google(r.credential).then(x => cb.current.onToken(x.token, x)).catch(e => cb.current.onError(e.message)),
      })
      // draw the new pair in a fresh layer on top, and drop the old one once google's
      // frames have loaded; clearing first made the button collapse and jump
      const host = el.current
      const layer = document.createElement('div')
      layer.className = 'glayer'
      for (const theme of ['outline', 'filled_black']) {
        const b = document.createElement('div')
        b.className = theme === 'outline' ? 'g-light' : 'g-dark'
        layer.appendChild(b)
        gid.renderButton(b, {
          theme, size: 'large', shape: 'pill', text: 'continue_with', logo_alignment: 'center',
          width: Math.max(200, Math.min(400, width)),
        })
      }
      host.appendChild(layer)
      setTimeout(() => { if (live) for (const old of [...host.children]) if (old !== layer) old.remove() }, 700)
    }).catch(e => live && cb.current.onError(e.message))
    return () => { live = false }
  }, [clientId, width])

  if (clientId === null) return <div className="muted">google sign-in isn't set up on this server.</div>
  return <div className="gbtn keep" ref={box}><div ref={el} /></div>
}

// the board around the table, clockwise from the top left; the ninth seat is yours
const SEATS: [string, number, number][] = [
  ['alice', 30, 19.3], ['bob', 50, 16.7], ['charlie', 70, 19.3], ['dave', 89.1, 40],
  ['ellie', 89.1, 60.7], ['felix', 70, 81.3], ['grace', 50, 84], ['hal', 30, 81.3], ['you?', 10.3, 50],
]

// a morning in somebody's group chat; the welcome page shows one at random
type Line = [who: string, said: string]
const CHATS: Line[][] = [
  [['grace', 'connections: purple first try'], ['hal', 'purple first is a cry for help'], ['grace', "it's called confidence, hal"]],
  [['felix', "today's mini was rigged"], ['charlie', 'it took me 41 seconds'], ['felix', 'yes. rigged.']],
  [['charlie', 'wordle 1,960 x/6'], ['dave', 'a moment of silence 🕯️']],
  [['alice', 'spelling bee: genius. stopped there, i have a life'], ['bob', "it's 6:40am"], ['alice', 'and my life starts at 6:41']],
  [['hal', "wait who's actually winning this week"], ['felix', 'me'], ['ellie', "felix has said 'me' every week since march"]],
  [['ellie', 'strands: no hints, spangram second word'], ['charlie', 'who asked'], ['ellie', "you will, at 11pm, when you're stuck"]],
  [['grace', 'mini in 0:52. take your time everyone'], ['bob', "i was about to start and now i simply won't"]],
  [['alice', "we need new blood. dave's been last on the mini for three weeks"], ['dave', "i prefer 'holding the group together'"], ['ellie', 'from the bottom, yes']],
  [['bob', 'wordle in 2 🫡'], ['charlie', "screenshot or it didn't happen"]],
]

export function Chat() {
  const [lines] = useState(() => CHATS[Math.floor(Math.random() * CHATS.length)])
  return (
    <div className="mc-chat" aria-label="from a group chat">
      <small>this morning</small>
      {lines.map(([who, said], i) => (
        <div key={i} className="mc-bub" style={{ ['--h' as string]: hue(who) }}>
          <i aria-hidden="true">{who[0]}</i><span><b>{who}</b>{said}</span>
        </div>
      ))}
    </div>
  )
}

/** The welcome pages are an email from the board: a green band with the logo, then the letter. */
export function MailCard({ children }: { children: ReactNode }) {
  return (
    <div className="mailpage">
      <article className="mailcard">
        <header className="mc-band">
          <TableMark size={34} tile />
          <Wordmark onBand />
          <span className="mc-tag">the minutes, the scores, and the receipts</span>
          <ThemeToggle />
        </header>
        <div className="mc-body">{children}</div>
      </article>
      <div className="fine"><a href="/privacy">privacy</a><span>·</span><a href="/terms">terms</a></div>
    </div>
  )
}

/** One reply on the ballot: a checkbox row that can hold its own action. */
export function Choice({ on, faint, title, sub, onPick, children }: {
  on: boolean; faint?: boolean; title: string; sub?: string; onPick: () => void; children?: ReactNode
}) {
  return (
    <div className={`mc-opt${on ? ' on' : ''}${faint ? ' faint' : ''}`}>
      <button className="mc-pick" role="radio" aria-checked={on} onClick={onPick}>
        <span className="mc-ck" aria-hidden="true" />
        <span className="mc-lbl">{title}{sub && <small>{sub}</small>}</span>
      </button>
      {children && <div className="mc-act">{children}</div>}
    </div>
  )
}

export default function SignIn({ invite, onSignedIn }: { invite?: Invite | null; onSignedIn: () => void }) {
  const [name, setName] = useState('')
  const check = useUsernameCheck(name)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [pick, setPick] = useState<'seat' | 'guest' | 'lurk'>('seat')

  // signing in from an invite is taking the seat: join straight away, unless the board has
  // imported seats, when the next page asks which one (if any) is yours
  const done = async (t: string) => {
    setToken(t)
    if (invite && !invite.seats.length) {
      try { await api.join(invite.code); go(`/b/${invite.slug}/you?welcome=1`, true) } catch { /* the invite page will offer it again */ }
    } else if (invite) justArrived(invite.code)
    onSignedIn()
  }
  const guest = async () => {
    setBusy(true); setErr('')
    try { done((await api.guest(name.trim() || undefined)).token) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <MailCard>
      {invite
        ? <>
            <p className="mc-kick"><b>{invite.inviter ?? invite.chair ?? 'someone'}</b> saved you a seat on <b>{invite.name}</b> · {invite.members} {invite.members === 1 ? 'member' : 'members'}</p>
            <h1>there's an empty seat at {invite.name}'s table.</h1>
          </>
        : <h1>there's an empty seat at your friends' table.</h1>}
      <Chat />
      <p className="mc-pitch">
        paste your daily puzzles like you always do. boredroom keeps the minutes, the scores, and the receipts.
        {invite && invite.library.length > 0 && <> {invite.name} plays {invite.library.slice(0, 3).join(', ')}{invite.library.length > 3 ? ` and ${invite.library.length - 3} more` : ''}.</>}
      </p>
      <div className="mc-reply" role="radiogroup" aria-label="reply with one">
        <small>reply with one</small>
        <Choice on={pick === 'seat'} title="take the seat" sub="your scores follow you to every device" onPick={() => setPick('seat')}>
          <GoogleButton onToken={done} onError={setErr} />
        </Choice>
        <Choice on={pick === 'guest'} title="sit in for now" sub="as a guest, on this device. sign in whenever" onPick={() => setPick('guest')}>
          {pick === 'guest'
            ? <div className="guest">
                <label htmlFor="g" className="sr">username</label>
                <input id="g" className="input" placeholder="a username, yours alone" value={name} autoFocus
                  onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && guest()}
                  autoCapitalize="none" autoComplete="off" spellCheck={false} />
                <button className="btn" onClick={guest} disabled={busy || check.state === 'bad' || check.state === 'taken'}>sit</button>
              </div>
            : <button className="alt" onClick={() => setPick('guest')}>pick a username →</button>}
          {pick === 'guest' && name.trim() && <small className={`ucheck ${check.state}`} aria-live="polite">{check.state === 'free' ? `${name.trim().toLowerCase()} is free` : check.note}</small>}
        </Choice>
        <Choice on={pick === 'lurk'} faint title="keep lurking in the group chat" onPick={() => setPick('lurk')}>
          {pick === 'lurk' && <span className="muted">fair. the seat will be here.</span>}
        </Choice>
      </div>
      {err && <div className="err">{err}</div>}
    </MailCard>
  )
}

// the invite page knows you only just signed in, so it skips straight to picking your seat
const ARRIVED = 'boredroom.arrived'
const justArrived = (code: string) => { try { sessionStorage.setItem(ARRIVED, code) } catch { /* fine */ } }
export function arrivedFor(code: string): boolean {
  try { return sessionStorage.getItem(ARRIVED) === code } catch { return false }
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

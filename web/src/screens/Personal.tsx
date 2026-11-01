import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, setToken, token, type Leaving } from '../api'
import { reseat } from '../outbox'
import { Av, Fx, FxEdit, Header, Nav, goBack, useApp } from '../ui'
import { setPref, useTheme, type Pref } from '../theme'
import { GoogleButton } from './SignIn'
import { useInstall } from '../install'
import { DeviceReminders } from '../reminders'
import { canChooseOpens, opensIn, setOpensIn, standalone, type Opens } from '../opens'
import { useUsernameCheck } from '../username'
import { go } from '../router'

/** Your username, edited in the formula bar. `start` opens it; `fx` is the bar to show
 *  in place of the usual one while it's open. */
export function useUsernameEdit() {
  const { me, refreshMe, toast } = useApp()
  const [v, setV] = useState<string | null>(null)
  const check = useUsernameCheck(v ?? me.username, me.username)
  const [busy, setBusy] = useState(false)
  const save = async () => {
    const name = (v ?? '').trim().toLowerCase()
    if (check.state !== 'free' || busy) return
    setBusy(true)
    try { await api.updateMe({ username: name }); await refreshMe(); setV(null); toast(`you're ${name} now. your names on boards stay as they are.`) }
    catch (e) { toast((e as Error).message) }
    finally { setBusy(false) }
  }
  const note = check.state === 'idle' ? 'type a new username. yours alone across boredroom.'
    : check.state === 'free' ? `${(v ?? '').trim().toLowerCase()} is free. ✓ to take it.` : check.note
  const fx = v === null ? null : (
    <FxEdit fn="you" field="username" value={v} onChange={setV} onSave={save} onCancel={() => setV(null)} max={30}
      ok={check.state === 'free'} busy={busy} note={{ text: note, tone: check.state }} />
  )
  return { start: () => setV(me.username), fx }
}

/** The "everywhere" sheet: your file. Who you are across boredroom, then this device. */
export function YourFile({ onEditName, closeTo }: { onEditName: () => void; closeTo: string }) {
  const { me, refreshMe, toast, signOut } = useApp()
  const [theme] = useTheme()
  const [how, install] = useInstall()
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
    <div className="file">
      <span className="file-tab" aria-hidden="true">file</span>
      <Av name={me.username} />
      <div className="g">
        <button className="file-name keep" onClick={onEditName} aria-label={`username ${me.username}, change it`}>{me.username}<span className="pen" aria-hidden="true">✎</span></button>
        <div className="sub">{me.kind === 'account' ? <>signed in with google{me.email && <span className="keep"> · {me.email}</span>}</> : 'a guest, on this device only'}</div>
        {me.boards.length > 0 && <div className="sub wrap">{me.boards.map(b => b.role === 'chair' ? `${b.name} (chair)` : b.name).join(' · ')}</div>}
      </div>
    </div>
    {me.kind === 'guest' && <GuestNote />}

    <div className="sec">particulars</div>
    <button className="cell go" onClick={onEditName}><span className="k">username</span><span className="v keep">{me.username}</span><span className="pen" aria-hidden="true">✎</span></button>
    <label className="cell">
      <span className="k">timezone{tz !== browserTz && <small className="muted"> · this device says {browserTz}</small>}</span>
      {zones.length
        ? <select className="cell-sel" value={tz} onChange={e => saveTz(e.target.value)}>{zones.map(z => <option key={z} value={z}>{z.toLowerCase()}</option>)}</select>
        : <input className="cell-sel" value={tz} onChange={e => setTz(e.target.value)} onBlur={() => saveTz(tz)} />}
    </label>

    <div className="sec">this device</div>
    <div className="cell">
      <span className="k">appearance</span>
      <div className="seg" role="radiogroup" aria-label="appearance">
        {(['system', 'light', 'dark'] as Pref[]).map(p => (
          <button key={p} role="radio" aria-checked={theme === p} className={theme === p ? 'on' : ''} onClick={() => setPref(p)}>
            {p === 'system' ? 'device' : p}
          </button>
        ))}
      </div>
    </div>
    <div className="cell">
      <span className="k">home screen{how === 'ios' && <small className="muted"> · in safari: share, then add to home screen</small>}</span>
      {standalone() ? <span className="chip badge">installed</span>
        : how === 'prompt' ? <button className="btn sm" onClick={async () => { if (await install()) toast('installed. see you on the home screen.') }}>install</button>
          : <span className="chip">{how === 'ios' ? 'two taps' : 'in the browser'}</span>}
    </div>
    <DeviceReminders />
    {canChooseOpens() && <OpensIn />}
    <div className="cell">
      <span className="k">sign out<small className="muted">{me.kind === 'guest' ? 'a guest seat is lost for good' : 'sign in again with google any time'}</small></span>
      <HoldToSign label="sign out" hint="hold to sign out" tone="ghost" busy={false} ready onDone={signOut} />
    </div>
    <div className="sec">the developer</div>
    <button className="go" onClick={() => go('/news')}>
      <span className="k">what's new{me.news && <span className="dot" aria-label="something new" />}</span><span className="v">{me.news ? me.news.title : 'the release notes'}</span>
    </button>
    <button className="go" onClick={() => go('/feedback')}><span className="k">send a note</span><span className="v">a bug, or an idea</span></button>

    <button className="go bad" onClick={() => go(closeTo)}><span className="k">wind up your account</span></button>
  </>
}

/** Where play links open from the installed app: in it, or in the phone's browser. */
function OpensIn() {
  const [o, setO] = useState<Opens>(opensIn)
  const pick = (v: Opens) => { setOpensIn(v); setO(v) }
  return (
    <div className="cell">
      <span className="k">games open<small className="muted">{o === 'app' ? 'inside boredroom; back is one swipe' : 'in your browser, where you may be signed in'}</small></span>
      <div className="seg" role="radiogroup" aria-label="games open">
        {(['app', 'browser'] as Opens[]).map(v => (
          <button key={v} role="radio" aria-checked={o === v} className={o === v ? 'on' : ''} onClick={() => pick(v)}>
            {v === 'app' ? 'in the app' : 'in the browser'}
          </button>
        ))}
      </div>
    </div>
  )
}

/** A guest's seat lives on this one device; signing in is what keeps it. */
export function GuestNote() {
  const { me, refreshMe, toast } = useApp()
  return (
    <div className="card guest-card">
      <b>you're a guest, as {me.username}, on this device only.</b>
      <small>sign in with google to keep your seat and scores on every device. nothing you've filed is lost.</small>
      <GoogleButton onToken={(t, x) => {
        reseat(token(), t); setToken(t); refreshMe()
        const m = x.merged, n = (k: number, w: string) => `${k} ${w}${k === 1 ? '' : 's'}`
        toast(!m ? 'signed in. your guest seat is now your account.'
          : `signed in as ${x.me.username}. this seat folded into it${m.results || m.boards ? `: ${[m.results && n(m.results, 'result'), m.boards && n(m.boards, 'board')].filter(Boolean).join(' and ')} came along` : ''}.`)
      }} onError={m => toast(m)} />
    </div>
  )
}

/** A motion that can't be taken back, on a page of its own: what will happen, then a red
 *  yes and a plain no. With `sign`, yes is a signature you hold to draw. */
export function Motion({ heading, children, yes, no, busy, err, ready = true, onYes, onNo, foot, sign = false }: {
  heading: string; children: ReactNode; yes: string; no: string; busy: boolean; err: string
  ready?: boolean; onYes: () => void; onNo: () => void; foot?: ReactNode; sign?: boolean
}) {
  const head = useRef<HTMLHeadingElement>(null)
  useEffect(() => { head.current?.focus() }, [])
  return (
    <div className="motion" onKeyDown={e => e.key === 'Escape' && !busy && onNo()}>
      <div className="motion-h">motion</div>
      <h3 ref={head} tabIndex={-1}>{heading}</h3>
      {children}
      <div className="row-a">
        {sign ? <HoldToSign label={yes} busy={busy} ready={ready} onDone={onYes} />
          : <button className="btn danger" disabled={busy || !ready} onClick={onYes}>{yes}</button>}
        <button className="lnk" disabled={busy} onClick={onNo}>{no}</button>
      </div>
      {err && <small className="err">{err}</small>}
      {foot}
    </div>
  )
}

const HOLD = 1100  // ms of holding to sign
const still = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Hold to sign: a signature draws while you hold, and letting go early rubs it out.
 *  Space and Enter hold too. With reduced motion it's a plain button. */
function HoldToSign({ label, busy, ready, onDone, hint = `hold to sign · ${label}`, tone = 'danger' }: {
  label: string; busy: boolean; ready: boolean; onDone: () => void; hint?: string; tone?: 'danger' | 'ghost'
}) {
  const [p, setP] = useState(0)
  const raf = useRef(0)
  const t0 = useRef(0)
  const done = useRef(false)
  const step = useRef(0)  // the thirds of the hold already felt
  const stop = () => { cancelAnimationFrame(raf.current); if (!done.current) setP(0) }
  const start = () => {
    if (busy || !ready || done.current) return
    t0.current = performance.now()
    step.current = 0
    navigator.vibrate?.(10)  // the pen touches the paper
    const tick = (now: number) => {
      const v = Math.min(1, (now - t0.current) / HOLD)
      setP(v)
      if (v >= 1) { done.current = true; navigator.vibrate?.([30, 60, 45]); onDone(); return }  // signed
      const third = Math.floor(v * 3)
      if (third > step.current) { step.current = third; navigator.vibrate?.(8) }  // the signature getting on
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
  }
  useEffect(() => () => cancelAnimationFrame(raf.current), [])
  useEffect(() => { if (!busy) done.current = false }, [busy])
  if (still()) return <button className={`btn ${tone}`} disabled={busy || !ready} onClick={onDone}>{label}</button>
  return (
    <button className={`btn ${tone} sign${p > 0 ? ' holding' : ''}`} disabled={busy || !ready} aria-label={`${label} (press and hold)`}
      onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); start() }} onPointerUp={stop} onPointerCancel={stop} onContextMenu={e => e.preventDefault()}
      onKeyDown={e => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); start() } }} onKeyUp={stop}>
      <svg viewBox="0 0 120 28" aria-hidden="true">
        <line className="sign-line" x1="2" y1="26" x2="118" y2="26" />
        <path pathLength={1} style={{ strokeDashoffset: 1 - p, opacity: p > 0 ? 1 : 0 }}
          d="M4 20c6-10 10-14 13-12s-5 14-2 14 7-14 10-14-2 12 1 12 6-9 9-9-1 8 2 8 5-6 8-6 0 5 3 5 6-8 9-8-2 9 2 9 8-4 12-4 10 2 14-1 10-3 16-2" />
      </svg>
      <span>{busy ? 'signing…' : p > 0 ? 'keep holding' : hint}</span>
    </button>
  )
}

const names = (xs: Leaving[]) => xs.map(x => x.name).join(', ')

/** Winding up the account: every board, said out loud first, and the username typed back. */
export function CloseAccount({ back }: { back: string }) {
  const { me, refreshMe, toast } = useApp()
  const [boards, setBoards] = useState<Leaving[] | null>(null)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  useEffect(() => { api.leaving().then(setBoards).catch(() => setBoards([])) }, [])
  const close = async () => {
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
    <div className="bd page">
      <Motion heading={`motion to wind up ${me.username}`} yes={busy ? 'deleting…' : 'delete everything'} no="no, keep me" busy={busy} err={err}
        ready={typed.trim().toLowerCase() === me.username} onYes={close} onNo={() => goBack(back)}>
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
    </div>
  )
}

/** "you" when you're not on a board yet: your file, on its own. */
export default function MeScreen({ page }: { page?: string }) {
  const { me } = useApp()
  const user = useUsernameEdit()
  if (page === 'close') return (
    <div className="app">
      <Header title="you.xlsx" back="/me" meta="wind up" />
      <Fx fn="close" args={[['username', me.username]]} />
      <CloseAccount back="/me" />
      <Nav on="you" />
    </div>
  )
  return (
    <div className="app">
      <Header title="you.xlsx" meta={me.username} />
      {user.fx ?? <Fx fn="you" args={[['username', me.username], ['boards', 'none yet']]} />}
      <div className="bd"><YourFile onEditName={user.start} closeTo="/me/close" /></div>
      <Nav on="you" />
    </div>
  )
}

const OLD_ZONES: Record<string, string> = { 'Asia/Calcutta': 'Asia/Kolkata', 'Asia/Saigon': 'Asia/Ho_Chi_Minh', 'Asia/Katmandu': 'Asia/Kathmandu', 'Asia/Rangoon': 'Asia/Yangon', 'Europe/Kiev': 'Europe/Kyiv' }

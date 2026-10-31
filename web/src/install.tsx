import { useState, useSyncExternalStore } from 'react'

// Putting boredroom on the home screen. Chrome and Edge offer an install prompt the page
// can trigger; iPhones don't, so there the memo shows the two taps in Safari instead.
// Reminders (web push) only reach an installed app on iPhones, so this matters there most.

type Prompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> }

let deferred: Prompt | null = null
const subs = new Set<() => void>()
const tell = () => subs.forEach(f => f())

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferred = e as Prompt; tell() })
  window.addEventListener('appinstalled', () => { deferred = null; tell() })
  if ('serviceWorker' in navigator && location.hostname !== 'localhost') {
    window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js').catch(() => {}) })
  }
}

export const standalone = () =>
  matchMedia('(display-mode: standalone)').matches || (navigator as { standalone?: boolean }).standalone === true
const ios = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

/** 'prompt': the browser will install on a tap. 'ios': show the steps. null: nothing to offer. */
export function useInstall(): ['prompt' | 'ios' | null, () => Promise<boolean>] {
  const can = useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, () => deferred)
  const how = standalone() ? null : can ? 'prompt' : ios() ? 'ios' : null
  const install = async () => {
    if (!deferred) return false
    await deferred.prompt()
    const { outcome } = await deferred.userChoice
    deferred = null; tell()
    return outcome === 'accepted'
  }
  return [how, install]
}

const SNOOZE = 'boredroom.install.snooze'
const snoozed = () => { try { return Number(localStorage.getItem(SNOOZE) ?? 0) > Date.now() } catch { return false } }
const snooze = (days: number) => { try { localStorage.setItem(SNOOZE, String(Date.now() + days * 864e5)) } catch { /* fine */ } }

/** Safari's share glyph, so the steps point at the button people will look for. */
function ShareGlyph() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-label="share" role="img" style={{ verticalAlign: '-3px' }}>
      <path d="M10 2.5v10M6.5 6 10 2.5 13.5 6" strokeLinecap="round" strokeLinejoin="round" /><path d="M6 9H4.5v8.5h11V9H14" strokeLinejoin="round" />
    </svg>
  )
}

/** A memo from the chair: put boredroom on your home screen. Shows on the agenda until
 *  it's installed or snoozed; `always` keeps it (for the "you" page). */
export function InstallMemo({ always = false, onDone }: { always?: boolean; onDone?: (installed: boolean) => void }) {
  const [how, install] = useInstall()
  const [hidden, setHidden] = useState(() => !always && snoozed())
  const [steps, setSteps] = useState(false)
  if (!how || hidden) return null

  const go = async () => {
    if (how === 'ios') { setSteps(s => !s); return }
    const ok = await install()
    onDone?.(ok)
  }
  return (
    <div className="memo">
      <div className="memo-h"><span>memo</span><span>from: the chair</span><span>re: your home screen</span></div>
      <b>motion to put boredroom on your home screen.</b>
      <small>one tap from the puzzle to the minutes, it opens like an app, and it's the only way the board can nudge you before a puzzle resets.</small>
      {steps && (
        <ol className="memo-steps">
          <li>in safari, tap <ShareGlyph /> share</li>
          <li>scroll down, tap <b>add to home screen</b></li>
          <li>open boredroom from your home screen</li>
        </ol>
      )}
      <div className="row-a">
        <button className="btn" onClick={go}>{how === 'ios' ? (steps ? 'got it' : 'show me how') : 'seconded. install'}</button>
        {!always && <button className="lnk" onClick={() => { snooze(7); setHidden(true) }}>table it for a week</button>}
      </div>
    </div>
  )
}

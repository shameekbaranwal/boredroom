import { useState } from 'react'
import { api } from './api'
import { askLater, disable, enable, shouldAsk, usePush, why } from './push'
import { useApp } from './ui'

// Reminders on screen: this device's switch (you → everywhere), the bell on each game of
// your agenda (a nudge an hour before it resets), and the memo that asks, once you've been
// around a couple of days. The evening digest is on by default, per board.

/** A bell: on, a nudge before this game resets. Drawn, not an emoji, so it takes the theme. */
export function Bell({ on, label, onFlip }: { on: boolean; label: string; onFlip: () => void }) {
  return (
    <button className={`bell${on ? ' on' : ''}`} role="switch" aria-checked={on} aria-label={label} onClick={onFlip}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
        <path d="M10 2.6c-2.9 0-4.8 2.2-4.8 5v3.1L3.6 13.5h12.8l-1.6-2.8V7.6c0-2.8-1.9-5-4.8-5Z" />
        <path d="M8.1 15.6a2 2 0 0 0 3.8 0" fill="none" />
      </svg>
    </button>
  )
}

/** "this device" under you → everywhere: the switch, or why there isn't one. */
export function DeviceReminders() {
  const { toast } = useApp()
  const p = usePush()
  const [testing, setTesting] = useState(false)
  if (!p.ready) return null
  const note = p.support === 'install' ? 'on an iphone, only from the home screen app'
    : p.support === 'none' ? "this browser can't take them"
      : !p.server ? "this server doesn't send them yet"
        : p.perm === 'denied' ? "blocked in your browser's settings for this site"
          : p.on ? 'the evening digest, and the bells on your agenda' : 'off on this device'
  const flip = async () => {
    if (p.busy) return
    if (p.on) { await disable().catch(() => {}); toast('reminders off on this device.'); return }
    if (await enable()) toast('carried. the board can reach this device.')
    else toast(why({ ...p, perm: Notification.permission }))
  }
  const test = async () => {
    setTesting(true)
    try { const r = await api.testPush(); toast(r.sent ? 'sent. look for the test memo.' : "it didn't reach any device. switch reminders off and on again.") }
    catch (e) { toast((e as Error).message) } finally { setTesting(false) }
  }
  const can = p.support === 'ok' && p.server && p.perm !== 'denied'
  return (
    <div className="cell">
      <span className="k">reminders<small className="muted">{note}{p.on && <> · <button className="lnk" disabled={testing} onClick={test}>{testing ? 'sending…' : 'send a test'}</button></>}</small></span>
      {can
        ? <button className={`sw${p.on ? ' on' : ''}`} role="switch" aria-checked={p.on} aria-label="reminders on this device" disabled={p.busy} onClick={flip}>
            <span className="sw-w">{p.on ? 'on' : 'off'}</span><i aria-hidden="true" />
          </button>
        : <span className="chip">{p.support === 'install' ? 'install first' : p.perm === 'denied' ? 'blocked' : 'not here'}</span>}
    </div>
  )
}

/** The ask: on the agenda on your 2nd to 4th day, while this device has never been asked. */
export function AskMemo() {
  const { toast } = useApp()
  const p = usePush()
  const [gone, setGone] = useState(false)
  if (gone || !shouldAsk(p)) return null
  const yes = async () => {
    if (await enable()) toast("carried. around 20:00, the board's day in one push.")
    else toast(why({ ...p, perm: Notification.permission }))
    setGone(true)
  }
  return (
    <div className="memo">
      <div className="memo-h"><span>memo</span><span>from: the chair</span><span>re: reminders</span></div>
      <b>motion to send you the board's day each evening.</b>
      <small>one push around 20:00: the big news, where you stand this week, what's left. ring a game's bell under you → agenda for a nudge an hour before it resets.</small>
      <div className="row-a">
        <button className="btn" disabled={p.busy} onClick={yes}>yes, nudge me</button>
        <button className="lnk" onClick={() => { askLater(); setGone(true) }}>not now</button>
      </div>
    </div>
  )
}

// The board table mark and the cell-row wordmark (brand canvas: mark c, wordmark b).
import { setPref, useTheme } from './theme'

export function TableMark({ size = 28, mono = false, tile = false }: { size?: number; mono?: boolean; tile?: boolean }) {
  const ink = mono ? 'currentColor' : 'var(--mark-ink)'
  const mute = mono ? 'currentColor' : 'var(--mark-mute)'
  const hl = mono ? 'currentColor' : 'var(--mark-hl)'
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true" style={{ flex: 'none', display: 'block' }}>
      {tile && <rect width="64" height="64" rx="14" fill="var(--mark-tile)" />}
      <rect x="15" y="21" width="34" height="22" rx="11" fill={ink} />
      <g fill={mute} opacity={mono ? 0.55 : 1}>
        <rect x="20" y="9" width="8" height="8" rx="1.5" /><rect x="36" y="9" width="8" height="8" rx="1.5" />
        <rect x="20" y="47" width="8" height="8" rx="1.5" /><rect x="36" y="47" width="8" height="8" rx="1.5" />
        <rect x="4" y="28" width="8" height="8" rx="1.5" />
      </g>
      <rect x="52" y="27" width="10" height="10" rx="1.5" fill={hl} />
    </svg>
  )
}

/** The name, with the double o as two filled cells (brand canvas: wordmark a). */
export function Wordmark({ size, onRoom = false, onBand = false }: { size?: number; onRoom?: boolean; onBand?: boolean }) {
  return (
    <span className={`wm${onRoom ? ' on-room' : ''}${onBand ? ' on-band' : ''}`} role="img" aria-label="boredroom" style={size ? { fontSize: size } : undefined}>
      boredr<i className="c1">o</i><i className="c2">o</i>m
    </span>
  )
}

/** A sun/moon switch. The page change itself animates from the switch (see theme.ts). */
export function ThemeToggle({ className = '' }: { className?: string }) {
  const [, shown] = useTheme()
  const next = shown === 'dark' ? 'light' : 'dark'
  return (
    <button className={`theme-tg ${className}`} data-mode={shown} role="switch" aria-checked={shown === 'dark'}
      aria-label="dark mode" title={`switch to ${next} mode`}
      onClick={e => setPref(next, { x: e.clientX, y: e.clientY })}>
      <span className="stars" aria-hidden="true"><i /><i /><i /></span>
      <span className="knob" aria-hidden="true">
        <svg className="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><circle cx="12" cy="12" r="4.2" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" /></svg>
        <svg className="moon" viewBox="0 0 24 24" fill="currentColor"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>
      </span>
    </button>
  )
}

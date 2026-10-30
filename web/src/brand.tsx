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

const WORD = 'boredroom'.split('')
const TINT = ['g', '', 'y', 'g', '', 'y', 'g', '', 'g']

/** The name typed into a row of cells, with column letters a–i above it. */
export function Wordmark({ cell = 30, onDark = false }: { cell?: number; onDark?: boolean }) {
  return (
    <span className={`wm${onDark ? ' on-dark' : ''}`} role="img" aria-label="boredroom"
      style={{ ['--cell' as string]: `${cell}px` }}>
      <i className="wm-h" />
      {'abcdefghi'.split('').map(c => <i key={c} className="wm-h">{c}</i>)}
      <i className="wm-h wm-n">1</i>
      {WORD.map((ch, k) => <b key={k} className={`wm-c ${TINT[k]}`}>{ch}</b>)}
    </span>
  )
}

export function ThemeToggle({ className = '' }: { className?: string }) {
  const [, shown] = useTheme()
  const next = shown === 'dark' ? 'light' : 'dark'
  return (
    <button className={`theme-tg ${className}`} onClick={() => setPref(next)} aria-label={`switch to ${next} mode`} title={`switch to ${next} mode`}>
      {shown === 'dark'
        ? <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
        : <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>}
    </button>
  )
}

import type { Game, Memo } from './api'
import { headline } from './format'
import { go } from './router'

// Memos from the chair: one sheet row each, a glyph for the kind, one line, and the number
// that matters. Tapping one opens the query behind it (the week's review, the minutes).

export const memoNumber = (m: Memo, game?: Game) => m.score ? headline(game, m.score.metrics, m.score.outcome) : m.number

export function MemoRow({ m, game, onDismiss }: { m: Memo; game?: Game; onDismiss?: () => void }) {
  const n = memoNumber(m, game)
  return (
    <div className={`memo-row${m.me ? ' me' : ''}`}>
      <span className={`memo-g k-${m.kind}`} aria-hidden="true">{m.glyph}</span>
      <button className="memo-t" onClick={() => go(m.link)}>{m.text}</button>
      {n && <span className="memo-n">{n}</span>}
      {onDismiss && <button className="memo-x" aria-label="dismiss this memo" onClick={onDismiss}>×</button>}
    </div>
  )
}

/** The day's memos as one message for the group chat, in third person. */
export function meetingText(board: string, label: string, memos: Memo[], games: Record<string, Game>) {
  const lines = memos.map(m => { const n = memoNumber(m, m.game ? games[m.game] : undefined); return `${m.glyph} ${m.plain}${n ? ` (${n})` : ''}` })
  return [`the daily bored meeting · ${board} · ${label}`, ...lines].join('\n')
}

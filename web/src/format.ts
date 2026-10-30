import type { Field, Game, Metric } from './api'

export function fmtMetric(m: Metric | undefined, v: number): string {
  if (!m) return String(v)
  if (m.kind === 'duration') {
    const s = Math.round(v), h = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60
    return h ? `${h}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}` : `${mm}:${String(ss).padStart(2, '0')}`
  }
  const n = Number.isInteger(v) ? String(v) : v.toFixed(1)
  if (m.max != null && (m.kind === 'ratio' || m.kind === 'count' || m.kind === 'points')) return `${n}/${m.max}`
  if (m.unit) return `${n} ${m.unit}`
  return `${n} ${m.name}`.trim()
}

/** The headline value: the game's ranker metrics in order, joined. */
export function headline(game: Game | undefined, metrics: Record<string, number>, outcome?: string): string {
  if (outcome === 'failed') return 'failed'
  if (!game) return Object.values(metrics).join(' · ')
  const names = game.ranker.length ? game.ranker : game.metrics.map(m => m.name)
  const parts = names.filter(n => metrics[n] != null).map(n => fmtMetric(game.metrics.find(m => m.name === n), metrics[n]))
  return parts.length ? parts.join(' · ') : 'played'
}

export function fieldText(f: Field): string {
  const v = f.value
  if (Array.isArray(v)) return v.join(f.name === 'route' ? ' → ' : ' ')
  if (v && typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** A grid of emoji keeps its line breaks; other fields are one line. */
export const isGrid = (f: Field) => typeof f.value === 'string' && f.value.includes('\n')

export function left(iso: string, now: number): string {
  const ms = new Date(iso).getTime() - now
  if (ms <= 0) return 'now'
  const m = Math.floor(ms / 60000), h = Math.floor(m / 60)
  return h ? `${h}h ${m % 60}m` : `${m}m`
}

export function dayLabel(iso: string, today: string): string {
  if (iso === today) return 'today'
  const d = new Date(iso + 'T00:00:00'), t = new Date(today + 'T00:00:00')
  const diff = Math.round((t.getTime() - d.getTime()) / 86400000)
  if (diff === 1) return 'yesterday'
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }).toLowerCase()
}

export function shiftDay(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

/** A stable colour per person, as in the mockups' avatars. */
export function hue(name: string): number {
  let h = 0
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360
  return h
}

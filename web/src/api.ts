// The JSON API (/api/v1, docs/SERVER.md part 5). One bearer token per seat, kept in
// localStorage; the server is always same-origin (Vite proxies it in development).

export type Kind = 'guest' | 'account' | 'placeholder'
export type BoardRef = { slug: string; name: string; nickname: string; role: string }
export type Me = { username: string; kind: Kind; tz: string; email: string | null; boards: BoardRef[] }
export type Metric = { name: string; kind: string; better: 'high' | 'low'; max: number | null; unit: string | null }
export type Game = { id: string; name: string; key: string; ranked: boolean; links: string[]; ranker: string[]; metrics: Metric[] }
export type Field = { name: string; value: unknown; visibility: 'public' | 'detail' | 'spoiler' }

export type Row = {
  id: number | null; nickname: string; me: boolean; place: string; puzzle: string
  outcome: 'solved' | 'failed' | 'played'; metrics: Record<string, number>; highlights: string[]
  late: boolean; amended: boolean; fields: Field[]; hidden: number; comment: string
  raw: string | null; forward: string | null; filed_at: string
}
export type Item = {
  game: string; name: string; ranked: boolean; links: string[]; day: string; puzzle: string | null
  resets_at: string; filed: boolean; place: string; present: number; players: number; filed_by: string[]
  leader: { nickname: string | null; tied: number; metrics: Record<string, number> } | null
  mine: Row | null
}
export type Today = { now: string; items: Item[] }
export type Minutes = {
  game: string; name: string; ranked: boolean; day: string; current: boolean; resets_at: string | null
  open: boolean; rows: Row[]; not_in: string[]
}
export type Member = { nickname: string; username: string; role: string; kind: Kind; games: number }
export type Board = {
  slug: string; name: string; settings: Record<string, unknown>; invite: { code: string; expires_at: string | null }
  you: { nickname: string; role: string; agenda: string[] }
  members: Member[]
  library: { game: string; name: string; rules: Record<string, unknown>; players: number }[]
  leaving: Leaving
}
/** What leaving a board would do. */
export type Leaving = { slug: string; name: string; chair: boolean; claimed: { nickname: string; results: number } | null; heir: string | null; alone: boolean }
export type Invite = { code: string; name: string; slug: string; chair: string | null; inviter: string | null; members: number; library: string[]
  seats: { username: string; nickname: string; results: number }[] }
export type Period = 'today' | 'week' | 'month' | 'all'
export type Standing = { nickname: string; me: boolean; wins: number; days: number; place: number }
export type Review = {
  period: Period; now: string; standings: Standing[]
  games?: { game: string; name: string; ranked: boolean; day: string; present: number; players: number; plays: boolean
    place: string | null; filed: boolean; leader: { nickname: string | null; tied: number; metrics: Record<string, number> } | null }[]
  records?: { game: string; name: string; nickname: string; me: boolean; metrics: Record<string, number>; day: string }[]
}
export type Event = {
  kind: 'filed' | 'merged' | 'duplicate' | 'conflict' | 'not_out_yet'
  game: string; puzzle: string; result_id: number | null; added: string[]; confidence: string; late: boolean
  outcome?: string | null; metrics?: Record<string, number>  // previews only
}
export type MyResult = {
  id: number; game: string; name: string; puzzle: string; day: string | null
  outcome: 'solved' | 'failed' | 'played'; metrics: Record<string, number>; late: boolean; withdrawn: boolean; filed_at: string
}
export type Unknown = { name: string; link: string | null; score: string | null; raw: string }
export type Filing = { paste_id: number; events: Event[]; unknown: Unknown[]; note: string }

const TOKEN = 'boredroom.token'

export function token(): string | null {
  try { return localStorage.getItem(TOKEN) } catch { return null }
}
export function setToken(t: string | null) {
  try { if (t) localStorage.setItem(TOKEN, t); else localStorage.removeItem(TOKEN) } catch { /* private mode */ }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const t = token()
  if (t) headers.Authorization = `Bearer ${t}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const r = await fetch(`/api/v1${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new ApiError(r.status, data.error ?? `the server said ${r.status}`)
  return data as T
}

const tz = () => Intl.DateTimeFormat().resolvedOptions().timeZone

export const api = {
  config: () => call<{ google_client_id: string | null; environment: string }>('GET', '/config'),
  games: () => call<Game[]>('GET', '/games'),
  me: () => call<Me>('GET', '/me'),
  updateMe: (b: Partial<{ tz: string; username: string }>) => call<Me>('PATCH', '/me', b),
  guest: (username?: string) => call<{ token: string; me: Me }>('POST', '/guests', { username, tz: tz() }),
  google: (credential: string) => call<{ token: string; created: boolean; me: Me }>('POST', '/auth/google', { credential, tz: tz() }),
  signOut: () => call<{ signed_out: boolean }>('POST', '/auth/signout'),
  closeAccount: (username: string) => call<{ deleted: boolean; boards_closed: string[] }>('DELETE', '/me', { username }),
  leaving: () => call<Leaving[]>('GET', '/me/leaving'),
  leave: (slug: string) => call<{ left: string; closed: boolean }>('POST', `/boards/${slug}/leave`),
  newBoard: (name: string) => call<Board>('POST', '/boards', { name }),
  invite: (code: string) => call<Invite>('GET', `/invites/${encodeURIComponent(code)}`),
  join: (code: string, claim?: string) => call<Board>('POST', '/boards/join', { code, claim }),
  board: (slug: string) => call<Board>('GET', `/boards/${slug}`),
  rename: (slug: string, name: string) => call<Board>('PATCH', `/boards/${slug}`, { name }),
  retireInvites: (slug: string) => call<{ retired: number; board: Board }>('DELETE', `/boards/${slug}/invites`),
  dropGame: (slug: string, game: string) => call<Board>('DELETE', `/boards/${slug}/library/${game}`),
  renewInvite: (slug: string) => call<Board>('POST', `/boards/${slug}/invite`),
  nickname: (slug: string, nickname: string) => call<Board>('PATCH', `/boards/${slug}/me`, { nickname }),
  agenda: (slug: string, game: string, on: boolean) => call<Board>(on ? 'PUT' : 'DELETE', `/boards/${slug}/agenda/${game}`),
  claim: (slug: string, username: string) => call<{ moved: number; board: Board }>('POST', `/boards/${slug}/claim`, { username }),
  review: (slug: string, period: Period) => call<Review>('GET', `/boards/${slug}/review?period=${period}`),
  today: (slug: string) => call<Today>('GET', `/boards/${slug}/today`),
  minutes: (slug: string, game: string, day?: string) =>
    call<Minutes>('GET', `/boards/${slug}/minutes/${game}${day ? `?day=${day}` : ''}`),
  paste: (text: string, source: 'paste' | 'share' = 'paste') => call<Filing>('POST', '/pastes', { text, source }),
  preview: (text: string) => call<Filing>('POST', '/pastes/preview', { text }),
  replace: (id: number, paste_id: number) => call<unknown>('POST', `/results/${id}/replace`, { paste_id }),
  results: () => call<MyResult[]>('GET', '/results'),
  withdraw: (id: number) => call<unknown>('DELETE', `/results/${id}`),
}

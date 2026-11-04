// The JSON API (/api/v1, docs/SERVER.md part 5). One bearer token per seat, kept in
// localStorage; the server is always same-origin (Vite proxies it in development).
import { lost, net, reached, set, type Away } from './net'

export type Kind = 'guest' | 'account' | 'placeholder'
export type BoardRef = { slug: string; name: string; nickname: string; role: string }
export type Me = { username: string; kind: Kind; tz: string; email: string | null; agenda_sort: string | null; reset_clock: boolean; boards: BoardRef[]
  news: (Release & { for_you?: string }) | null }  // the latest release, while it's news to you; or one that answered your note
/** A release's notes (what's new). Its id is the day it went out. */
export type Release = { id: string; title: string; notes: string[]; major: boolean }
/** Your note, answered by the developer with a release: yours alone to see. */
export type Reply = { release: string; kind: 'bug' | 'idea'; text: string; reply: string; read: boolean }
/** A note to the developer. */
export type Note = { id: number; kind: 'bug' | 'idea'; text: string; board: string | null; sent_at: string }
export type Metric = { name: string; kind: string; better: 'high' | 'low'; max: number | null; unit: string | null }
export type Game = { id: string; name: string; key: string; ranked: boolean; weekly: boolean; links: string[]; play: string | null; ranker: string[]; metrics: Metric[] }
export type Field = { name: string; value: unknown; visibility: 'public' | 'detail' | 'spoiler' }

export type Row = {
  id: number | null; nickname: string; me: boolean; place: string; puzzle: string
  outcome: 'solved' | 'failed' | 'played'; metrics: Record<string, number>; highlights: string[]
  late: boolean; amended: boolean; fields: Field[]; hidden: number; comment: string
  raw: string | null; forward: string | null; filed_at: string; tenure?: number
}
export type Item = {
  game: string; name: string; ranked: boolean; links: string[]; play: string | null; day: string; puzzle: string | null
  resets_at: string; filed: boolean; skipped: boolean; weekly: boolean; place: string; present: number; players: number; filed_by: string[]
  leader: { nickname: string | null; tied: number; metrics: Record<string, number> } | null
  mine: Row | null; tenure: { days: number; at_risk: boolean }
  results: number; board_month: number  // filed by you ever; by the board in the last 30 days
  position: number  // its place in your own order ("my order")
}
export type Memo = {
  id: number; kind: string; glyph: string; day: string; game: string | null
  text: string; plain: string; number: string; score: { metrics: Record<string, number>; outcome: string } | null
  link: string; about: string[]; me: boolean; dismissed: boolean
}
export type Today = { now: string; items: Item[]; memos: Memo[] }
export type Meeting = { day: string; today: string; earlier: string | null; memos: Memo[] }
export type Minutes = {
  game: string; name: string; ranked: boolean; weekly: boolean; day: string; current: boolean; resets_at: string | null
  open: boolean; rows: Row[]; not_in: string[]
}
export type Member = { nickname: string; username: string; role: string; kind: Kind; games: number; results: number; joined_at: string }
export type Board = {
  slug: string; name: string; settings: Record<string, unknown>; invite: { code: string; expires_at: string | null }
  you: { nickname: string; role: string; agenda: string[]; claimed?: boolean; digest: boolean; nudges: string[]; order: string[] }
  members: Member[]
  library: { game: string; name: string; rules: Record<string, unknown>; players: number; removable: boolean }[]
  leaving: Leaving
}
/** What leaving a board would do. */
export type Leaving = { slug: string; name: string; chair: boolean; claimed: { nickname: string; results: number } | null; heir: string | null; alone: boolean }
export type Invite = { code: string; name: string; slug: string; chair: string | null; inviter: string | null; members: number; library: string[]
  seats: { username: string; nickname: string; results: number }[] }
export type Period = 'today' | 'week' | 'month' | 'all'
export type Standing = { nickname: string; me: boolean; wins: number; days: number; filed: number; rate: number; place: number | null
  played?: number; average?: number | null; best?: Record<string, number> | null; qualified?: boolean
  tenure?: number; longest?: number; at_risk?: boolean }
export type Review = {
  period: Period; game: string | null; weekly: boolean; stat: string; stats: string[]; vs: string | null; now: string
  standings: Standing[]; members: string[]; ranked_games: string[]; strip: ('' | 'on' | 'ls' | 'lv')[]
  h2h?: { you: number; them: number; level: number }
  min_plays?: number; metric?: string; record?: { nickname: string; me: boolean; metrics: Record<string, number>; day: string } | null
  games?: ReviewItem[]
  weeklies?: ReviewItem[]  // on "today": weekly games, this week's puzzle so far
  records?: { game: string; name: string; nickname: string; me: boolean; metrics: Record<string, number>; day: string }[]
}
export type ReviewItem = {
  game: string; name: string; ranked: boolean; day: string; present: number; players: number; plays: boolean
  place: string | null; filed: boolean; leader: { nickname: string | null; tied: number; metrics: Record<string, number> } | null
}
/** One member's activity on a board (=member(board, who)). Scores only: details stay in the minutes. */
export type MemberGame = { game: string; name: string; ranked: boolean; weekly: boolean; results: number; played: number; wins: number
  tenure: number; longest: number; at_risk: boolean; average: number | null; best: Record<string, number> | null; last: string | null; today: string }
export type MemberResult = { game: string; name: string; weekly: boolean; day: string; puzzle: string; outcome: 'solved' | 'failed' | 'played'
  metrics: Record<string, number>; highlights: string[]; late: boolean; place: string; of: number; filed_at: string }
export type MemberPage = { nickname: string; me: boolean; role: string; joined_at: string; today: string; games: MemberGame[]
  daily: number; strip: number[]; present: number; wins: number; recent: MemberResult[]; memos: Memo[] }
/** A google sign-in: `merged` says what a guest seat brought into an account that already existed. */
export type SignedIn = { token: string; created: boolean; merged: { results: number; boards: number } | null; me: Me }
export type ReviewQuery = { period: Period; game?: string | null; stat?: string | null; vs?: string | null }
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
export type Device = { id: number; device: string | null; endpoint: string; since: string; last_ok_at: string | null }
export type Devices = { available?: boolean; devices: Device[] }
export type Filing = { paste_id: number; events: Event[]; unknown: Unknown[]; note: string }

const TOKEN = 'boredroom.token'

export function token(): string | null {
  try { return localStorage.getItem(TOKEN) } catch { return null }
}
export function setToken(t: string | null) {
  try { if (t) localStorage.setItem(TOKEN, t); else localStorage.removeItem(TOKEN) } catch { /* private mode */ }
  forget()  // another seat's copies aren't yours
}

export class ApiError extends Error {
  status: number
  away: boolean  // never reached the server: offline, or it's restarting
  constructor(status: number, message: string, away = false) { super(message); this.status = status; this.away = away }
}

// What each screen last loaded, kept on this device: offline, or while the server restarts,
// the screen shows that copy (the strip says how old) instead of nothing.
const COPY = 'boredroom.copy:', COPIES = 'boredroom.copies', KEEP = 40
type Copy = { at: number; data: unknown }
function keep(path: string, data: unknown) {
  const put = () => {
    localStorage.setItem(COPY + path, JSON.stringify({ at: Date.now(), data }))
    const paths = [path, ...(JSON.parse(localStorage.getItem(COPIES) ?? '[]') as string[]).filter(p => p !== path)]
    for (const p of paths.slice(KEEP)) localStorage.removeItem(COPY + p)
    localStorage.setItem(COPIES, JSON.stringify(paths.slice(0, KEEP)))
  }
  try { put() } catch { try { forget(); put() } catch { /* no room: no copy */ } }
}
function copy(path: string): Copy | null {
  try { return JSON.parse(localStorage.getItem(COPY + path) ?? 'null') } catch { return null }
}
function forget() {
  try {
    for (const p of JSON.parse(localStorage.getItem(COPIES) ?? '[]') as string[]) localStorage.removeItem(COPY + p)
    localStorage.removeItem(COPIES)
  } catch { /* fine */ }
}

const WAIT = 15000  // a call that hasn't answered by now isn't going to
const AGAIN = [500, 1000, 2000, 3000, 4000]  // a load tries again for ~10s: a deploy restarts the server in ~4
const AWAY = new Set([502, 503, 504, 520, 521, 522, 523, 524, 530])  // the tunnel couldn't reach the server
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))
export const awayText = (why: Away) => why === 'offline'
  ? "you're offline. it'll catch up when you're back."
  : "boredroom isn't answering. probably a quick restart; it'll catch up."

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const t = token()
  if (t) headers.Authorization = `Bearer ${t}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const load = method === 'GET'
  for (let n = 0; ; n++) {
    let r: Response | null = null
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), WAIT)
    try { r = await fetch(`/api/v1${path}`, { method, headers, signal: ctl.signal, body: body === undefined ? undefined : JSON.stringify(body) }) }
    catch { /* offline, or no answer in time */ } finally { clearTimeout(timer) }
    if (r && !AWAY.has(r.status)) {
      reached()
      const data = await r.json().catch(() => ({}))
      if (r.status === 401 && t) {  // the seat is gone (signed out elsewhere, or the database was reset): back to the door
        setToken(null)
        window.dispatchEvent(new Event('boredroom:signedout'))
      }
      if (!r.ok) throw new ApiError(r.status, data.error ?? `the server said ${r.status}`)
      if (load) keep(path, data)
      return data as T
    }
    const why: Away = r || navigator.onLine ? 'down' : 'offline'
    lost(why)
    const kept = load ? copy(path) : null
    if (kept) { set({ stale: Math.min(net().stale ?? kept.at, kept.at) }); return kept.data as T }
    // a load tries again for a while; a change never does, so nothing is filed twice
    if (!load || why === 'offline' || n >= AGAIN.length) throw new ApiError(r?.status ?? 0, awayText(why), true)
    await sleep(AGAIN[n])
  }
}

const tz = () => Intl.DateTimeFormat().resolvedOptions().timeZone

export const api = {
  config: () => call<{ google_client_id: string | null; environment: string; vapid_public_key: string | null }>('GET', '/config'),
  games: () => call<Game[]>('GET', '/games'),
  me: () => call<Me>('GET', '/me'),
  updateMe: (b: Partial<{ tz: string; username: string; agenda_sort: string | null; reset_clock: boolean }>) => call<Me>('PATCH', '/me', b),
  guest: (username?: string) => call<{ token: string; me: Me }>('POST', '/guests', { username, tz: tz() }),
  google: (credential: string) => call<SignedIn>('POST', '/auth/google', { credential, tz: tz() }),
  signOut: () => call<{ signed_out: boolean }>('POST', '/auth/signout'),
  username: (name: string) => call<{ username: string; available: boolean; reason: string | null }>('GET', `/usernames/${encodeURIComponent(name)}`),
  closeAccount: (username: string) => call<{ deleted: boolean; boards_closed: string[] }>('DELETE', '/me', { username }),
  leaving: () => call<Leaving[]>('GET', '/me/leaving'),
  leave: (slug: string) => call<{ left: string; closed: boolean }>('POST', `/boards/${encodeURIComponent(slug)}/leave`),
  newBoard: (name: string) => call<Board>('POST', '/boards', { name }),
  invite: (code: string) => call<Invite>('GET', `/invites/${encodeURIComponent(code)}`),
  join: (code: string, claim?: string) => call<Board>('POST', '/boards/join', { code, claim }),
  board: (slug: string) => call<Board>('GET', `/boards/${encodeURIComponent(slug)}`),
  rename: (slug: string, name: string) => call<Board>('PATCH', `/boards/${encodeURIComponent(slug)}`, { name }),
  retireInvites: (slug: string) => call<{ retired: number; board: Board }>('DELETE', `/boards/${encodeURIComponent(slug)}/invites`),
  dropGame: (slug: string, game: string) => call<Board>('DELETE', `/boards/${encodeURIComponent(slug)}/library/${encodeURIComponent(game)}`),
  renewInvite: (slug: string) => call<Board>('POST', `/boards/${encodeURIComponent(slug)}/invite`),
  nickname: (slug: string, nickname: string) => call<Board>('PATCH', `/boards/${encodeURIComponent(slug)}/me`, { nickname }),
  digest: (slug: string, digest: boolean) => call<Board>('PATCH', `/boards/${encodeURIComponent(slug)}/me`, { digest }),
  nudges: (slug: string, on: boolean) => call<Board>(on ? 'PUT' : 'DELETE', `/boards/${encodeURIComponent(slug)}/nudges`),
  nudge: (slug: string, game: string, on: boolean) => call<Board>(on ? 'PUT' : 'DELETE', `/boards/${encodeURIComponent(slug)}/agenda/${encodeURIComponent(game)}/nudge`),
  devices: () => call<Devices>('GET', '/me/push'),
  subscribe: (sub: PushSubscriptionJSON) => call<Devices>('PUT', '/me/push', sub),
  unsubscribe: (id: number) => call<Devices>('DELETE', `/me/push/${id}`),
  testPush: () => call<{ sent: number } & Devices>('POST', '/me/push/test'),
  /** Your agenda here in your own order, for the "my order" sort. */
  order: (slug: string, games: string[]) => call<Board>('PUT', `/boards/${encodeURIComponent(slug)}/order`, { games }),
  agenda: (slug: string, game: string, on: boolean) => call<Board>(on ? 'PUT' : 'DELETE', `/boards/${encodeURIComponent(slug)}/agenda/${encodeURIComponent(game)}`),
  claim: (slug: string, username: string) => call<{ moved: number; board: Board }>('POST', `/boards/${encodeURIComponent(slug)}/claim`, { username }),
  review: (slug: string, q: ReviewQuery) => call<Review>('GET', `/boards/${encodeURIComponent(slug)}/review?${new URLSearchParams(
    Object.entries(q).filter(([, v]) => v) as [string, string][])}`),
  member: (slug: string, nickname: string) => call<MemberPage>('GET', `/boards/${encodeURIComponent(slug)}/members/${encodeURIComponent(nickname)}`),
  today: (slug: string) => call<Today>('GET', `/boards/${encodeURIComponent(slug)}/today`),
  skip: (slug: string, game: string, on: boolean) => call<Today>(on ? 'PUT' : 'DELETE', `/boards/${encodeURIComponent(slug)}/skips/${encodeURIComponent(game)}`),
  minutes: (slug: string, game: string, day?: string) =>
    call<Minutes>('GET', `/boards/${encodeURIComponent(slug)}/minutes/${encodeURIComponent(game)}${day ? `?day=${encodeURIComponent(day)}` : ''}`),
  meeting: (slug: string, day?: string) => call<Meeting>('GET', `/boards/${encodeURIComponent(slug)}/meeting${day ? `?day=${encodeURIComponent(day)}` : ''}`),
  dismissMemo: (slug: string, id: number, on: boolean) => call<{ memos: Memo[] }>(on ? 'POST' : 'DELETE', `/boards/${encodeURIComponent(slug)}/memos/${id}/dismiss`),
  paste: (text: string, source: 'paste' | 'share' = 'paste', pasted_at?: string) => call<Filing>('POST', '/pastes', { text, source, pasted_at }),
  preview: (text: string) => call<Filing>('POST', '/pastes/preview', { text }),
  replace: (id: number, paste_id: number) => call<unknown>('POST', `/results/${id}/replace`, { paste_id }),
  results: () => call<MyResult[]>('GET', '/results'),
  news: () => call<{ releases: Release[]; seen: string | null; replies: Reply[] }>('GET', '/news'),
  newsSeen: (id: string) => call<Me>('POST', '/news/seen', { id }),
  notes: () => call<Note[]>('GET', '/feedback'),
  sendNote: (kind: Note['kind'], text: string, board: string | null) => call<Note[]>('POST', '/feedback', { kind, text, board }),
  withdraw: (id: number) => call<unknown>('DELETE', `/results/${id}`),
}

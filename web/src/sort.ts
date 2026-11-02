import type { Item } from './api'

// How the agenda orders its games, picked in the formula bar: =agenda(…, sort:"resets",
// order:"soonest first"). It orders within each tab, so "to do" still means what's left.
// The choice goes with your account (me.agenda_sort, "resets:first"), so every device
// you sign in on orders it the same way.

export type SortBy = 'usual' | 'resets' | 'mine' | 'popular' | 'busy' | 'tenure' | 'name'
export type Order = 'first' | 'last'  // the sort's natural way round, or the other
export type Sort = { by: SortBy; order: Order }

/** Each sort: its name in the bar, its two orders' names, and the value it ranks by
 *  (the natural order puts the biggest first, except resets and names). */
const SORTS: Record<SortBy, { label: string; orders: [string, string]; up?: boolean; key: (i: Item) => number | string }> = {
  usual: { label: 'the usual', orders: ['as usual', 'reversed'], key: () => 0 },
  resets: { label: 'resets', orders: ['soonest first', 'latest first'], up: true, key: i => Date.parse(i.resets_at) },
  mine: { label: 'my results', orders: ['most first', 'fewest first'], key: i => i.results },
  popular: { label: 'popularity', orders: ['most played first', 'least played first'], key: i => i.board_month },
  busy: { label: 'busy today', orders: ['busiest first', 'quietest first'], key: i => i.present },
  tenure: { label: 'my tenure', orders: ['longest first', 'shortest first'], key: i => i.tenure.days * (i.weekly ? 7 : 1) },  // weeks, counted in days
  name: { label: 'a–z', orders: ['a → z', 'z → a'], up: true, key: i => i.name.toLowerCase() },
}

export const sortOptions = (Object.keys(SORTS) as SortBy[]).map(b => [b, SORTS[b].label] as [string, string])
export const orderOptions = (by: SortBy): [string, string][] => [['first', SORTS[by].orders[0]], ['last', SORTS[by].orders[1]]]

/** The items in this order. Ties keep the server's order, which is the usual one. */
export function sorted(items: Item[], { by, order }: Sort): Item[] {
  const s = SORTS[by]
  const at = new Map(items.map((i, n) => [i.game, n]))
  const sign = (s.up ? 1 : -1) * (order === 'first' ? 1 : -1)
  return [...items].sort((a, b) => {
    const x = s.key(a), y = s.key(b)
    const c = x < y ? -1 : x > y ? 1 : 0
    return by === 'usual' ? (at.get(a.game)! - at.get(b.game)!) * (order === 'first' ? 1 : -1) : sign * c || at.get(a.game)! - at.get(b.game)!
  })
}

/** The account's "by:order", or the usual when it's missing or from a newer app. */
export function readSort(v: string | null | undefined): Sort {
  const [by, order] = (v ?? '').split(':')
  return by in SORTS && (order === 'first' || order === 'last') ? { by: by as SortBy, order } : { by: 'usual', order: 'first' }
}
export const writeSort = (s: Sort) => `${s.by}:${s.order}`

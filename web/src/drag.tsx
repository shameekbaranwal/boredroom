import { useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from 'react'

// Rows dragged into a new order by a grip at each row's start. Pointer events, so a finger,
// a mouse and a pen all work; the grip takes the touch (touch-action: none) so the page
// doesn't scroll under it, and the page scrolls by itself near the screen's edges. From
// the keyboard: focus a grip, and ↑ and ↓ move its row one place. Mid-drag the rows stay
// where they are in the page and only slide (moving them would lose the pointer); the new
// order is handed over on the drop.

const EDGE = 72   // px from the top or bottom where the page starts scrolling by itself
const SPEED = 9   // px a frame
const buzz = (ms: number) => navigator.vibrate?.(ms)

type Drop = (ids: string[], moved: string) => void
type Live = {
  id: string; ids: string[]; from: number; tops: number[]; hs: number[]
  y0: number; at: number; order: string[]; scroll: number; drop: Drop
}

export function useReorder() {
  const rows = useRef(new Map<string, HTMLElement>())
  const live = useRef<Live | null>(null)
  const [drag, setDrag] = useState<{ id: string; shifts: Record<string, number> } | null>(null)

  // where the pointer is, in page coordinates, decides the slot
  const track = (clientY: number) => {
    const d = live.current
    if (!d) return
    d.at = clientY
    const dy = clientY + scrollY - d.y0
    const centre = d.tops[d.from] + d.hs[d.from] / 2 + dy
    const others = d.ids.filter(x => x !== d.id)
    const slot = others.filter(x => { const k = d.ids.indexOf(x); return d.tops[k] + d.hs[k] / 2 < centre }).length
    const order = [...others.slice(0, slot), d.id, ...others.slice(slot)]
    if (order.join() !== d.order.join()) buzz(4)
    d.order = order
    // the others slide to their new places; the dragged one follows the finger
    const shifts: Record<string, number> = {}
    let top = d.tops[0]
    for (const x of order) { const k = d.ids.indexOf(x); shifts[x] = x === d.id ? dy : top - d.tops[k]; top += d.hs[k] }
    setDrag({ id: d.id, shifts })
  }
  const edge = () => {
    const d = live.current
    if (!d) return
    const v = d.at < EDGE ? -SPEED : d.at > innerHeight - EDGE ? SPEED : 0
    if (v) { scrollBy(0, v); track(d.at) }
    d.scroll = requestAnimationFrame(edge)
  }
  const end = (keep: boolean) => {
    const d = live.current
    if (!d) return
    cancelAnimationFrame(d.scroll)
    live.current = null
    setDrag(null)
    if (keep && d.order.join() !== d.ids.join()) d.drop(d.order, d.id)
  }

  return {
    dragging: drag !== null,
    /** On each row's outermost element. */
    row: (id: string) => ({
      ref: (el: HTMLElement | null) => { if (el) rows.current.set(id, el); else rows.current.delete(id) },
      className: drag ? (drag.id === id ? 'dragging' : 'shifting') : undefined,
      style: (drag?.shifts[id] ? { transform: `translateY(${drag.shifts[id]}px)` } : undefined) as CSSProperties | undefined,
    }),
    /** On the grip: a button that drags, or moves with ↑ and ↓. */
    grip: (id: string, ids: string[], drop: Drop) => ({
      className: 'grip',
      onPointerDown: (e: PointerEvent<HTMLElement>) => {
        if (e.button !== 0 || live.current) return
        e.preventDefault(); e.stopPropagation()
        e.currentTarget.setPointerCapture(e.pointerId)
        const rects = ids.map(x => rows.current.get(x)?.getBoundingClientRect())
        if (rects.some(r => !r)) return
        buzz(10)
        live.current = {
          id, ids, from: ids.indexOf(id), drop, order: ids, at: e.clientY, y0: e.clientY + scrollY,
          tops: rects.map(r => r!.top + scrollY), hs: rects.map(r => r!.height), scroll: 0,
        }
        live.current.scroll = requestAnimationFrame(edge)
        setDrag({ id, shifts: {} })
      },
      onPointerMove: (e: PointerEvent<HTMLElement>) => { if (live.current) track(e.clientY) },
      onPointerUp: () => end(true),
      onPointerCancel: () => end(false),
      onClick: (e: { stopPropagation: () => void }) => e.stopPropagation(),  // a row's own tap stays the row's
      onKeyDown: (e: KeyboardEvent<HTMLElement>) => {
        const n = ids.indexOf(id), to = e.key === 'ArrowUp' ? n - 1 : e.key === 'ArrowDown' ? n + 1 : -1
        if (to < 0 || to >= ids.length) return
        e.preventDefault(); e.stopPropagation()
        const xs = [...ids];
        [xs[n], xs[to]] = [xs[to], xs[n]]
        drop(xs, id)
        requestAnimationFrame(() => (rows.current.get(id)?.querySelector('.grip') as HTMLElement | null)?.focus())
      },
    }),
  }
}

/** The grip's dots. */
export const Dots = () => (
  <svg viewBox="0 0 10 16" width="10" height="16" aria-hidden="true">
    {[3, 7].flatMap(x => [3, 8, 13].map(y => <circle key={`${x}${y}`} cx={x} cy={y} r="1.3" />))}
  </svg>
)

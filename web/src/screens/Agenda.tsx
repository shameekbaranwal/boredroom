import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Board, type Filing, type Item, type Today } from '../api'
import { headline, left } from '../format'
import { go } from '../router'
import { Av, Clip, Fx, Header, Loading, Nav, Tile, sendOn, useApp, useNow } from '../ui'
import Boards from './Boards'

const playUrl = (i: Item) => (i.links[0] ? `https://${i.links[0]}` : null)

export default function Agenda({ slug, shared }: { slug: string; shared?: string }) {
  const { games, toast } = useApp()
  const [today, setToday] = useState<Today | null>(null)
  const [board, setBoard] = useState<Board | null>(null)
  const [err, setErr] = useState('')
  const [picker, setPicker] = useState(false)
  const now = useNow()

  const load = useCallback(() => {
    api.today(slug).then(setToday).catch(e => setErr(e.message))
    api.board(slug).then(setBoard).catch(() => {})
  }, [slug])
  useEffect(load, [load])

  if (err) return <div className="app"><Header title="boredroom.xlsx" /><div className="center err">{err}</div></div>
  if (!today || !board) return <div className="app"><Header title={`${slug}.xlsx`} meta="agenda" /><Loading what="the agenda" /></div>

  const open = today.items.filter(i => !i.filed), filed = today.items.filter(i => i.filed)
  const next = open[0]
  const extra = board.library.filter(g => !board.you.agenda.includes(g.game)).length
  const placeholders = board.members.filter(m => m.kind === 'placeholder')

  return (
    <div className="app">
      <Header title={`${board.name}.xlsx`} meta="agenda" onTitle={() => setPicker(true)} />
      <Fx fn="agenda" args={[['board', board.name], ['puzzles', 'current']]} />
      <div className="bd">
        <Pasteboard board={board} shared={shared} onFiled={load} />
        <div className="st1">
          <b>{filed.length} of {today.items.length} filed</b>
          {next ? <span>{next.name} resets in {left(next.resets_at, now)}</span> : today.items.length ? <span>all filed · the board thanks you</span> : null}
        </div>
        {placeholders.length > 0 && (
          <button className="more" onClick={() => go(`/b/${slug}/you#seats`)}>
            {placeholders.length} imported seats unclaimed · is one of them yours? →
          </button>
        )}
        {open.map(i => <OpenRow key={i.game} i={i} slug={slug} now={now} />)}
        {filed.length > 0 && <div className="sec">filed</div>}
        {filed.map(i => (
          <div key={i.game} className="it" onClick={() => go(`/b/${slug}/m/${i.game}`)}>
            <Tile game={i.game} name={i.name} />
            <div className="g">
              <div className="nm">{i.name} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>{i.mine?.puzzle}</span></div>
              <div className="sub">
                {i.mine && headline(games[i.game], i.mine.metrics, i.mine.outcome)}
                {i.mine?.late && <span className="stamp">filed late</span>}
                <span>· {i.present}/{i.players} present</span>
              </div>
            </div>
            <div className="pr">
              <span className="pill done">{i.ranked && i.place ? `#${i.place}` : '✓'}</span>
              {i.mine?.forward && <button className="lnk" style={{ fontSize: 12 }} onClick={e => { e.stopPropagation(); sendOn(i.mine!.forward!, toast) }}>send on</button>}
            </div>
          </div>
        ))}
        {today.items.length === 0 && <div className="sub wrap">nothing on your agenda yet. pick your games, or just paste a result: its game joins your agenda.</div>}
        <button className="more" onClick={() => go(`/b/${slug}/you`)}>
          {extra ? `${extra} more in ${board.name}'s library →` : 'your games →'}
        </button>
      </div>
      <Nav slug={slug} on="agenda" />
      {picker && <Boards current={slug} onClose={() => setPicker(false)} />}
    </div>
  )
}

function OpenRow({ i, slug, now }: { i: Item; slug: string; now: number }) {
  const { games } = useApp()
  const url = playUrl(i)
  const ms = new Date(i.resets_at).getTime() - now
  return (
    <div className="it" onClick={() => go(`/b/${slug}/m/${i.game}`)}>
      <Tile game={i.game} name={i.name} />
      <div className="g">
        <div className="nm">{i.name} {i.puzzle && <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>{i.puzzle}</span>}</div>
        <div className="sub">
          {i.present === 0 ? 'no one yet · be first' : <>
            <span className="stack">{i.filed_by.slice(0, 4).map(n => <Av key={n} name={n} />)}</span>
            {i.present}/{i.players} present
            {i.leader && <> · {i.leader.nickname ?? `${i.leader.tied} tied`} {headline(games[i.game], i.leader.metrics)}</>}
          </>}
        </div>
      </div>
      <div className="pr">
        {url ? <a className="pill todo" href={url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>play</a> : <span className="pill todo">open</span>}
        <span className={`rs${ms < 3600000 ? ' urg' : ''}`}>{left(i.resets_at, now)} left</span>
      </div>
    </div>
  )
}

/** The pasteboard: paste a share text, see what the clerk read, then save it or dismiss it.
 *  Saving files it everywhere; the cards then say what happened. */
export function Pasteboard({ board, shared, onFiled }: { board?: Board; shared?: string; onFiled: () => void }) {
  const { games, refreshMe } = useApp()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<{ text: string; source: 'paste' | 'share'; read: Filing } | null>(null)
  const [out, setOut] = useState<Filing | null>(null)
  const [err, setErr] = useState('')
  const [answered, setAnswered] = useState<Record<number, string>>({})
  const ta = useRef<HTMLTextAreaElement>(null)
  const sharedDone = useRef(false)

  const read = useCallback(async (t: string, source: 'paste' | 'share' = 'paste') => {
    if (!t.trim()) return
    setBusy(true); setErr(''); setOut(null); setAnswered({})
    try { setDraft({ text: t, source, read: await api.preview(t) }); setText('') }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }, [])

  const save = async () => {
    if (!draft) return
    setBusy(true); setErr('')
    try {
      const f = await api.paste(draft.text, draft.source)
      setOut(f); setDraft(null)
      // a new game joins your agenda on this board, as "+ add a game" does
      const add = board ? f.events.filter(e => e.kind !== 'not_out_yet' && !board.you.agenda.includes(e.game)).map(e => e.game) : []
      for (const g of new Set(add)) await api.agenda(board!.slug, g, true).catch(() => {})
      if (add.length) refreshMe()
      onFiled()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  useEffect(() => {
    if (shared && !sharedDone.current) { sharedDone.current = true; read(shared, 'share'); history.replaceState(null, '', board ? `/b/${board.slug}` : '/desk') }
  }, [shared, read, board])

  const name = (g: string) => games[g]?.name ?? g
  const replace = async (rid: number, paste: number) => {
    try { await api.replace(rid, paste); setAnswered(a => ({ ...a, [rid]: 'replaced. stamped "amended".' })); onFiled() }
    catch (e) { setErr((e as Error).message) }
  }
  const minutes = (g: string) => board && <button className="lnk" style={{ fontSize: 12, alignSelf: 'flex-start' }} onClick={() => go(`/b/${board.slug}/m/${g}`)}>see how {board.name} did →</button>
  const worth = draft && (draft.read.unknown.length > 0 || draft.read.events.some(e => e.kind === 'filed' || e.kind === 'merged' || e.kind === 'conflict'))

  return (
    <div className="pbw">
      {!draft && <>
        <label className="pb">
          <Clip />
          <textarea ref={ta} rows={text.includes('\n') ? Math.min(8, text.split('\n').length) : 1} placeholder="paste a result" aria-label="paste a result"
            spellCheck={false} value={text} disabled={busy} className="keep"
            onChange={e => setText(e.target.value)}
            onPaste={e => { const t = e.clipboardData.getData('text'); if (t.trim()) { e.preventDefault(); read(t) } }} />
        </label>
        {text.trim() && <div className="pb-a"><button className="btn" onClick={() => read(text)} disabled={busy}>read it</button><button className="lnk" onClick={() => setText('')}>clear</button></div>}
        {!text && navigator.clipboard?.readText && !out && (
          <div className="pb-a"><button className="lnk" onClick={async () => { try { read(await navigator.clipboard.readText()) } catch { ta.current?.focus() } }}>paste from clipboard</button></div>
        )}
      </>}
      {err && <div className="err">{err}</div>}

      {draft && (
        <div className="cards">
          <div className="pb-h">the clerk read</div>
          {draft.read.events.map((e, k) => (
            <div className={`card${e.kind === 'filed' || e.kind === 'merged' ? '' : ' quiet'}`} key={k}>
              {e.kind === 'filed' && <><b>{name(e.game)} {e.puzzle}{e.metrics && Object.keys(e.metrics).length ? ` · ${headline(games[e.game], e.metrics, e.outcome ?? undefined)}` : e.outcome === 'failed' ? ' · failed' : ''}</b>
                <small>{e.late ? 'late · ' : ''}{e.confidence !== 'exact' ? `read as ${e.confidence} · ` : ''}new</small></>}
              {e.kind === 'merged' && <><b>more detail for {name(e.game)} {e.puzzle}</b><small>adds the {e.added.join(', ')}. the score stays.</small></>}
              {e.kind === 'duplicate' && <><b>{name(e.game)} {e.puzzle} is already in the minutes</b><small>nothing new here.</small></>}
              {e.kind === 'not_out_yet' && <><b>{name(e.game)} {e.puzzle} isn't out yet</b><small>file it once it's the current puzzle.</small></>}
              {e.kind === 'conflict' && <><b>{name(e.game)} {e.puzzle} is already filed, with a different result</b><small>save, and you'll pick which one to keep.</small></>}
            </div>
          ))}
          {draft.read.unknown.map((u, k) => (
            <div className="card quiet" key={`u${k}`}><b>we can't read {u.name} yet</b><small>{u.score ? `${u.score} · ` : ''}saving asks the clerk for a parser.</small></div>
          ))}
          {!draft.read.events.length && !draft.read.unknown.length && <div className="card quiet"><b>nothing readable in that</b><small>{draft.read.note || 'paste the share text the game gives you.'}</small></div>}
          <div className="row-a">
            {worth && <button className="btn" onClick={save} disabled={busy}>save to the minutes</button>}
            <button className={worth ? 'lnk' : 'btn ghost'} onClick={() => setDraft(null)} disabled={busy}>{worth ? 'dismiss' : 'ok'}</button>
          </div>
        </div>
      )}

      {out && (
        <div className="cards" style={{ marginTop: 8 }}>
          {out.events.map((e, k) => (
            <div className="card" key={k}>
              {e.kind === 'filed' && <><b>filed {name(e.game)} {e.puzzle}</b><small>{e.late ? 'filed late · ' : ''}{board ? `counts on every board with ${name(e.game)} on your agenda` : 'kept for you. it counts once you join a board that plays it.'}</small>{minutes(e.game)}</>}
              {e.kind === 'merged' && <><b>added the {e.added.join(', ')} to {name(e.game)} {e.puzzle}</b><small>same puzzle, more detail. nothing else changed.</small>{minutes(e.game)}</>}
              {e.kind === 'duplicate' && <><b>{name(e.game)} {e.puzzle} is already in the minutes</b><small>nothing new in that paste.</small></>}
              {e.kind === 'not_out_yet' && <><b>{name(e.game)} {e.puzzle} isn't out yet</b><small>file it once it's the current puzzle.</small></>}
              {e.kind === 'conflict' && e.result_id != null && (answered[e.result_id]
                ? <b>{answered[e.result_id]}</b>
                : <><b>you already filed {name(e.game)} {e.puzzle}, with a different result</b>
                    <div className="row-a"><button className="btn" onClick={() => replace(e.result_id!, out.paste_id)}>replace it</button>
                      <button className="lnk" onClick={() => setAnswered(a => ({ ...a, [e.result_id!]: 'kept the first one.' }))}>keep the first one</button></div></>)}
            </div>
          ))}
          {out.unknown.map((u, k) => (
            <div className="card" key={`u${k}`}>
              <b>we can't read {u.name} yet</b>
              <small>{u.score ? `${u.score} · ` : ''}the clerk has asked for a parser. it'll count once there is one.</small>
            </div>
          ))}
          <div className="row-a"><button className="lnk" onClick={() => setOut(null)}>done</button></div>
        </div>
      )}
    </div>
  )
}

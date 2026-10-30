import { useEffect, useMemo, useState } from 'react'
import { api, setToken, type Board } from '../api'
import { query, usePath } from '../router'
import { Fx, Header, Loading, Nav, Tile, sendOn, useApp } from '../ui'
import { GoogleButton } from './SignIn'

export default function You({ slug }: { slug: string }) {
  const { me, games, refreshMe, toast, signOut } = useApp()
  const path = usePath()
  const welcome = query(path).get('welcome')
  const [b, setB] = useState<Board | null>(null)
  const [nick, setNick] = useState('')
  const [tz, setTz] = useState(me.tz)
  const [q, setQ] = useState('')
  const [err, setErr] = useState('')
  useEffect(() => { api.board(slug).then(x => { setB(x); setNick(x.you.nickname) }).catch(e => setErr(e.message)) }, [slug])
  useEffect(() => { if (location.hash === '#seats') document.getElementById('seats')?.scrollIntoView() }, [b])

  const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone
  const zones = useMemo(() => (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.('timeZone') ?? [], [])
  if (err) return <div className="app"><Header title="you.xlsx" /><div className="center err">{err}</div></div>
  if (!b) return <div className="app"><Header title="you.xlsx" meta={me.username} /><Loading what="your seat" /></div>

  const lib = new Map(b.library.map(g => [g.game, g]))
  const all = Object.values(games).sort((x, y) => x.name.localeCompare(y.name))
  const shown = all.filter(g => lib.has(g.id) || (q && g.name.includes(q.toLowerCase())))
  const mine = new Set(b.you.agenda)
  const toggle = async (g: string) => {
    try { setB(await api.agenda(slug, g, !mine.has(g))) } catch (e) { toast((e as Error).message) }
  }
  const saveNick = async () => {
    if (nick.trim() && nick !== b.you.nickname) {
      try { setB(await api.nickname(slug, nick.trim())); refreshMe(); toast('noted in the minutes') } catch (e) { toast((e as Error).message) }
    }
  }
  const saveTz = async (v: string) => {
    setTz(v)
    try { await api.updateMe({ tz: v }); refreshMe(); toast(`timezone set to ${v}`) } catch (e) { toast((e as Error).message) }
  }
  const placeholders = b.members.filter(m => m.kind === 'placeholder')
  const claim = async (username: string, nickname: string) => {
    if (!confirmClaim(nickname)) return
    try {
      const r = await api.claim(slug, username)
      setB(r.board); refreshMe(); toast(`welcome back. ${r.moved} results are yours now.`)
    } catch (e) { toast((e as Error).message) }
  }
  const invite = `${location.origin}/join/${b.invite_code}`

  return (
    <div className="app">
      <Header title="you.xlsx" meta={me.username} />
      <Fx fn="seat" args={[['board', b.name]]} />
      <div className="bd">
        {welcome && <div className="card"><b>welcome aboard, {b.you.nickname}.</b><small>pick your games below. you can always paste a result to add its game.</small></div>}
        <div className="field">
          <label htmlFor="nick">your name on {b.name}</label>
          <input id="nick" className="input" value={nick} onChange={e => setNick(e.target.value)} onBlur={saveNick} onKeyDown={e => e.key === 'Enter' && saveNick()} />
        </div>

        <div className="sec">your games · {mine.size} of {b.library.length} in {b.name}</div>
        {shown.map(g => {
          const lg = lib.get(g.id)
          return (
            <div key={g.id} className="it" style={{ cursor: 'default' }}>
              <Tile game={g.id} name={g.name} />
              <span className="nm" style={{ flex: 1 }}>{g.name}</span>
              <span className="sub">{lg ? `${lg.players} play${g.ranked ? '' : ' · for fun'}` : 'new to the board'}</span>
              <button className={`add${mine.has(g.id) ? ' on' : ''}`} onClick={() => toggle(g.id)}>{mine.has(g.id) ? '✓ mine' : 'add'}</button>
            </div>
          )
        })}
        <div className="field">
          <label htmlFor="q">add a game to the board</label>
          <input id="q" className="input" placeholder="search the games boredroom reads" value={q} onChange={e => setQ(e.target.value)} />
        </div>

        <div className="sec">invite</div>
        <div className="row-a">
          <span className="sub keep" style={{ flex: 1 }}>{invite}</span>
          <button className="btn" onClick={() => sendOn(`join ${b.name} on boredroom: ${invite}`, toast)}>send invite</button>
        </div>

        {placeholders.length > 0 && <>
          <div className="sec" id="seats">imported seats · claim yours to take its history</div>
          {placeholders.map(p => (
            <div key={p.username} className="it" style={{ cursor: 'default' }}>
              <span className="nm" style={{ flex: 1 }}>{p.nickname}</span>
              <span className="sub">{p.games} games</span>
              <button className="add" onClick={() => claim(p.username, p.nickname)}>that's me</button>
            </div>
          ))}
        </>}

        <div className="sec">members · {b.members.length}</div>
        {b.members.filter(m => m.kind !== 'placeholder').map(m => (
          <div key={m.username} className="mrow">
            <span>{m.nickname} <span className="muted">{m.role === 'chair' ? '· chair' : ''}</span></span>
            <span className="chip">{m.games} games</span>
          </div>
        ))}

        <div className="sec">you</div>
        <div className="field">
          <label htmlFor="tz">timezone {tz !== browserTz && <span className="muted">(this device says {browserTz})</span>}</label>
          {zones.length
            ? <select id="tz" className="input" value={tz} onChange={e => saveTz(e.target.value)}>{zones.map(z => <option key={z} value={z}>{z}</option>)}</select>
            : <input id="tz" className="input" value={tz} onChange={e => setTz(e.target.value)} onBlur={() => saveTz(tz)} />}
        </div>
        <div className="mrow">
          <span>{me.kind === 'account' ? <>signed in{me.email && <span className="muted keep"> · {me.email}</span>}</> : 'guest seat on this device'}</span>
          <span className={`chip${me.kind === 'guest' ? ' seat' : ''}`}>{me.kind === 'account' ? 'signed in' : 'guest seat'}</span>
        </div>
        {me.kind === 'guest' && (
          <div className="field">
            <label>keep this seat: sign in with google</label>
            <GoogleButton onToken={t => { setToken(t); refreshMe(); toast('signed in. your guest seat is now your account.') }} onError={m => toast(m)} />
          </div>
        )}
        <div><button className="lnk" onClick={signOut}>sign out</button></div>
      </div>
      <Nav slug={slug} on="you" />
    </div>
  )
}

function confirmClaim(nickname: string): boolean {
  // a real dialog would be nicer; this keeps it to one tap plus a check
  return window.confirm(`claim ${nickname}'s seat? their history becomes yours.`)
}

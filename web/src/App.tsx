import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, setToken, token, type Game, type Invite, type Me } from './api'
import { go, match, query, usePath } from './router'
import { AppCtx, Loading, NetBar, Toast, Trouble, type Ctx } from './ui'
import { send, type Sent } from './outbox'
import Agenda from './screens/Agenda'
import Desk from './screens/Desk'
import Join from './screens/Join'
import Meeting from './screens/Meeting'
import Minutes from './screens/Minutes'
import Review from './screens/Review'
import NoBoardReview from './screens/NoBoardReview'
import NewBoard from './screens/NewBoard'
import MeScreen from './screens/Personal'
import SignIn from './screens/SignIn'
import You from './screens/You'

const LAST = 'boredroom.board'
const remember = (slug: string) => { try { localStorage.setItem(LAST, slug) } catch { /* fine */ } }
const lastBoard = () => { try { return localStorage.getItem(LAST) } catch { return null } }

/** A corner badge on every non-production instance, so stage is never mistaken for the real thing. */
function EnvBadge() {
  const [env, setEnv] = useState<string | null>(null)
  useEffect(() => {
    api.config().then(c => {
      if (c.environment !== 'production') { setEnv(c.environment); document.title = `${c.environment} · boredroom` }
    }).catch(() => {})
  }, [])
  return env ? <div className="env-badge" role="note">{env}</div> : null
}

export default function App() {
  return <><Shell /><EnvBadge /><NetBar /></>
}

function Shell() {
  const path = usePath()
  const [me, setMe] = useState<Me | null>(null)
  const [games, setGames] = useState<Record<string, Game>>({})
  const [state, setState] = useState<'loading' | 'out' | 'in' | 'away'>(token() ? 'loading' : 'out')
  const [toast, setToastState] = useState<{ msg: string; action?: { label: string; run: () => void } } | null>(null)
  const [invite, setInvite] = useState<Invite | null>(null)

  const refreshMe = useCallback(async () => {
    try { setMe(await api.me()); setState('in') }
    catch (e) { if (e instanceof ApiError && e.status === 401) { setToken(null); setState('out') } else throw e }
  }, [])

  useEffect(() => { api.games().then(gs => setGames(Object.fromEntries(gs.map(g => [g.id, g])))).catch(() => {}) }, [])
  // unreachable, with no copy of your seat yet: say so, and open by itself once it answers
  useEffect(() => { if (state === 'loading') refreshMe().catch(() => setState('away')) }, [state, refreshMe])

  useEffect(() => {
    const out = () => { setMe(null); setState('out'); go('/', true) }
    window.addEventListener('boredroom:signedout', out)
    return () => window.removeEventListener('boredroom:signedout', out)
  }, [])

  // the server's back: try your seat again
  useEffect(() => {
    if (state !== 'away') return
    const back = () => setState('loading')
    window.addEventListener('boredroom:back', back)
    return () => window.removeEventListener('boredroom:back', back)
  }, [state])

  // results held on this device go out once you're in, and say how it went
  useEffect(() => {
    if (state !== 'in') return
    const sent = (e: Event) => {
      const { filed, conflicts, failed } = (e as CustomEvent<Sent>).detail
      const c = conflicts[0]
      if (c && c.result_id != null) {
        const rid = c.result_id
        setToastState({ msg: `${filed ? `filed ${filed} held result${filed > 1 ? 's' : ''}. ` : ''}${games[c.game]?.name ?? c.game} ${c.puzzle} was already filed, differently. kept the first.`,
          action: { label: 'use the new one', run: () => { api.replace(rid, c.paste_id).catch(() => {}) } } })
      } else if (failed.length) setToastState({ msg: `a held result couldn't be filed: ${failed[0]}` })
      else setToastState({ msg: `filed ${filed} held result${filed > 1 ? 's' : ''}.` })
      window.dispatchEvent(new Event('boredroom:back'))  // the screens load what was just filed
    }
    window.addEventListener('boredroom:sent', sent)
    send()
    return () => window.removeEventListener('boredroom:sent', sent)
  }, [state, games])

  const joinCode = match('/join/:code', path)?.code
  useEffect(() => { if (joinCode && state === 'out') api.invite(joinCode).then(setInvite).catch(() => setInvite(null)) }, [joinCode, state])

  const signOut = useCallback(() => {
    api.signOut().catch(() => {}).finally(() => { setToken(null); setMe(null); setState('out'); go('/', true) })
  }, [])

  if (state === 'out') return <SignIn invite={joinCode ? invite : null} onSignedIn={() => setState('loading')} />
  if (state === 'away') return <div className="app"><Trouble err="can't reach boredroom right now. it'll open by itself once it can." retry={() => setState('loading')} /></div>
  if (!me) return <div className="app"><Loading what="your seat" /></div>

  const ctx: Ctx = { me, games, refreshMe, signOut, toast: (msg, action) => setToastState({ msg, action }) }
  return (
    <AppCtx.Provider value={ctx}>
      <Route path={path} me={me} />
      {toast && <Toast {...toast} onDone={() => setToastState(null)} />}
    </AppCtx.Provider>
  )
}

function Route({ path, me }: { path: string; me: Me }) {
  const onBoard = (slug: string) => me.boards.some(b => b.slug === slug)
  let m
  if ((m = match('/join/:code', path))) return <Join code={m.code} />
  if (match('/new', path)) return <NewBoard />
  if (match('/desk', path)) return <Desk />
  if (match('/me', path)) return <MeScreen />
  if (match('/me/close', path)) return <MeScreen page="close" />
  if (match('/meeting', path)) {  // the meeting tab from a screen with no board: your last board's
    const slug = lastBoard() && onBoard(lastBoard()!) ? lastBoard()! : me.boards[0]?.slug
    return <Redirect to={slug ? `/b/${slug}/meeting` : '/desk'} />
  }
  if (match('/review', path)) {  // the review tab from a screen with no board: your last board's, else the empty one
    const slug = lastBoard() && onBoard(lastBoard()!) ? lastBoard()! : me.boards[0]?.slug
    return slug ? <Redirect to={`/b/${slug}/review`} /> : <NoBoardReview />
  }
  if (match('/share', path)) {
    // the android share target: file the text on the board you last used
    const q = query(path), text = [q.get('text'), q.get('url')].filter(Boolean).join('\n')
    const slug = lastBoard() && onBoard(lastBoard()!) ? lastBoard()! : me.boards[0]?.slug
    if (!slug) return <Desk shared={text} />
    return <Agenda slug={slug} shared={text} />
  }
  if ((m = match('/b/:slug', path)) && onBoard(m.slug)) { remember(m.slug); return <Agenda key={m.slug} slug={m.slug} /> }
  if ((m = match('/b/:slug/you', path)) && onBoard(m.slug)) return <You key={m.slug} slug={m.slug} />
  if ((m = match('/b/:slug/you/:page', path)) && onBoard(m.slug)) return <You key={`${m.slug}/${m.page}`} slug={m.slug} page={m.page} />
  if ((m = match('/b/:slug/you/:page/:arg', path)) && onBoard(m.slug)) return <You key={`${m.slug}/${m.page}/${m.arg}`} slug={m.slug} page={m.page} arg={m.arg} />
  if ((m = match('/b/:slug/meeting', path)) && onBoard(m.slug)) return <Meeting key={m.slug} slug={m.slug} day={query(path).get('day') ?? undefined} />
  if ((m = match('/b/:slug/review', path)) && onBoard(m.slug)) return <Review key={m.slug} slug={m.slug} />
  if ((m = match('/b/:slug/m/:game', path)) && onBoard(m.slug)) return <Minutes slug={m.slug} game={m.game} />
  if ((m = match('/b/:slug/m/:game/:day', path)) && onBoard(m.slug)) return <Minutes slug={m.slug} game={m.game} day={m.day} />
  // home: the last board you used, else your first, else your desk
  const slug = lastBoard() && onBoard(lastBoard()!) ? lastBoard()! : me.boards[0]?.slug
  return <Redirect to={slug ? `/b/${slug}` : '/desk'} />
}

function Redirect({ to }: { to: string }) {
  useEffect(() => { go(to, true) }, [to])
  return null
}

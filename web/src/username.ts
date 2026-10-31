// The live "is this username free?" check. The format is checked here, instantly; only a
// well-formed name goes to the server, a quarter-second after typing stops, and each answer
// is remembered for the visit. The server checks again when the name is actually taken.
import { useEffect, useState } from 'react'
import { api } from './api'

export const USERNAME = /^[a-z0-9][a-z0-9_.-]{1,29}$/
export type Check = { state: 'idle' | 'checking' | 'free' | 'taken' | 'bad'; note: string }

const seen = new Map<string, Check>()

export function useUsernameCheck(raw: string, current?: string): Check {
  const name = raw.trim().toLowerCase()
  const local: Check | null =
    !name || name === current ? { state: 'idle', note: '' }
      : !USERNAME.test(name) ? { state: 'bad', note: name.length < 2 ? 'at least 2 characters' : name.length > 30 ? 'at most 30 characters' : 'letters, digits, . _ - only, starting with a letter or digit' }
        : seen.get(name) ?? null
  const [remote, setRemote] = useState<{ name: string; check: Check } | null>(null)
  useEffect(() => {
    if (local) return
    let live = true
    const t = setTimeout(() => {
      api.username(name).then(r => {
        const check: Check = r.available ? { state: 'free', note: r.reason ?? 'available' } : { state: 'taken', note: r.reason === 'taken' ? 'taken' : r.reason ?? 'not available' }
        seen.set(name, check)
        if (live) setRemote({ name, check })
      }).catch(() => { if (live) setRemote({ name, check: { state: 'idle', note: '' } }) })
    }, 250)
    return () => { live = false; clearTimeout(t) }
  }, [name, local === null])  // eslint-disable-line react-hooks/exhaustive-deps
  return local ?? (remote?.name === name ? remote.check : { state: 'checking', note: 'checking…' })
}

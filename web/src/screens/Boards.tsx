import { go } from '../router'
import { Overlay, useApp } from '../ui'
import { JoinByCode } from './Desk'

export default function Boards({ current, onClose }: { current: string; onClose: () => void }) {
  const { me } = useApp()
  return (
    <Overlay title="your boards" onClose={onClose}>
      {me.boards.map(b => (
        <button key={b.slug} className={`bopt${b.slug === current ? ' on' : ''}`} onClick={() => { if (b.slug === current && history.state?.overlay) history.back(); else { onClose(); go(`/b/${b.slug}`) } }}>
          <span style={{ flex: 1 }}><b>{b.name}</b><div className="sub">as {b.nickname}{b.role === 'chair' ? ' · chair' : ''}</div></span>
        </button>
      ))}
      <button className="bopt" onClick={() => { onClose(); go('/new') }}><b style={{ color: 'var(--accent)' }}>+ start a board</b></button>
      <div style={{ padding: '10px 14px 14px' }}><JoinByCode /></div>
    </Overlay>
  )
}

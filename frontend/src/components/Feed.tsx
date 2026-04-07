import type { FeedItem } from '../types'

interface Props {
  feed: FeedItem[]
}

function timeAgo(ts: number): string {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  return `${Math.round(diff / 3600)}h ago`
}

const TYPE_STYLES: Record<string, { icon: string; color: string; bg: string; border: string }> = {
  trade: { icon: '🟢', color: 'var(--green)', bg: '#00ff8809', border: '#00ff8833' },
  skip:  { icon: '⚠️',  color: 'var(--yellow)', bg: '#ffcc0009', border: '#ffcc0033' },
  scan:  { icon: '🔄', color: 'var(--cyan)',  bg: '#00d4ff09', border: '#00d4ff33' },
  error: { icon: '🚨', color: 'var(--red)',   bg: '#ff446609', border: '#ff446633' },
}

function FeedRow({ item, index }: { item: FeedItem; index: number }) {
  const s = TYPE_STYLES[item.type] ?? TYPE_STYLES.scan
  return (
    <div className="ticker-item" style={{
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      borderLeft: `2px solid ${s.border}`,
      background: s.bg,
      animationDelay: `${index * 0.04}s`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>{s.icon}</span>
          <span style={{ fontSize: 10, fontWeight: 600, color: s.color, letterSpacing: '0.04em' }}>
            {item.text}
          </span>
        </div>
        <span style={{ fontSize: 8, color: 'var(--text-dim)' }}>{timeAgo(item.time)}</span>
      </div>
      <div style={{ fontSize: 9, color: 'var(--text-dim)', paddingLeft: 22 }}>
        {item.detail}
      </div>
    </div>
  )
}

export function Feed({ feed }: Props) {
  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <div className="dot" />
        LIVE FEED
        <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--text-dim)' }}>
          {feed.length} events
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {feed.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '40px 20px', fontSize: 11 }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>📻</div>
            Waiting for events…
          </div>
        ) : (
          feed.map((item, i) => <FeedRow key={`${item.time}-${i}`} item={item} index={i} />)
        )}
      </div>
    </div>
  )
}

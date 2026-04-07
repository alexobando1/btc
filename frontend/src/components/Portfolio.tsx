import { useState } from 'react'
import type { Position, Stats } from '../types'

interface Props {
  positions: Position[]
  stats: Stats | null
}

function PositionCard({ pos }: { pos: Position }) {
  const pnl = pos.closed
    ? ((pos.exit_price ?? 0) - pos.entry_price) / pos.entry_price * pos.size_usd
    : (pos.current_price - pos.entry_price) / pos.entry_price * pos.size_usd
  const pct = pos.entry_price > 0
    ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
    : 0
  const positive = pnl >= 0
  const age = Math.round((Date.now() / 1000 - pos.timestamp) / 3600)

  return (
    <div style={{
      background: 'var(--bg3)',
      border: `1px solid ${positive ? '#00ff8833' : '#ff446633'}`,
      borderLeft: `3px solid ${positive ? 'var(--green)' : 'var(--red)'}`,
      borderRadius: 6,
      padding: '10px 12px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      animation: 'slide-in-up 0.3s ease both',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, fontSize: 11, color: 'var(--text)', lineHeight: 1.4, paddingRight: 8 }}>
          {pos.question.length > 50 ? pos.question.slice(0, 50) + '…' : pos.question}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <span style={{
            padding: '1px 6px', borderRadius: 3, fontSize: 9, fontWeight: 700,
            background: pos.side === 'YES' ? '#00ff8822' : '#ff446622',
            color: pos.side === 'YES' ? 'var(--green)' : 'var(--red)',
            border: `1px solid ${pos.side === 'YES' ? '#00ff8844' : '#ff446644'}`,
          }}>
            {pos.side}
          </span>
          {pos.closed && (
            <span style={{ padding: '1px 6px', borderRadius: 3, fontSize: 9, background: '#ffffff11', color: 'var(--text-dim)' }}>
              CLOSED
            </span>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
        <div>
          <div style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>ENTRY</div>
          <div style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>${pos.entry_price.toFixed(3)}</div>
        </div>
        <div>
          <div style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>NOW</div>
          <div style={{ fontSize: 11, color: positive ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
            ${pos.current_price.toFixed(3)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>SIZE</div>
          <div style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>${pos.size_usd.toFixed(0)}</div>
        </div>
        <div>
          <div style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>P&L</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: positive ? 'var(--green)' : 'var(--red)', textShadow: positive ? 'var(--glow-g)' : 'var(--glow-r)' }}>
            {positive ? '+' : ''}{pnl.toFixed(2)} <span style={{ fontSize: 9 }}>({positive ? '+' : ''}{pct.toFixed(1)}%)</span>
          </div>
        </div>
      </div>

      {/* Price progress bar */}
      {!pos.closed && (
        <div style={{ position: 'relative' }}>
          <div className="progress-bar">
            <div className="progress-bar-fill" style={{
              width: `${Math.min(pos.current_price * 100, 100)}%`,
              background: positive ? 'linear-gradient(90deg,var(--green-dim),var(--green))' : 'linear-gradient(90deg,var(--red-dim),var(--red))',
              boxShadow: positive ? '0 0 8px var(--green)' : '0 0 8px var(--red)',
            }} />
          </div>
          <div style={{ fontSize: 8, color: 'var(--text-dim)', marginTop: 3, textAlign: 'right' }}>
            {age}h ago
          </div>
        </div>
      )}
    </div>
  )
}

export function Portfolio({ positions, stats }: Props) {
  const [tab, setTab] = useState<'open' | 'closed'>('open')

  const open = positions.filter(p => !p.closed)
  const closed = positions.filter(p => p.closed)
  const displayed = tab === 'open' ? open : closed

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <div className="dot" />
        PORTFOLIO
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {(['open', 'closed'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              background: tab === t ? '#00d4ff22' : 'transparent',
              border: `1px solid ${tab === t ? 'var(--cyan)' : 'transparent'}`,
              color: tab === t ? 'var(--cyan)' : 'var(--text-dim)',
              padding: '1px 8px', borderRadius: 3, fontSize: 9, cursor: 'pointer',
              fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase',
            }}>
              {t} ({(t === 'open' ? open : closed).length})
            </button>
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>
        <div className="stat-card" style={{ padding: '6px 10px' }}>
          <div className="label">Invested</div>
          <div className="value" style={{ fontSize: 14, color: 'var(--cyan)' }}>
            ${(stats?.total_invested ?? 0).toFixed(0)}
          </div>
        </div>
        <div className="stat-card" style={{ padding: '6px 10px' }}>
          <div className="label">Open P&L</div>
          <div className="value" style={{ fontSize: 14, color: (stats?.unrealized_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {(stats?.unrealized_pnl ?? 0) >= 0 ? '+' : ''}{(stats?.unrealized_pnl ?? 0).toFixed(2)}
          </div>
        </div>
        <div className="stat-card" style={{ padding: '6px 10px' }}>
          <div className="label">Win Rate</div>
          <div className="value" style={{ fontSize: 14, color: 'var(--yellow)' }}>
            {((stats?.win_rate ?? 0) * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {displayed.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', paddingTop: 40, fontSize: 11 }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
            No {tab} positions
          </div>
        ) : (
          displayed.map(p => <PositionCard key={p.id} pos={p} />)
        )}
      </div>
    </div>
  )
}

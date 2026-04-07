import type { Stats } from '../types'

interface Props {
  stats: Stats | null
}

export function StatsBar({ stats }: Props) {
  const items = [
    { label: 'TOTAL TRADES', value: stats?.total_trades ?? 0, format: (v: number) => String(v), color: 'var(--cyan)' },
    { label: 'WINS', value: stats?.wins ?? 0, format: (v: number) => String(v), color: 'var(--green)' },
    { label: 'LOSSES', value: stats?.losses ?? 0, format: (v: number) => String(v), color: 'var(--red)' },
    { label: 'WIN RATE', value: (stats?.win_rate ?? 0) * 100, format: (v: number) => `${v.toFixed(1)}%`, color: 'var(--yellow)' },
    { label: 'REALIZED P&L', value: stats?.realized_pnl ?? 0, format: (v: number) => `${v >= 0 ? '+' : ''}$${v.toFixed(2)}`, color: (stats?.realized_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' },
    { label: 'OPEN P&L', value: stats?.unrealized_pnl ?? 0, format: (v: number) => `${v >= 0 ? '+' : ''}$${v.toFixed(2)}`, color: (stats?.unrealized_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' },
    { label: 'OPEN POSITIONS', value: stats?.open_positions ?? 0, format: (v: number) => String(v), color: 'var(--purple)' },
    { label: 'XP', value: stats?.xp ?? 0, format: (v: number) => v.toLocaleString(), color: 'var(--purple)' },
  ]

  return (
    <div style={{
      display: 'flex',
      gap: 1,
      background: 'var(--bg)',
      borderTop: '1px solid var(--border)',
      flexShrink: 0,
      height: 42,
    }}>
      {items.map((item, i) => (
        <div key={i} style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          gap: 2,
          padding: '0 8px',
          borderRight: i < items.length - 1 ? '1px solid var(--border)' : 'none',
          background: 'var(--bg2)',
        }}>
          <div style={{ fontSize: 7, color: 'var(--text-dim)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            {item.label}
          </div>
          <div style={{ fontFamily: 'var(--font-hud)', fontSize: 13, fontWeight: 700, color: item.color }}>
            {item.format(item.value)}
          </div>
        </div>
      ))}
    </div>
  )
}

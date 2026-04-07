import { useEffect, useState } from 'react'
import type { Stats } from '../types'

const RANKS = [
  { name: 'DEGEN',  minXp: 0,     color: '#5a6080' },
  { name: 'TRADER', minXp: 100,   color: '#00d4ff' },
  { name: 'SHARK',  minXp: 500,   color: '#00ff88' },
  { name: 'WHALE',  minXp: 2000,  color: '#ffcc00' },
  { name: 'LEGEND', minXp: 10000, color: '#a855f7' },
]

function getLevel(xp: number) {
  for (let i = RANKS.length - 1; i >= 0; i--) {
    if (xp >= RANKS[i].minXp) {
      const next = RANKS[i + 1]
      const pct = next
        ? ((xp - RANKS[i].minXp) / (next.minXp - RANKS[i].minXp)) * 100
        : 100
      return { rank: RANKS[i], next, pct: Math.min(pct, 100) }
    }
  }
  return { rank: RANKS[0], next: RANKS[1], pct: 0 }
}

interface Props {
  stats: Stats | null
  connected: boolean
  scanning: boolean
  scanProgress: number
}

export function Header({ stats, connected, scanning, scanProgress }: Props) {
  const [now, setNow] = useState(new Date())
  const [nextScan, setNextScan] = useState(1800)

  useEffect(() => {
    const t = setInterval(() => {
      setNow(new Date())
      setNextScan(prev => (prev <= 1 ? 1800 : prev - 1))
    }, 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (scanning) setNextScan(1800)
  }, [scanning])

  const xp = stats?.xp ?? 0
  const { rank, next, pct } = getLevel(xp)
  const totalPnl = (stats?.unrealized_pnl ?? 0) + (stats?.realized_pnl ?? 0)
  const invested = stats?.total_invested ?? 0
  const pnlPct = invested > 0 ? (totalPnl / invested) * 100 : 0
  const streak = stats?.streak ?? 0

  const mm = String(Math.floor(nextScan / 60)).padStart(2, '0')
  const ss = String(nextScan % 60).padStart(2, '0')

  return (
    <header style={{
      background: 'var(--bg3)',
      borderBottom: '1px solid var(--border)',
      padding: '0 20px',
      height: 64,
      display: 'flex',
      alignItems: 'center',
      gap: 24,
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 180 }}>
        <span style={{ fontSize: 24 }}>🤖</span>
        <div>
          <div style={{ fontFamily: 'var(--font-hud)', fontSize: 14, fontWeight: 900, color: 'var(--cyan)', letterSpacing: '0.1em', textShadow: 'var(--glow-c)' }}>
            POLY<span style={{ color: 'var(--green)', textShadow: 'var(--glow-g)' }}>BOT</span>
          </div>
          <div style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.2em' }}>AUTOMATED TRADER</div>
        </div>
      </div>

      {/* Connection status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 10px', background: connected ? '#00ff8811' : '#ff446611', border: `1px solid ${connected ? '#00ff8844' : '#ff446644'}`, borderRadius: 4 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: connected ? 'var(--green)' : 'var(--red)', boxShadow: connected ? 'var(--glow-g)' : 'var(--glow-r)', animation: 'pulse-dot 2s infinite' }} />
        <span style={{ fontSize: 9, fontFamily: 'var(--font-hud)', letterSpacing: '0.12em', color: connected ? 'var(--green)' : 'var(--red)' }}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>

      {/* Rank + XP bar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 160 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-hud)', fontSize: 10, fontWeight: 700, color: rank.color, letterSpacing: '0.1em' }}>
            {rank.name}
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>
            {xp.toLocaleString()} XP {next ? `/ ${next.minXp.toLocaleString()}` : ''}
          </span>
        </div>
        <div className="xp-bar">
          <div className="xp-bar-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Streak */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 12px', background: streak >= 3 ? '#ff880011' : 'var(--bg2)', border: `1px solid ${streak >= 3 ? '#ff880044' : 'var(--border)'}`, borderRadius: 4 }}>
        <span style={{ fontSize: 16 }}>{streak >= 5 ? '🔥' : streak >= 3 ? '⚡' : '💫'}</span>
        <div>
          <div style={{ fontFamily: 'var(--font-hud)', fontSize: 14, fontWeight: 700, color: streak >= 3 ? '#ff8800' : 'var(--text)', lineHeight: 1 }}>
            {streak}
          </div>
          <div style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>STREAK</div>
        </div>
      </div>

      {/* P&L */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>TOTAL P&L</div>
          <div style={{ fontFamily: 'var(--font-hud)', fontSize: 18, fontWeight: 700, color: totalPnl >= 0 ? 'var(--green)' : 'var(--red)', textShadow: totalPnl >= 0 ? 'var(--glow-g)' : 'var(--glow-r)' }}>
            {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)}
          </div>
        </div>
        <div style={{ padding: '2px 6px', background: pnlPct >= 0 ? '#00ff8822' : '#ff446622', borderRadius: 3, fontSize: 10, color: pnlPct >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
          {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%
        </div>
      </div>

      <div style={{ flex: 1 }} />

      {/* Scan progress */}
      <div style={{ minWidth: 160 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>
            {scanning ? `SCANNING ${scanProgress}%` : 'NEXT SCAN'}
          </span>
          <span style={{ fontSize: 9, color: scanning ? 'var(--cyan)' : 'var(--text-dim)', fontFamily: 'var(--font-hud)' }}>
            {scanning ? `${scanProgress}%` : `${mm}:${ss}`}
          </span>
        </div>
        <div className="progress-bar">
          <div className="progress-bar-fill" style={{ width: scanning ? `${scanProgress}%` : '0%' }} />
        </div>
      </div>

      {/* Clock */}
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: 'var(--font-hud)', fontSize: 14, fontWeight: 700, color: 'var(--text)', letterSpacing: '0.06em' }}>
          {now.toLocaleTimeString('en-US', { hour12: false })}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>
          {now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </div>
      </div>
    </header>
  )
}

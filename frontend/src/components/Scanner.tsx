import { useEffect, useRef } from 'react'
import type { Market } from '../types'

interface Props {
  markets: Market[]
  activeMarket: Market | null
  scanning: boolean
  scanProgress: number
}

function EVBar({ ev }: { ev: number }) {
  const pct = Math.min(Math.abs(ev) * 400, 100)
  const color = ev >= 0.05 ? 'var(--green)' : ev >= 0 ? 'var(--yellow)' : 'var(--red)'
  const glow = ev >= 0.05 ? '0 0 8px var(--green)' : ev >= 0 ? '0 0 6px var(--yellow)' : 'none'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: color,
          boxShadow: glow, borderRadius: 2, transition: 'width 0.6s ease',
        }} />
      </div>
      <span style={{
        fontSize: 9, fontWeight: 600,
        color: ev >= 0.05 ? 'var(--green)' : ev >= 0 ? 'var(--yellow)' : 'var(--red)',
        minWidth: 40, textAlign: 'right',
      }}>
        {ev >= 0 ? '+' : ''}{(ev * 100).toFixed(1)}%
      </span>
    </div>
  )
}

function MarketRow({ market, index, isActive }: { market: Market; index: number; isActive: boolean }) {
  const hasEdge = market.ev >= 0.05
  return (
    <div style={{
      padding: '7px 12px',
      borderBottom: '1px solid var(--border)',
      background: isActive ? '#00d4ff08' : hasEdge ? '#00ff8806' : 'transparent',
      borderLeft: `2px solid ${isActive ? 'var(--cyan)' : hasEdge ? 'var(--green)' : 'transparent'}`,
      transition: 'all 0.3s',
      animation: isActive ? 'slide-in-right 0.2s ease' : undefined,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
          <span style={{ fontSize: 9, color: 'var(--text-dim)', minWidth: 18 }}>#{index + 1}</span>
          <span className={`conf-dot conf-${market.confidence}`} />
          <span style={{ fontSize: 11, color: isActive ? 'var(--cyan)' : hasEdge ? 'var(--green)' : 'var(--text)', lineHeight: 1.3 }}>
            {market.question.length > 52 ? market.question.slice(0, 52) + '…' : market.question}
          </span>
          {hasEdge && <span style={{ fontSize: 9, color: 'var(--green)', marginLeft: 4 }}>◆ EDGE</span>}
          {isActive && <span style={{ fontSize: 9, color: 'var(--cyan)', animation: 'blink 1s infinite' }}>▌ANALYSING</span>}
        </div>
        <div style={{ display: 'flex', gap: 10, fontSize: 10, minWidth: 120, justifyContent: 'flex-end' }}>
          <span style={{ color: 'var(--green)' }}>Y ${market.yes_price.toFixed(2)}</span>
          <span style={{ color: 'var(--red)' }}>N ${market.no_price.toFixed(2)}</span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <EVBar ev={market.ev} />
        </div>
        <span style={{ fontSize: 9, color: 'var(--text-dim)', minWidth: 60, textAlign: 'right' }}>
          AI: {(market.ai_prob * 100).toFixed(0)}% | Vol ${market.volume >= 1e6 ? (market.volume / 1e6).toFixed(1) + 'M' : (market.volume / 1e3).toFixed(0) + 'K'}
        </span>
      </div>
    </div>
  )
}

export function Scanner({ markets, activeMarket, scanning, scanProgress }: Props) {
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (activeMarket && listRef.current) {
      const idx = markets.findIndex(m => m.question === activeMarket.question)
      if (idx >= 0) {
        const el = listRef.current.children[idx] as HTMLElement
        el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    }
  }, [activeMarket, markets])

  const edges = markets.filter(m => m.ev >= 0.05)

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <div className="dot" style={{ background: scanning ? 'var(--cyan)' : 'var(--green)', boxShadow: scanning ? 'var(--glow-c)' : 'var(--glow-g)' }} />
        MARKET SCANNER
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, fontSize: 9 }}>
          <span style={{ color: 'var(--text-dim)' }}>{markets.length} MKTs</span>
          <span style={{ color: 'var(--green)' }}>{edges.length} EDGES</span>
          {scanning && <span style={{ color: 'var(--cyan)', animation: 'blink 1s infinite' }}>SCANNING {scanProgress}%</span>}
        </div>
      </div>

      {/* Column headers */}
      <div style={{ display: 'flex', padding: '5px 12px', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
        <span style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.12em', flex: 1 }}>QUESTION</span>
        <span style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: '0.12em', minWidth: 120, textAlign: 'right' }}>YES / NO</span>
      </div>

      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
        {scanning && <div className="hud-scan" />}
        {markets.map((m, i) => (
          <MarketRow
            key={m.question}
            market={m}
            index={i}
            isActive={activeMarket?.question === m.question}
          />
        ))}
        {markets.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '40px 20px', fontSize: 11 }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>📡</div>
            Connecting to Polymarket CLOB…
          </div>
        )}
      </div>

      {/* Terminal output row */}
      <div style={{
        padding: '5px 12px',
        borderTop: '1px solid var(--border)',
        background: 'var(--bg)',
        fontFamily: 'var(--font-mono)',
        fontSize: 9,
        color: 'var(--text-dim)',
        display: 'flex',
        justifyContent: 'space-between',
      }}>
        <span>
          {scanning
            ? <span className="neon-c">▶ Scanning {scanProgress}% complete…</span>
            : <span>Scan complete — {markets.length} markets loaded</span>}
        </span>
        <span style={{ color: 'var(--text-dim)', animation: 'blink 1.2s infinite' }}>█</span>
      </div>
    </div>
  )
}

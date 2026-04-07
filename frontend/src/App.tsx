import { useEffect, useState } from 'react'
import { useBot } from './hooks/useBot'
import { Header } from './components/Header'
import { Portfolio } from './components/Portfolio'
import { Scanner } from './components/Scanner'
import { Feed } from './components/Feed'
import { PnLChart } from './components/PnLChart'
import { Achievements } from './components/Achievements'
import { StatsBar } from './components/StatsBar'

// Trade executed toast
function TradeToast({ trade, onDone }: { trade: Record<string, unknown> | null; onDone: () => void }) {
  useEffect(() => {
    if (!trade) return
    const t = setTimeout(onDone, 4000)
    return () => clearTimeout(t)
  }, [trade, onDone])

  if (!trade) return null
  return (
    <div style={{
      position: 'fixed', top: 80, right: 20, zIndex: 1000,
      background: 'var(--bg3)',
      border: '1px solid var(--green)',
      borderLeft: '4px solid var(--green)',
      borderRadius: 6,
      padding: '12px 16px',
      minWidth: 280,
      boxShadow: '0 0 30px #00ff8833, 0 4px 20px rgba(0,0,0,0.5)',
      animation: 'slide-in-right 0.3s ease',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 18 }}>🟢</span>
        <span style={{ fontFamily: 'var(--font-hud)', fontSize: 11, color: 'var(--green)', letterSpacing: '0.1em', fontWeight: 700 }}>
          TRADE EXECUTED
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text)', marginBottom: 4 }}>
        {(trade.question as string)?.slice(0, 55)}
      </div>
      <div style={{ display: 'flex', gap: 16, fontSize: 10 }}>
        <span style={{ color: 'var(--green)' }}>BUY {trade.side as string}</span>
        <span style={{ color: 'var(--text-dim)' }}>
          ${(trade.size_usd as number)?.toFixed(0)} @ ${(trade.price as number)?.toFixed(3)}
        </span>
        <span style={{ color: 'var(--cyan)' }}>
          EV +{((trade.ev as number) * 100)?.toFixed(1)}%
        </span>
      </div>
    </div>
  )
}

export default function App() {
  const bot = useBot()
  const [toast, setToast] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    if (bot.lastTrade) setToast(bot.lastTrade)
  }, [bot.lastTrade])

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      background: 'var(--bg)',
    }}>
      {/* Header */}
      <Header
        stats={bot.stats}
        balance={bot.balance}
        connected={bot.connected}
        scanning={bot.scanning}
        scanProgress={bot.scanProgress}
        botRunning={bot.botRunning}
        onStop={bot.emergencyStop}
        onResume={bot.resumeBot}
      />

      {/* Main grid */}
      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '300px 1fr 240px',
        gridTemplateRows: '1fr 200px',
        gap: 6,
        padding: 6,
        overflow: 'hidden',
        minHeight: 0,
      }}>
        {/* Column 1: Portfolio (spans 2 rows) */}
        <div style={{ gridRow: '1 / 3', overflow: 'hidden' }}>
          <Portfolio positions={bot.positions} stats={bot.stats} />
        </div>

        {/* Center top: Scanner */}
        <div style={{ overflow: 'hidden' }}>
          <Scanner
            markets={bot.markets}
            activeMarket={bot.activeMarket}
            scanning={bot.scanning}
            scanProgress={bot.scanProgress}
          />
        </div>

        {/* Right: Feed (spans 2 rows) */}
        <div style={{ gridRow: '1 / 3', overflow: 'hidden' }}>
          <Feed feed={bot.feed} />
        </div>

        {/* Center bottom: split between chart and achievements */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 6,
          overflow: 'hidden',
        }}>
          <PnLChart history={bot.pnlHistory} />
          <Achievements stats={bot.stats} />
        </div>
      </div>

      {/* Bottom stats bar */}
      <StatsBar stats={bot.stats} />

      {/* Trade toast */}
      <TradeToast trade={toast} onDone={() => setToast(null)} />
    </div>
  )
}

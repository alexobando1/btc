import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import type { PnLPoint } from '../types'

interface Props {
  history: PnLPoint[]
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null
  const val = payload[0].value as number
  return (
    <div style={{
      background: 'var(--bg3)', border: '1px solid var(--border)',
      padding: '6px 10px', borderRadius: 4, fontSize: 10,
    }}>
      <div style={{ color: 'var(--text-dim)', marginBottom: 2 }}>{payload[0].payload.label}</div>
      <div style={{ color: val >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
        {val >= 0 ? '+' : ''}{val.toFixed(2)} USDC
      </div>
    </div>
  )
}

export function PnLChart({ history }: Props) {
  const lastVal = history[history.length - 1]?.pnl ?? 0
  const positive = lastVal >= 0
  const minVal = Math.min(...history.map(h => h.pnl), 0)
  const maxVal = Math.max(...history.map(h => h.pnl), 0)

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <div className="dot" style={{ background: positive ? 'var(--green)' : 'var(--red)' }} />
        P&L HISTORY (7d)
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-hud)', fontSize: 12, fontWeight: 700, color: positive ? 'var(--green)' : 'var(--red)', textShadow: positive ? 'var(--glow-g)' : 'var(--glow-r)' }}>
            {positive ? '+' : ''}{lastVal.toFixed(2)} USDC
          </span>
        </div>
      </div>

      <div style={{ flex: 1, padding: '8px 4px 4px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={positive ? '#00ff88' : '#ff4466'} stopOpacity={0.3} />
                <stop offset="95%" stopColor={positive ? '#00ff88' : '#ff4466'} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="label"
              tick={{ fill: '#5a6080', fontSize: 8, fontFamily: 'JetBrains Mono' }}
              axisLine={false} tickLine={false}
            />
            <YAxis
              tick={{ fill: '#5a6080', fontSize: 8, fontFamily: 'JetBrains Mono' }}
              axisLine={false} tickLine={false} width={40}
              tickFormatter={v => `$${v}`}
              domain={[Math.floor(minVal * 1.1), Math.ceil(maxVal * 1.1)]}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#1e2340', strokeWidth: 1 }} />
            <ReferenceLine y={0} stroke="#1e2340" strokeDasharray="3 3" />
            <Area
              type="monotone" dataKey="pnl"
              stroke={positive ? '#00ff88' : '#ff4466'}
              strokeWidth={2}
              fill="url(#pnlGrad)"
              dot={false}
              activeDot={{ r: 4, fill: positive ? '#00ff88' : '#ff4466', stroke: 'var(--bg)', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

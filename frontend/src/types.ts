export interface Position {
  id: number
  question: string
  side: 'YES' | 'NO'
  entry_price: number
  current_price: number
  exit_price?: number
  size_usd: number
  timestamp: number
  closed: boolean
}

export interface Market {
  question: string
  yes_price: number
  no_price: number
  volume: number
  ev: number
  ai_prob: number
  confidence: 'high' | 'medium' | 'low'
}

export interface Stats {
  open_positions: number
  total_invested: number
  unrealized_pnl: number
  realized_pnl: number
  total_trades: number
  win_rate: number
  wins: number
  losses: number
  xp: number
  streak: number
}

export interface FeedItem {
  type: 'trade' | 'skip' | 'scan' | 'error'
  text: string
  detail: string
  time: number
}

export interface PnLPoint {
  ts: number
  pnl: number
  label: string
}

export interface WSEvent {
  event: 'market_analysed' | 'scan_complete' | 'trade_executed'
  data: Record<string, unknown>
}

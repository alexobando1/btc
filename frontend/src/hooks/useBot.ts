import { useEffect, useRef, useState, useCallback } from 'react'
import type { Position, Market, Stats, FeedItem, PnLPoint } from '../types'

const API = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? ''

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`)
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json()
}

interface WSEvent {
  event: 'market_analysed' | 'scan_complete' | 'trade_executed'
  data: Record<string, unknown>
}

interface ScannedMarket {
  question: string
  yes_price: number
  no_price: number
  volume: number
  ev: number
  ai_prob: number
  confidence: 'high' | 'medium' | 'low'
  index: number
  total: number
}

export function useBot() {
  const [positions, setPositions] = useState<Position[]>([])
  const [markets, setMarkets] = useState<Market[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [feed, setFeed] = useState<FeedItem[]>([])
  const [pnlHistory, setPnlHistory] = useState<PnLPoint[]>([])
  const [connected, setConnected] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState(0)
  const [activeMarket, setActiveMarket] = useState<Market | null>(null)
  const [lastTrade, setLastTrade] = useState<Record<string, unknown> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const loadAll = useCallback(async () => {
    try {
      const [posData, statsData, mktData, feedData, pnlData] = await Promise.all([
        apiFetch<{ positions: Position[] }>('/api/positions'),
        apiFetch<Stats>('/api/stats'),
        apiFetch<{ markets: Market[] }>('/api/markets'),
        apiFetch<{ feed: FeedItem[] }>('/api/feed'),
        apiFetch<{ history: PnLPoint[] }>('/api/pnl_history'),
      ])
      setPositions(posData.positions)
      setStats(statsData)
      setMarkets(mktData.markets)
      setFeed(feedData.feed)
      setPnlHistory(pnlData.history)
    } catch (e) {
      console.error('loadAll failed:', e)
    }
  }, [])

  useEffect(() => {
    loadAll()
    const interval = setInterval(loadAll, 60_000)
    return () => clearInterval(interval)
  }, [loadAll])

  useEffect(() => {
    const wsUrl = API
      ? `${API.replace('http', 'ws')}/ws`
      : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

    const connect = () => {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, 3000)
      }
      ws.onmessage = (evt: MessageEvent<string>) => {
        const msg = JSON.parse(evt.data) as WSEvent
        if (msg.event === 'market_analysed') {
          const d = msg.data as unknown as ScannedMarket
          setScanning(true)
          setScanProgress(Math.round((d.index / d.total) * 100))
          setActiveMarket({
            question: d.question,
            yes_price: d.yes_price,
            no_price: d.no_price,
            volume: d.volume,
            ev: d.ev,
            ai_prob: d.ai_prob,
            confidence: d.confidence,
          })
        } else if (msg.event === 'scan_complete') {
          setScanning(false)
          setScanProgress(100)
          setActiveMarket(null)
          const scanned = Number(msg.data.markets_scanned ?? 0)
          const edges = Number(msg.data.edges_found ?? 0)
          setFeed(prev => [{
            type: 'scan',
            text: 'SCAN COMPLETE',
            detail: `${scanned} markets | ${edges} edges`,
            time: Date.now() / 1000,
          }, ...prev.slice(0, 49)])
        } else if (msg.event === 'trade_executed') {
          setLastTrade(msg.data)
          const side = String(msg.data.side ?? '')
          const question = String(msg.data.question ?? '')
          const size = Number(msg.data.size_usd ?? 0)
          const ev = Number(msg.data.ev ?? 0)
          setFeed(prev => [{
            type: 'trade',
            text: `BUY ${side} – ${question}`,
            detail: `$${size.toFixed(0)} | EV ${(ev * 100).toFixed(1)}%`,
            time: Date.now() / 1000,
          }, ...prev.slice(0, 49)])
          loadAll()
        }
      }
    }

    connect()
    return () => wsRef.current?.close()
  }, [loadAll])

  return {
    positions,
    markets,
    stats,
    feed,
    pnlHistory,
    connected,
    scanning,
    scanProgress,
    activeMarket,
    lastTrade,
  }
}

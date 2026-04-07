import { useEffect, useRef, useState, useCallback } from 'react'
import type { Position, Market, Stats, FeedItem, PnLPoint, WSEvent } from '../types'

const API = import.meta.env.VITE_API_URL ?? ''

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`)
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json()
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
  const [lastTrade, setLastTrade] = useState<WSEvent['data'] | null>(null)
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
      ws.onmessage = (evt) => {
        const msg: WSEvent = JSON.parse(evt.data)
        if (msg.event === 'market_analysed') {
          const d = msg.data as Market & { index: number; total: number }
          setScanning(true)
          setScanProgress(Math.round((d.index / d.total) * 100))
          setActiveMarket(d)
        } else if (msg.event === 'scan_complete') {
          setScanning(false)
          setScanProgress(100)
          setActiveMarket(null)
          const d = msg.data as { markets_scanned: number; edges_found: number }
          setFeed(prev => [{
            type: 'scan',
            text: 'SCAN COMPLETE',
            detail: `${d.markets_scanned} markets | ${d.edges_found} edges`,
            time: Date.now() / 1000,
          }, ...prev.slice(0, 49)])
        } else if (msg.event === 'trade_executed') {
          setLastTrade(msg.data)
          const d = msg.data as { question: string; side: string; size_usd: number; ev: number }
          setFeed(prev => [{
            type: 'trade',
            text: `BUY ${d.side} – ${d.question}`,
            detail: `$${d.size_usd.toFixed(0)} | EV ${(d.ev * 100).toFixed(1)}%`,
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

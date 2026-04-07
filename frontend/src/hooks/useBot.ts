import { useEffect, useRef, useState, useCallback } from 'react'
import type { Position, Market, Stats, FeedItem, PnLPoint, WalletBalance } from '../types'

const API = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? ''

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`)
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json()
}

async function apiPost<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { method: 'POST' })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json()
}

interface WSEvent {
  event: 'market_analysed' | 'scan_complete' | 'trade_executed' | 'bot_stopped' | 'bot_started'
  data: Record<string, unknown>
}

interface ScannedMarket {
  question: string; yes_price: number; no_price: number
  volume: number; ev: number; ai_prob: number
  confidence: 'high' | 'medium' | 'low'; index: number; total: number
}

export function useBot() {
  const [positions, setPositions] = useState<Position[]>([])
  const [markets, setMarkets] = useState<Market[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [feed, setFeed] = useState<FeedItem[]>([])
  const [pnlHistory, setPnlHistory] = useState<PnLPoint[]>([])
  const [balance, setBalance] = useState<WalletBalance | null>(null)
  const [botRunning, setBotRunning] = useState(true)
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
    } catch (e) { console.error('loadAll:', e) }
  }, [])

  const loadBalance = useCallback(async () => {
    try {
      const b = await apiFetch<WalletBalance>('/api/balance')
      setBalance(b)
    } catch (e) { console.error('balance:', e) }
  }, [])

  const loadBotStatus = useCallback(async () => {
    try {
      const s = await apiFetch<{ running: boolean }>('/api/bot_status')
      setBotRunning(s.running)
    } catch (e) { console.error('bot_status:', e) }
  }, [])

  const emergencyStop = useCallback(async () => {
    await apiPost('/api/stop')
    setBotRunning(false)
  }, [])

  const resumeBot = useCallback(async () => {
    await apiPost('/api/start')
    setBotRunning(true)
  }, [])

  useEffect(() => {
    loadAll()
    loadBalance()
    loadBotStatus()
    const t1 = setInterval(loadAll, 30_000)
    const t2 = setInterval(loadBalance, 15_000)
    const t3 = setInterval(loadBotStatus, 10_000)
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3) }
  }, [loadAll, loadBalance, loadBotStatus])

  useEffect(() => {
    const wsUrl = API
      ? `${API.replace('http', 'ws')}/ws`
      : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

    const connect = () => {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onopen = () => setConnected(true)
      ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
      ws.onmessage = (evt: MessageEvent<string>) => {
        const msg = JSON.parse(evt.data) as WSEvent
        if (msg.event === 'market_analysed') {
          const d = msg.data as unknown as ScannedMarket
          setScanning(true)
          setScanProgress(Math.round((d.index / d.total) * 100))
          setActiveMarket({ question: d.question, yes_price: d.yes_price, no_price: d.no_price, volume: d.volume, ev: d.ev, ai_prob: d.ai_prob, confidence: d.confidence })
        } else if (msg.event === 'scan_complete') {
          setScanning(false); setScanProgress(100); setActiveMarket(null)
          const scanned = Number(msg.data.markets_scanned ?? 0)
          const edges = Number(msg.data.edges_found ?? 0)
          setFeed(prev => [{ type: 'scan', text: 'SCAN COMPLETE', detail: `${scanned} markets | ${edges} edges`, time: Date.now() / 1000 }, ...prev.slice(0, 49)])
        } else if (msg.event === 'trade_executed') {
          setLastTrade(msg.data)
          setFeed(prev => [{ type: 'trade', text: `BUY ${msg.data.side} – ${msg.data.question}`, detail: `$${Number(msg.data.size_usd).toFixed(0)} | EV ${(Number(msg.data.ev) * 100).toFixed(1)}%`, time: Date.now() / 1000 }, ...prev.slice(0, 49)])
          loadAll(); loadBalance()
        } else if (msg.event === 'bot_stopped') {
          setBotRunning(false)
        } else if (msg.event === 'bot_started') {
          setBotRunning(true)
        }
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [loadAll, loadBalance])

  return {
    positions, markets, stats, feed, pnlHistory,
    balance, botRunning,
    connected, scanning, scanProgress, activeMarket, lastTrade,
    emergencyStop, resumeBot,
  }
}

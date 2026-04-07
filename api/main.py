"""
Polymarket Bot Dashboard API
FastAPI backend — serves REST + WebSocket + React SPA static files.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DB_PATH = os.getenv("DB_PATH", "positions.db")
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

# ---------------------------------------------------------------------------
# Mock data (shown when DB is empty / bot not yet running)
# ---------------------------------------------------------------------------
MOCK_MARKETS = [
    {"question": "Will Fed cut rates in June 2026?", "yes_price": 0.42, "no_price": 0.58, "volume": 1_200_000, "ev": 0.183, "ai_prob": 0.61, "confidence": "high"},
    {"question": "BTC above $95K by March 31?", "yes_price": 0.35, "no_price": 0.65, "volume": 890_000, "ev": 0.081, "ai_prob": 0.44, "confidence": "medium"},
    {"question": "NYC temp > 60F on March 20?", "yes_price": 0.28, "no_price": 0.72, "volume": 340_000, "ev": 0.031, "ai_prob": 0.31, "confidence": "low"},
    {"question": "Trump pardons before April?", "yes_price": 0.61, "no_price": 0.39, "volume": 2_100_000, "ev": 0.143, "ai_prob": 0.74, "confidence": "high"},
    {"question": "ETH flips BNB market cap?", "yes_price": 0.15, "no_price": 0.85, "volume": 156_000, "ev": -0.02, "ai_prob": 0.14, "confidence": "low"},
    {"question": "SpaceX Starship orbital by Q2 2026?", "yes_price": 0.55, "no_price": 0.45, "volume": 670_000, "ev": 0.092, "ai_prob": 0.67, "confidence": "medium"},
    {"question": "Apple releases AR glasses in 2026?", "yes_price": 0.38, "no_price": 0.62, "volume": 420_000, "ev": -0.01, "ai_prob": 0.37, "confidence": "low"},
    {"question": "Inflation below 2% in 2026?", "yes_price": 0.29, "no_price": 0.71, "volume": 980_000, "ev": 0.073, "ai_prob": 0.38, "confidence": "medium"},
]

MOCK_POSITIONS = [
    {
        "id": 1, "question": "Will Fed cut rates in June 2026?", "side": "YES",
        "entry_price": 0.42, "current_price": 0.51, "size_usd": 112.0,
        "timestamp": time.time() - 3600 * 6, "closed": False,
    },
    {
        "id": 2, "question": "Trump pardons before April?", "side": "YES",
        "entry_price": 0.61, "current_price": 0.68, "size_usd": 98.0,
        "timestamp": time.time() - 3600 * 2, "closed": False,
    },
    {
        "id": 3, "question": "SpaceX Starship orbital by Q2 2026?", "side": "YES",
        "entry_price": 0.55, "current_price": 0.58, "size_usd": 60.0,
        "timestamp": time.time() - 3600 * 1, "closed": False,
    },
]

MOCK_CLOSED = [
    {
        "id": 4, "question": "BTC above $80K by Jan 31?", "side": "YES",
        "entry_price": 0.45, "exit_price": 0.89, "size_usd": 80.0,
        "timestamp": time.time() - 3600 * 48, "closed": True,
    },
    {
        "id": 5, "question": "ETH staking yield > 5%?", "side": "NO",
        "entry_price": 0.32, "exit_price": 0.11, "size_usd": 45.0,
        "timestamp": time.time() - 3600 * 72, "closed": True,
    },
    {
        "id": 6, "question": "Solana above $200 by Feb?", "side": "YES",
        "entry_price": 0.61, "exit_price": 0.91, "size_usd": 55.0,
        "timestamp": time.time() - 3600 * 96, "closed": True,
    },
]

MOCK_FEED = [
    {"type": "trade", "text": "BUY YES – Will Fed cut rates?", "detail": "$112 @ $0.42 | EV +18.3%", "time": time.time() - 600},
    {"type": "trade", "text": "BUY YES – Trump pardons before April?", "detail": "$98 @ $0.61 | EV +14.3%", "time": time.time() - 7200},
    {"type": "skip", "text": "SKIP – ETH flips BNB market cap?", "detail": "Spread > 2% (low liquidity)", "time": time.time() - 7400},
    {"type": "trade", "text": "BUY YES – SpaceX Starship orbital?", "detail": "$60 @ $0.55 | EV +9.2%", "time": time.time() - 3700},
    {"type": "scan", "text": "SCAN COMPLETE", "detail": "53 markets | 3 edges | next in 30min", "time": time.time() - 3600},
]

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------
class WSManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.connections.discard(ws) if hasattr(self.connections, "discard") else None
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: Any) -> None:
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = WSManager()


# ---------------------------------------------------------------------------
# Simulated scan events pushed over WebSocket
# ---------------------------------------------------------------------------
async def simulate_scanner() -> None:
    """Push fake scan events every 30 seconds so the UI feels alive."""
    await asyncio.sleep(5)
    scan_num = 0
    while True:
        scan_num += 1
        markets = random.sample(MOCK_MARKETS, k=len(MOCK_MARKETS))
        for i, m in enumerate(markets):
            await asyncio.sleep(0.4)
            await ws_manager.broadcast({
                "event": "market_analysed",
                "data": {**m, "index": i + 1, "total": len(markets)},
            })

        edges = [m for m in markets if m["ev"] > 0.05]
        await ws_manager.broadcast({
            "event": "scan_complete",
            "data": {
                "markets_scanned": len(markets),
                "edges_found": len(edges),
                "scan_num": scan_num,
                "timestamp": time.time(),
            },
        })

        # Occasionally fire a fake trade
        if edges and random.random() > 0.5:
            edge = random.choice(edges)
            await asyncio.sleep(1)
            await ws_manager.broadcast({
                "event": "trade_executed",
                "data": {
                    "question": edge["question"],
                    "side": "YES" if edge["ai_prob"] > 0.5 else "NO",
                    "price": edge["yes_price"] if edge["ai_prob"] > 0.5 else edge["no_price"],
                    "size_usd": round(random.uniform(40, 150), 2),
                    "ev": edge["ev"],
                    "timestamp": time.time(),
                },
            })

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(simulate_scanner())
    yield


app = FastAPI(lifespan=lifespan, title="Polymarket Bot Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# DB helpers (fall back to mock if DB absent / empty)
# ---------------------------------------------------------------------------
async def db_get_positions() -> list[dict]:
    try:
        if not Path(DB_PATH).exists():
            return []
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM positions ORDER BY timestamp DESC") as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.get("/api/positions")
async def get_positions():
    rows = await db_get_positions()
    if not rows:
        return {"positions": MOCK_POSITIONS + MOCK_CLOSED, "source": "mock"}
    return {"positions": rows, "source": "live"}


@app.get("/api/stats")
async def get_stats():
    rows = await db_get_positions()
    if not rows:
        positions = MOCK_POSITIONS
        closed = MOCK_CLOSED
    else:
        positions = [r for r in rows if not r.get("closed")]
        closed = [r for r in rows if r.get("closed")]

    open_pnl = sum(
        (p["current_price"] - p["entry_price"]) / p["entry_price"] * p["size_usd"]
        for p in positions
        if p.get("entry_price", 0) > 0
    )
    total_invested = sum(p["size_usd"] for p in positions)

    wins = [
        p for p in closed
        if p.get("exit_price", 0) > p.get("entry_price", 0)
    ]
    win_rate = len(wins) / len(closed) if closed else 0.0

    realized_pnl = sum(
        (p.get("exit_price", 0) - p.get("entry_price", 0)) / p.get("entry_price", 1) * p["size_usd"]
        for p in closed
        if p.get("entry_price", 0) > 0
    )

    # XP: 10 per trade, 50 bonus per win
    xp = len(closed) * 10 + len(wins) * 50 + max(0, int(realized_pnl))

    return {
        "open_positions": len(positions),
        "total_invested": round(total_invested, 2),
        "unrealized_pnl": round(open_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_trades": len(closed),
        "win_rate": round(win_rate, 4),
        "wins": len(wins),
        "losses": len(closed) - len(wins),
        "xp": xp,
        "streak": min(len(wins), 7),  # simplified
    }


@app.get("/api/markets")
async def get_markets():
    return {"markets": MOCK_MARKETS}


@app.get("/api/feed")
async def get_feed():
    return {"feed": sorted(MOCK_FEED, key=lambda x: x["time"], reverse=True)}


@app.get("/api/pnl_history")
async def get_pnl_history():
    """Generate a 7-day P&L history for the chart."""
    now = time.time()
    day = 86400
    points = []
    pnl = 0.0
    for i in range(7, -1, -1):
        ts = now - i * day
        delta = random.gauss(4, 12)
        pnl += delta
        points.append({"ts": ts, "pnl": round(pnl, 2), "label": f"-{i}d" if i > 0 else "now"})
    return {"history": points}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Serve React SPA (must be last)
# ---------------------------------------------------------------------------
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return FileResponse(str(FRONTEND_DIST / "index.html"))

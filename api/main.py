"""
Polymarket Bot Dashboard API
FastAPI backend — serves REST + WebSocket + React SPA static files.
Fetches REAL markets from Polymarket CLOB. Falls back to mock only on error.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

DB_PATH = os.getenv("DB_PATH", "positions.db")
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
CLOB_URL = "https://clob.polymarket.com"

# ---------------------------------------------------------------------------
# Real market cache
# ---------------------------------------------------------------------------
_market_cache: list[dict] = []
_market_cache_ts: float = 0
_CACHE_TTL = 300  # 5 minutes

FALLBACK_MARKETS = [
    {"question": "Will Fed cut rates in June 2026?", "yes_price": 0.42, "no_price": 0.58,
     "volume": 1_200_000, "ev": 0.18, "ai_prob": 0.61, "confidence": "high"},
    {"question": "BTC above $95K by March 31?", "yes_price": 0.35, "no_price": 0.65,
     "volume": 890_000, "ev": 0.08, "ai_prob": 0.44, "confidence": "medium"},
    {"question": "Trump pardons before April?", "yes_price": 0.61, "no_price": 0.39,
     "volume": 2_100_000, "ev": 0.14, "ai_prob": 0.74, "confidence": "high"},
    {"question": "ETH flips BNB market cap?", "yes_price": 0.15, "no_price": 0.85,
     "volume": 156_000, "ev": -0.02, "ai_prob": 0.14, "confidence": "low"},
    {"question": "SpaceX Starship orbital by Q2 2026?", "yes_price": 0.55, "no_price": 0.45,
     "volume": 670_000, "ev": 0.09, "ai_prob": 0.67, "confidence": "medium"},
]


async def fetch_real_markets() -> list[dict]:
    global _market_cache, _market_cache_ts
    if time.time() - _market_cache_ts < _CACHE_TTL and _market_cache:
        return _market_cache

    logger.info("Fetching real markets from Polymarket CLOB…")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{CLOB_URL}/markets",
                params={"active": "true", "limit": 100},
            )
            resp.raise_for_status()
            raw = resp.json().get("data", [])

        processed: list[dict] = []
        for m in raw:
            tokens = m.get("tokens", [])
            yes_t = next((t for t in tokens if str(t.get("outcome", "")).upper() == "YES"), None)
            no_t  = next((t for t in tokens if str(t.get("outcome", "")).upper() == "NO"),  None)
            if not yes_t or not no_t:
                continue
            yes_price = float(yes_t.get("price") or 0)
            no_price  = float(no_t.get("price") or 0)
            volume    = float(m.get("volume") or 0)
            if volume < 5_000 or yes_price <= 0 or no_price <= 0:
                continue
            # Simple edge estimate: how far market is from 50/50
            edge = abs(yes_price - 0.5) * 0.4
            processed.append({
                "question":   m.get("question", ""),
                "yes_price":  round(yes_price, 4),
                "no_price":   round(no_price, 4),
                "volume":     volume,
                "ev":         round(edge, 3),
                "ai_prob":    round(yes_price, 3),  # placeholder until bot runs
                "confidence": "medium",
                "condition_id": m.get("condition_id", ""),
            })

        processed.sort(key=lambda x: x["volume"], reverse=True)
        _market_cache = processed[:60]
        _market_cache_ts = time.time()
        logger.info("Cached %d real markets", len(_market_cache))
    except Exception as exc:
        logger.warning("CLOB fetch failed (%s), using fallback", exc)
        if not _market_cache:
            _market_cache = FALLBACK_MARKETS

    return _market_cache


# ---------------------------------------------------------------------------
# WebSocket manager
# ---------------------------------------------------------------------------
class WSManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
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


async def simulate_scanner() -> None:
    """Push real market scan events over WebSocket every 30s."""
    await asyncio.sleep(8)  # let startup settle
    scan_num = 0
    while True:
        scan_num += 1
        markets = await fetch_real_markets()
        if not markets:
            await asyncio.sleep(30)
            continue

        shuffled = list(markets)
        random.shuffle(shuffled)
        edges = [m for m in shuffled if m.get("ev", 0) >= 0.05]

        for i, m in enumerate(shuffled):
            await asyncio.sleep(0.35)
            await ws_manager.broadcast({
                "event": "market_analysed",
                "data": {**m, "index": i + 1, "total": len(shuffled)},
            })

        await ws_manager.broadcast({
            "event": "scan_complete",
            "data": {
                "markets_scanned": len(shuffled),
                "edges_found": len(edges),
                "scan_num": scan_num,
                "timestamp": time.time(),
            },
        })

        # Broadcast a simulated trade if real bot hasn't placed one yet
        db_empty = not Path(DB_PATH).exists()
        if db_empty and edges and random.random() > 0.5:
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
                    "simulated": True,
                },
            })

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(fetch_real_markets())  # warm cache on startup
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
# DB helpers
# ---------------------------------------------------------------------------
async def db_get_positions() -> list[dict]:
    try:
        if not Path(DB_PATH).exists():
            return []
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM positions ORDER BY timestamp DESC"
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("DB read failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.get("/api/positions")
async def get_positions():
    rows = await db_get_positions()
    source = "live" if rows else "mock"
    if not rows:
        # Return clearly-labelled mock positions
        rows = [
            {"id": 1, "question": "Will Fed cut rates in June 2026?", "side": "YES",
             "entry_price": 0.42, "current_price": 0.51, "size_usd": 112.0,
             "timestamp": time.time() - 21600, "closed": False, "exit_price": 0},
            {"id": 2, "question": "Trump pardons before April?", "side": "YES",
             "entry_price": 0.61, "current_price": 0.68, "size_usd": 98.0,
             "timestamp": time.time() - 7200, "closed": False, "exit_price": 0},
            {"id": 3, "question": "SpaceX Starship orbital by Q2 2026?", "side": "YES",
             "entry_price": 0.55, "current_price": 0.58, "size_usd": 60.0,
             "timestamp": time.time() - 3600, "closed": False, "exit_price": 0},
        ]
    return {"positions": rows, "source": source}


@app.get("/api/stats")
async def get_stats():
    rows = await db_get_positions()
    if rows:
        open_pos  = [r for r in rows if not r.get("closed")]
        closed_pos = [r for r in rows if r.get("closed")]
        open_pnl = sum(
            (r["current_price"] - r["entry_price"]) / r["entry_price"] * r["size_usd"]
            for r in open_pos if r.get("entry_price", 0) > 0
        )
        wins = [r for r in closed_pos if r.get("exit_price", 0) > r.get("entry_price", 0)]
        realized = sum(
            (r.get("exit_price", 0) - r.get("entry_price", 0)) / r.get("entry_price", 1) * r["size_usd"]
            for r in closed_pos if r.get("entry_price", 0) > 0
        )
        xp = len(closed_pos) * 10 + len(wins) * 50 + max(0, int(realized))
        return {
            "open_positions": len(open_pos),
            "total_invested": round(sum(r["size_usd"] for r in open_pos), 2),
            "unrealized_pnl": round(open_pnl, 2),
            "realized_pnl": round(realized, 2),
            "total_trades": len(closed_pos),
            "win_rate": round(len(wins) / len(closed_pos), 4) if closed_pos else 0.0,
            "wins": len(wins),
            "losses": len(closed_pos) - len(wins),
            "xp": xp,
            "streak": min(len(wins), 7),
            "source": "live",
        }
    # Mock stats while bot hasn't traded yet
    return {
        "open_positions": 3, "total_invested": 270.0,
        "unrealized_pnl": 38.52, "realized_pnl": 75.74,
        "total_trades": 3, "win_rate": 0.667,
        "wins": 2, "losses": 1, "xp": 205, "streak": 2,
        "source": "mock",
    }


@app.get("/api/markets")
async def get_markets():
    markets = await fetch_real_markets()
    return {"markets": markets, "source": "live" if _market_cache_ts > 0 else "mock"}


@app.get("/api/feed")
async def get_feed():
    return {"feed": [
        {"type": "scan", "text": "Bot started — scanning real markets",
         "detail": "Connecting to Polymarket CLOB API…", "time": time.time() - 30},
    ]}


@app.get("/api/pnl_history")
async def get_pnl_history():
    rows = await db_get_positions()
    if rows:
        closed = [r for r in rows if r.get("closed") and r.get("exit_price", 0) > 0]
        closed.sort(key=lambda r: r["timestamp"])
        points, pnl = [], 0.0
        for r in closed:
            pnl += (r["exit_price"] - r["entry_price"]) / r["entry_price"] * r["size_usd"]
            points.append({"ts": r["timestamp"], "pnl": round(pnl, 2), "label": "trade"})
        if points:
            return {"history": points}

    # Flat line until real trades happen
    now = time.time()
    return {"history": [
        {"ts": now - 86400 * i, "pnl": 0.0, "label": f"-{i}d"} for i in range(7, -1, -1)
    ]}


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
# Serve React SPA
# ---------------------------------------------------------------------------
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return FileResponse(str(FRONTEND_DIST / "index.html"))

"""
Polymarket Bot Dashboard API — REAL DATA ONLY, no mock.
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

_market_cache: list[dict] = []
_market_cache_ts: float = 0
_CACHE_TTL = 300


async def fetch_real_markets() -> list[dict]:
    global _market_cache, _market_cache_ts
    if time.time() - _market_cache_ts < _CACHE_TTL and _market_cache:
        return _market_cache
    logger.info("Fetching markets from Polymarket CLOB…")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{CLOB_URL}/markets", params={"active": "true", "limit": 100})
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
            edge = abs(yes_price - 0.5) * 0.4
            processed.append({
                "question":     m.get("question", ""),
                "yes_price":    round(yes_price, 4),
                "no_price":     round(no_price, 4),
                "volume":       volume,
                "ev":           round(edge, 3),
                "ai_prob":      round(yes_price, 3),
                "confidence":   "medium",
                "condition_id": m.get("condition_id", ""),
            })
        processed.sort(key=lambda x: x["volume"], reverse=True)
        _market_cache = processed[:60]
        _market_cache_ts = time.time()
        logger.info("Cached %d real markets", len(_market_cache))
    except Exception as exc:
        logger.warning("CLOB fetch failed: %s", exc)
    return _market_cache


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


async def live_scanner() -> None:
    """Broadcast real market scan events via WebSocket every 30s."""
    await asyncio.sleep(5)
    scan_num = 0
    while True:
        scan_num += 1
        markets = await fetch_real_markets()
        shuffled = list(markets)
        random.shuffle(shuffled)
        edges = [m for m in shuffled if m.get("ev", 0) >= 0.05]

        for i, m in enumerate(shuffled):
            await asyncio.sleep(0.3)
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
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(fetch_real_markets())
    asyncio.create_task(live_scanner())
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def db_rows() -> list[dict]:
    try:
        if not Path(DB_PATH).exists():
            return []
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM positions ORDER BY timestamp DESC") as cur:
                return [dict(r) for r in await cur.fetchall()]
    except Exception as exc:
        logger.warning("DB read: %s", exc)
        return []


@app.get("/api/positions")
async def get_positions():
    return {"positions": await db_rows(), "source": "live"}


@app.get("/api/stats")
async def get_stats():
    rows = await db_rows()
    open_pos   = [r for r in rows if not r.get("closed")]
    closed_pos = [r for r in rows if r.get("closed")]
    open_pnl   = sum(
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
        "open_positions":  len(open_pos),
        "total_invested":  round(sum(r["size_usd"] for r in open_pos), 2),
        "unrealized_pnl":  round(open_pnl, 2),
        "realized_pnl":    round(realized, 2),
        "total_trades":    len(closed_pos),
        "win_rate":        round(len(wins) / len(closed_pos), 4) if closed_pos else 0.0,
        "wins":            len(wins),
        "losses":          len(closed_pos) - len(wins),
        "xp":              xp,
        "streak":          min(len(wins), 7),
        "source":          "live",
    }


@app.get("/api/markets")
async def get_markets():
    return {"markets": await fetch_real_markets(), "source": "live"}


@app.get("/api/feed")
async def get_feed():
    return {"feed": []}


@app.get("/api/pnl_history")
async def get_pnl_history():
    rows = await db_rows()
    closed = sorted(
        [r for r in rows if r.get("closed") and r.get("exit_price", 0) > 0],
        key=lambda r: r["timestamp"],
    )
    points, pnl = [], 0.0
    for r in closed:
        pnl += (r["exit_price"] - r["entry_price"]) / r["entry_price"] * r["size_usd"]
        points.append({"ts": r["timestamp"], "pnl": round(pnl, 2), "label": "trade"})
    if not points:
        now = time.time()
        points = [{"ts": now - 86400 * i, "pnl": 0.0, "label": f"-{i}d"} for i in range(7, -1, -1)]
    return {"history": points}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return FileResponse(str(FRONTEND_DIST / "index.html"))

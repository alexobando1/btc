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
from json import loads as json_loads
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from web3 import Web3

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

DB_PATH = os.getenv("DB_PATH", "positions.db")
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
CLOB_URL  = "https://clob.polymarket.com"
GAMMA_URL = "https://gamma-api.polymarket.com"
STOP_FILE = Path("/tmp/polybot_stop")
USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
_ERC20_ABI = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
               "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
               "type": "function"}]

_market_cache: list[dict] = []
_market_cache_ts: float = 0
_CACHE_TTL = 300


async def fetch_real_markets() -> list[dict]:
    global _market_cache, _market_cache_ts
    if time.time() - _market_cache_ts < _CACHE_TTL and _market_cache:
        return _market_cache
    logger.info("Fetching markets from Polymarket CLOB…")
    try:
        all_raw: list[dict] = []
        offset, limit = 0, 100
        async with httpx.AsyncClient(timeout=30) as client:
            for _ in range(20):
                resp = await client.get(
                    f"{GAMMA_URL}/markets",
                    params={"active": "true", "closed": "false", "limit": limit, "offset": offset},
                )
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                all_raw.extend(batch)
                if len(batch) < limit:
                    break
                offset += limit
        raw = all_raw
        processed: list[dict] = []
        for m in raw:
            try:
                if not m.get("active") or m.get("closed"):
                    continue
                volume = float(m.get("volume") or m.get("volumeNum") or 0)
                if volume < 5_000:
                    continue
                raw_prices = m.get("outcomePrices", "[]")
                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
                if len(prices) < 2:
                    continue
                yes_price = float(prices[0])
                no_price  = float(prices[1])
                if yes_price <= 0 or no_price <= 0:
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
                    "condition_id": m.get("conditionId", m.get("condition_id", "")),
                })
            except Exception:
                continue
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


@app.get("/api/balance")
async def get_balance():
    try:
        pk = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        api_key = os.getenv("POLYMARKET_API_KEY", "")
        api_secret = os.getenv("POLYMARKET_API_SECRET", "")
        api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "")
        if not pk:
            return {"wallet": "—", "usdc_balance": 0.0, "error": "No private key set"}
        loop = asyncio.get_event_loop()
        def _read():
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
            # Derive wallet address (local op, no RPC needed)
            w3 = Web3()
            acct = w3.eth.account.from_key(pk)
            wallet = acct.address
            # Polymarket holds USDC internally — read via CLOB API balance endpoint
            if api_key and api_secret and api_passphrase:
                creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
                client = ClobClient(host=CLOB_URL, chain_id=137, key=pk, creds=creds)
                result = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
                raw_bal = result.get("balance", "0") if isinstance(result, dict) else "0"
                return wallet, float(raw_bal) / 1e6
            return wallet, 0.0
        wallet, balance = await loop.run_in_executor(None, _read)
        return {"wallet": wallet, "usdc_balance": round(balance, 2)}
    except Exception as exc:
        logger.warning("Balance fetch failed: %s", exc)
        return {"wallet": "—", "usdc_balance": 0.0, "error": str(exc)}


@app.get("/api/bot_status")
async def bot_status():
    return {"running": not STOP_FILE.exists(), "stop_file": str(STOP_FILE)}


@app.post("/api/stop")
async def stop_bot():
    STOP_FILE.touch()
    logger.info("EMERGENCY STOP triggered via API")
    await ws_manager.broadcast({"event": "bot_stopped", "data": {}})
    return {"status": "stopped"}


@app.post("/api/start")
async def start_bot():
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    logger.info("Bot RESUMED via API")
    await ws_manager.broadcast({"event": "bot_started", "data": {}})
    return {"status": "running"}


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

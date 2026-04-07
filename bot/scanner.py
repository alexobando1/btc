"""
Layer 1 – Data & Market Access
Uses Polymarket Gamma API for market data (includes live prices + volume).
Uses CLOB client only for order placement.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

from bot.logger import setup_logger
from config import config

logger = setup_logger(__name__)

CLOB_HOST  = "https://clob.polymarket.com"
GAMMA_URL  = "https://gamma-api.polymarket.com"


@dataclass
class MarketToken:
    token_id: str
    outcome: str
    price: float = 0.0


@dataclass
class Market:
    condition_id: str
    question: str
    volume: float
    tokens: list[MarketToken] = field(default_factory=list)
    yes_price: float = 0.0
    no_price: float = 0.0
    spread: float = 0.0

    @property
    def mid_price(self) -> float:
        return (self.yes_price + self.no_price) / 2 if self.yes_price else 0.0


class MarketScanner:
    def __init__(self) -> None:
        creds = None
        if config.POLYMARKET_API_KEY:
            creds = ApiCreds(
                api_key=config.POLYMARKET_API_KEY,
                api_secret=config.POLYMARKET_API_SECRET,
                api_passphrase=config.POLYMARKET_API_PASSPHRASE,
            )
        self._clob = ClobClient(
            host=CLOB_HOST, chain_id=137,
            key=config.POLYMARKET_PRIVATE_KEY or None,
            creds=creds,
        )
        logger.info("MarketScanner initialised (Gamma API + CLOB)")

    async def fetch_markets(self, min_volume: float = config.MIN_MARKET_VOLUME) -> list[Market]:
        logger.info("Fetching markets from Gamma API (min volume $%.0f)…", min_volume)
        raw = await self._fetch_gamma_markets()
        logger.info("Gamma API returned %d total markets", len(raw))

        markets: list[Market] = []
        for m in raw:
            try:
                volume = float(m.get("volume") or m.get("volumeNum") or 0)
                if volume < min_volume:
                    continue
                if not m.get("active") or m.get("closed"):
                    continue

                # outcomePrices is a JSON-encoded string like '["0.42","0.58"]'
                raw_prices = m.get("outcomePrices", "[]")
                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
                if len(prices) < 2:
                    continue
                yes_price = float(prices[0])
                no_price  = float(prices[1])
                if yes_price <= 0 or no_price <= 0:
                    continue

                # clobTokenIds is a JSON-encoded string of token IDs
                raw_ids = m.get("clobTokenIds", "[]")
                token_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids

                outcomes_raw = m.get("outcomes", '["Yes","No"]')
                outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw

                tokens = []
                for i, tid in enumerate(token_ids[:2]):
                    outcome = outcomes[i] if i < len(outcomes) else ("YES" if i == 0 else "NO")
                    price   = yes_price if i == 0 else no_price
                    tokens.append(MarketToken(token_id=str(tid), outcome=outcome.upper(), price=price))

                spread = abs(yes_price + no_price - 1.0)
                markets.append(Market(
                    condition_id=m.get("conditionId", m.get("condition_id", "")),
                    question=m.get("question", ""),
                    volume=volume,
                    tokens=tokens,
                    yes_price=yes_price,
                    no_price=no_price,
                    spread=spread,
                ))
            except Exception as exc:
                logger.warning("Skipping malformed market: %s", exc)

        markets.sort(key=lambda m: m.volume, reverse=True)
        logger.info("Loaded %d qualifying markets", len(markets))
        return markets

    async def _fetch_gamma_markets(self) -> list[dict]:
        """Fetch active binary markets from Gamma API with pagination."""
        all_markets: list[dict] = []
        offset = 0
        limit  = 100
        async with httpx.AsyncClient(timeout=30) as client:
            for _ in range(20):  # max 2000 markets
                try:
                    resp = await client.get(
                        f"{GAMMA_URL}/markets",
                        params={"active": "true", "closed": "false",
                                "limit": limit, "offset": offset},
                    )
                    resp.raise_for_status()
                    batch = resp.json()
                    if not batch:
                        break
                    all_markets.extend(batch)
                    logger.info("Gamma page offset=%d: %d markets", offset, len(batch))
                    if len(batch) < limit:
                        break
                    offset += limit
                except Exception as exc:
                    logger.error("Gamma API page error (offset=%d): %s", offset, exc)
                    break
        return all_markets

    async def get_orderbook(self, token_id: str) -> Optional[dict]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, lambda: self._clob.get_order_book(token_id))
        except Exception as exc:
            logger.warning("Orderbook fetch failed %s: %s", token_id, exc)
            return None

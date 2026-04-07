"""
Layer 1 – Data & Market Access
Fetches active markets directly from Polymarket CLOB REST API via httpx.
Uses cursor-based pagination to get all markets.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

from bot.logger import setup_logger
from config import config

logger = setup_logger(__name__)

CLOB_HOST = "https://clob.polymarket.com"


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
            host=CLOB_HOST,
            chain_id=137,
            key=config.POLYMARKET_PRIVATE_KEY or None,
            creds=creds,
        )
        logger.info("MarketScanner initialised (CLOB host: %s)", CLOB_HOST)

    async def fetch_markets(self, min_volume: float = config.MIN_MARKET_VOLUME) -> list[Market]:
        """Return active binary markets above *min_volume* USD using direct REST calls."""
        logger.info("Fetching active markets (min volume $%.0f)…", min_volume)

        raw_markets = await self._fetch_all_pages()
        logger.info("Raw markets fetched from CLOB: %d", len(raw_markets))

        markets: list[Market] = []
        for raw in raw_markets:
            try:
                volume = float(raw.get("volume", 0) or 0)
                if volume < min_volume:
                    continue

                tokens = raw.get("tokens", [])
                if len(tokens) < 2:
                    continue

                market_tokens = [
                    MarketToken(
                        token_id=t["token_id"],
                        outcome=t["outcome"],
                        price=float(t.get("price", 0) or 0),
                    )
                    for t in tokens
                ]

                yes_token = next((t for t in market_tokens if t.outcome.upper() == "YES"), None)
                no_token  = next((t for t in market_tokens if t.outcome.upper() == "NO"),  None)

                if not yes_token or not no_token:
                    continue
                if yes_token.price <= 0 or no_token.price <= 0:
                    continue

                spread = abs(yes_token.price + no_token.price - 1.0)

                markets.append(Market(
                    condition_id=raw.get("condition_id", ""),
                    question=raw.get("question", ""),
                    volume=volume,
                    tokens=market_tokens,
                    yes_price=yes_token.price,
                    no_price=no_token.price,
                    spread=spread,
                ))
            except Exception as exc:
                logger.warning("Skipping malformed market: %s", exc)

        markets.sort(key=lambda m: m.volume, reverse=True)
        logger.info("Loaded %d qualifying markets", len(markets))
        return markets

    async def _fetch_all_pages(self) -> list[dict]:
        """Paginate through CLOB /markets using cursor until exhausted."""
        all_markets: list[dict] = []
        cursor = "MA=="   # base64("0") — starting cursor for Polymarket pagination
        max_pages = 10

        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(max_pages):
                try:
                    resp = await client.get(
                        f"{CLOB_HOST}/markets",
                        params={"next_cursor": cursor},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    page_markets = data.get("data", [])
                    all_markets.extend(page_markets)
                    logger.info("CLOB page %d: %d markets", page + 1, len(page_markets))

                    next_cursor = data.get("next_cursor", "")
                    # LTE== is the sentinel "end of results" cursor
                    if not next_cursor or next_cursor in ("", "LTE=", cursor):
                        break
                    cursor = next_cursor
                except Exception as exc:
                    logger.error("CLOB page fetch error (page %d): %s", page + 1, exc)
                    break

        return all_markets

    async def get_orderbook(self, token_id: str) -> Optional[dict]:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: self._clob.get_order_book(token_id)
            )
        except Exception as exc:
            logger.warning("Orderbook fetch failed for %s: %s", token_id, exc)
            return None

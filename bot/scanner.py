"""
Layer 1 – Data & Market Access
Fetches active markets from the Polymarket CLOB API via py-clob-client.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

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
    # Derived after fetch
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
        self._client = ClobClient(
            host=CLOB_HOST,
            chain_id=137,
            key=config.POLYMARKET_PRIVATE_KEY or None,
            creds=creds,
        )
        logger.info("MarketScanner initialised (CLOB host: %s)", CLOB_HOST)

    async def fetch_markets(self, min_volume: float = config.MIN_MARKET_VOLUME) -> list[Market]:
        """Return active binary markets above *min_volume* USD."""
        logger.info("Fetching active markets (min volume $%.0f)…", min_volume)

        loop = asyncio.get_event_loop()
        raw_markets = await loop.run_in_executor(None, self._fetch_sync)

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

                yes_token = next(
                    (t for t in market_tokens if t.outcome.upper() == "YES"), None
                )
                no_token = next(
                    (t for t in market_tokens if t.outcome.upper() == "NO"), None
                )

                if not yes_token or not no_token:
                    continue

                spread = abs(yes_token.price + no_token.price - 1.0)

                m = Market(
                    condition_id=raw.get("condition_id", ""),
                    question=raw.get("question", ""),
                    volume=volume,
                    tokens=market_tokens,
                    yes_price=yes_token.price,
                    no_price=no_token.price,
                    spread=spread,
                )
                markets.append(m)
            except Exception as exc:
                logger.warning("Skipping malformed market entry: %s", exc)

        markets.sort(key=lambda m: m.volume, reverse=True)
        logger.info("Loaded %d qualifying markets", len(markets))
        return markets

    def _fetch_sync(self) -> list[dict]:
        """Synchronous CLOB call wrapped for executor."""
        try:
            resp = self._client.get_markets()
            # py-clob-client returns a dict with a 'data' key
            if isinstance(resp, dict):
                return resp.get("data", [])
            return list(resp) if resp else []
        except Exception as exc:
            logger.error("CLOB fetch_markets failed: %s", exc)
            return []

    async def get_orderbook(self, token_id: str) -> Optional[dict]:
        """Fetch full orderbook for a single token."""
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None, lambda: self._client.get_order_book(token_id)
            )
        except Exception as exc:
            logger.warning("Failed to fetch orderbook for %s: %s", token_id, exc)
            return None

"""
Layer 4 – Execution
Places GTC (Good Till Cancelled) orders on Polymarket via py-clob-client.
Checks on-chain USDC balance before every trade.
Enforces max slippage.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from web3 import Web3

from bot.logger import setup_logger
from bot.math_engine import TradeDecision
from bot.position_tracker import Position, PositionTracker
from bot.scanner import Market
from config import config

logger = setup_logger(__name__)


class Executor:
    def __init__(self, tracker: PositionTracker) -> None:
        self._tracker = tracker
        # Web3 only needed for address derivation (local op, no RPC call)
        self._w3 = Web3()

        # Polymarket uses proxy wallets: signature_type=1 (POLY_PROXY)
        # funder = the proxy wallet address shown on polymarket.com profile
        POLY_PROXY = 1
        proxy = config.POLYMARKET_PROXY_WALLET or None

        # Start with a bare client (no creds) — we'll derive them below
        self._clob = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=config.POLYMARKET_PRIVATE_KEY,
            signature_type=POLY_PROXY,
            funder=proxy,
        )
        self._wallet = self._derive_address()

        # Auto-derive CLOB API credentials from private key
        creds = self._derive_or_create_creds()
        if creds:
            self._clob = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=137,
                key=config.POLYMARKET_PRIVATE_KEY,
                creds=creds,
                signature_type=POLY_PROXY,
                funder=proxy,
            )
        logger.info("Proxy wallet (funder): %s", proxy or "not set (defaulting to EOA)")

        logger.info("Executor initialised (wallet: %s)", self._wallet)

    def _derive_or_create_creds(self) -> ApiCreds | None:
        """Derive CLOB API credentials from the private key.

        Calls the Polymarket CLOB API to create or retrieve existing
        credentials tied to the wallet. No manual API key management needed.
        """
        try:
            creds = self._clob.create_or_derive_api_creds()
            logger.info("CLOB API credentials derived successfully (api_key: %s…)", creds.api_key[:12])
            return creds
        except Exception as exc:
            logger.error("Failed to derive CLOB API credentials: %s", exc)
            # Fall back to env var creds if derivation fails
            if config.POLYMARKET_API_KEY:
                logger.info("Falling back to env var CLOB credentials")
                return ApiCreds(
                    api_key=config.POLYMARKET_API_KEY,
                    api_secret=config.POLYMARKET_API_SECRET,
                    api_passphrase=config.POLYMARKET_API_PASSPHRASE,
                )
            return None

    def _derive_address(self) -> str:
        try:
            account = self._w3.eth.account.from_key(config.POLYMARKET_PRIVATE_KEY)
            return account.address
        except Exception:
            return "0x0000000000000000000000000000000000000000"

    async def get_usdc_balance(self) -> float:
        """Return Polymarket USDC trading balance via CLOB API.

        Funds deposited into Polymarket are held in their proxy contracts,
        not as raw USDC in the EOA — so on-chain balance would always be 0.
        The CLOB balance-allowance endpoint returns the actual tradeable amount.
        """
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._clob.get_balance_allowance(
                    BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
                ),
            )
            logger.info("Balance API raw response: %s", result)
            raw_bal = result.get("balance", "0") if isinstance(result, dict) else "0"
            balance = float(raw_bal) / 1e6
            logger.info("Polymarket USDC balance: $%.2f (raw: %s)", balance, raw_bal)
            return balance
        except Exception as exc:
            logger.error("Balance check failed: %s", exc)
            return 0.0

    async def execute_trade(
        self,
        market: Market,
        decision: TradeDecision,
    ) -> Optional[Position]:
        """
        Full pre-trade checklist then place a GTC limit order.
        Returns the opened Position, or None on failure.
        """
        # 1. Skip if already in this market
        if await self._tracker.position_exists(market.condition_id):
            logger.info("Already have open position in '%s' – skipping", market.question[:50])
            return None

        # 2. Slippage guard – spread must be within MAX_SLIPPAGE
        if market.spread > config.MAX_SLIPPAGE:
            logger.info(
                "SKIPPED (spread %.2f%% > %.2f%%): %s",
                market.spread * 100,
                config.MAX_SLIPPAGE * 100,
                market.question[:60],
            )
            return None

        # 3. Balance pre-check
        balance = await self.get_usdc_balance()
        if balance < decision.position_size_usd:
            logger.warning(
                "Insufficient balance $%.2f for trade $%.2f on '%s'",
                balance,
                decision.position_size_usd,
                market.question[:50],
            )
            return None

        # 4. Find the correct token
        token = next(
            (t for t in market.tokens if t.outcome.upper() == decision.side),
            None,
        )
        if not token:
            logger.error("Token for side %s not found in market %s", decision.side, market.condition_id)
            return None

        # 5. Place GTC order
        # py_clob_client expects "BUY"/"SELL", not "YES"/"NO".
        # We always BUY the correct outcome token (YES token or NO token).
        order_id = await self._place_gtc_order(
            token_id=token.token_id,
            price=decision.market_price,
            size_usd=decision.position_size_usd,
        )
        if not order_id:
            return None

        # 6. Record in DB
        pos = Position(
            id=None,
            condition_id=market.condition_id,
            question=market.question,
            side=decision.side,
            token_id=token.token_id,
            entry_price=decision.market_price,
            current_price=decision.market_price,
            size_usd=decision.position_size_usd,
            order_id=order_id,
            timestamp=time.time(),
        )
        pos.id = await self._tracker.open_position(pos)
        return pos

    async def _place_gtc_order(
        self,
        token_id: str,
        price: float,
        size_usd: float,
    ) -> Optional[str]:
        loop = asyncio.get_running_loop()
        try:
            # size in shares = USD / price
            size_shares = size_usd / price if price > 0 else 0

            order_args = OrderArgs(
                token_id=token_id,
                price=round(price, 4),
                size=round(size_shares, 2),
                side=BUY,
            )
            resp = await loop.run_in_executor(
                None,
                lambda: self._clob.create_and_post_order(order_args),
            )
            order_id = resp.get("orderID", "") if isinstance(resp, dict) else str(resp)
            logger.info(
                "GTC order placed: BUY %s @ %.4f, size $%.2f | order_id=%s",
                token_id[:12], price, size_usd, order_id,
            )
            return order_id
        except Exception as exc:
            logger.error("Order placement failed: %s", exc)
            return None

"""
Polymarket Automated Trading Bot
=================================
Pipeline: Data → AI Brain → Math → Execution → Monitoring

Usage:
    python main.py

Environment variables are loaded from .env (see .env.example).
"""
from __future__ import annotations

import asyncio
import time

from bot.analyzer import MarketAnalyzer
from bot.executor import Executor
from bot.logger import setup_logger
from bot.math_engine import evaluate_trade
from bot.monitor import TelegramMonitor
from bot.position_tracker import PositionTracker
from bot.scanner import MarketScanner
from config import config

logger = setup_logger("main")


async def run_scan_cycle(
    scanner: MarketScanner,
    analyzer: MarketAnalyzer,
    executor: Executor,
    tracker: PositionTracker,
    monitor: TelegramMonitor,
) -> None:
    """Single scan → analyse → trade cycle."""
    logger.info("=== SCAN CYCLE STARTED ===")
    cycle_start = time.monotonic()

    # --- Layer 1: Fetch markets ---
    markets = await scanner.fetch_markets()
    if not markets:
        logger.warning("No markets returned – skipping cycle")
        return

    logger.info("Connecting to Polymarket CLOB API... Connected ✓")
    logger.info("Fetching active markets... %d found.", len(markets))
    for i, m in enumerate(markets[:5], 1):
        vol_str = f"${m.volume/1e6:.1f}M" if m.volume >= 1e6 else f"${m.volume/1e3:.0f}K"
        logger.info(
            "#%d %r  YES: $%.2f | NO: $%.2f | Volume: %s",
            i, m.question, m.yes_price, m.no_price, vol_str,
        )
    if len(markets) > 5:
        logger.info("... %d more markets loaded.", len(markets) - 5)

    # --- Layer 4: Portfolio pre-check for position updates ---
    open_positions = await tracker.get_open_positions()
    balance = await executor.get_usdc_balance()
    logger.info("Bankroll (on-chain USDC): $%.2f | Open positions: %d", balance, len(open_positions))

    # Update current prices for open positions
    market_price_map = {m.condition_id: m for m in markets}
    for pos in open_positions:
        if pos.condition_id in market_price_map:
            mkt = market_price_map[pos.condition_id]
            current = mkt.yes_price if pos.side == "YES" else mkt.no_price
            await tracker.update_price(pos.id, current)

    # Refresh positions after price update
    open_positions = await tracker.get_open_positions()
    await monitor.alert_portfolio(open_positions)

    # --- Layers 2 + 3: Analyse and decide ---
    edges_found = 0
    trades_placed = 0

    # Analyse concurrently (up to 10 at a time)
    semaphore = asyncio.Semaphore(10)

    async def analyse_one(market):
        nonlocal edges_found, trades_placed
        async with semaphore:
            try:
                analysis = await analyzer.analyse(
                    question=market.question,
                    yes_price=market.yes_price,
                    no_price=market.no_price,
                    volume=market.volume,
                )
                if not analysis:
                    return

                decision = evaluate_trade(
                    ai_probability=analysis.probability,
                    yes_price=market.yes_price,
                    no_price=market.no_price,
                    bankroll_usd=balance,
                    ev_threshold=config.EV_THRESHOLD,
                    kelly_fraction_multiplier=config.KELLY_FRACTION,
                    max_position_usd=config.MAX_POSITION_USD,
                )

                if not decision.should_trade:
                    if market.spread > config.MAX_SLIPPAGE:
                        await monitor.alert_skipped(market.question, "Low liquidity detected")
                    return

                edges_found += 1
                logger.info(
                    "EDGE FOUND: %s | %s | EV=%.2f%% | Kelly=%.2f%% | $%.2f",
                    market.question[:50],
                    decision.side,
                    decision.ev * 100,
                    decision.kelly_fraction * 100,
                    decision.position_size_usd,
                )

                # --- Layer 4: Execute ---
                position = await executor.execute_trade(market, decision)
                if position:
                    trades_placed += 1
                    await monitor.alert_trade_executed(
                        position=position,
                        ev=decision.ev,
                        kelly=decision.kelly_fraction,
                    )

            except Exception as exc:
                logger.error("Error processing market '%s': %s", market.question[:50], exc)
                await monitor.alert_error(f"market analysis: {market.question[:40]}", exc)

    await asyncio.gather(*[analyse_one(m) for m in markets])

    elapsed = time.monotonic() - cycle_start
    next_scan_min = config.SCAN_INTERVAL_SECONDS // 60
    logger.info(
        "=== SCAN COMPLETE — %.0fs | Markets: %d | Edges: %d | Trades: %d | Next in %dmin ===",
        elapsed, len(markets), edges_found, trades_placed, next_scan_min,
    )
    await monitor.alert_scan_complete(
        markets_scanned=len(markets),
        edges_found=edges_found,
        trades_placed=trades_placed,
        next_scan_minutes=next_scan_min,
    )


async def main() -> None:
    logger.info("Polymarket Trading Bot starting…")
    config.validate()

    tracker = PositionTracker()
    await tracker.init()

    scanner = MarketScanner()
    analyzer = MarketAnalyzer()
    monitor = TelegramMonitor(tracker)
    executor = Executor(tracker)

    # Start Telegram polling as a background task
    polling_task = asyncio.create_task(monitor.start_polling())

    try:
        while True:
            try:
                await run_scan_cycle(scanner, analyzer, executor, tracker, monitor)
            except Exception as exc:
                logger.error("Scan cycle failed: %s", exc, exc_info=True)
                await monitor.alert_error("scan cycle", exc)

            logger.info("Sleeping %ds until next scan…", config.SCAN_INTERVAL_SECONDS)
            await asyncio.sleep(config.SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        polling_task.cancel()
        await monitor.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

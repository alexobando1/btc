"""
Layer 5 – Monitoring & Alerts
Telegram bot using aiogram v3 for real-time notifications and
an inline dashboard to view/close positions.
"""
from __future__ import annotations

import asyncio
import traceback
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.logger import setup_logger
from bot.position_tracker import Position, PositionTracker
from config import config

logger = setup_logger(__name__)


class TelegramMonitor:
    def __init__(self, tracker: PositionTracker) -> None:
        self._tracker = tracker
        self._bot: Optional[Bot] = None
        self._dp: Optional[Dispatcher] = None
        self._enabled = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)

        if self._enabled:
            try:
                self._bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
                self._dp = Dispatcher()
                self._register_handlers()
                logger.info("TelegramMonitor enabled (chat_id: %s)", config.TELEGRAM_CHAT_ID)
            except Exception as exc:
                logger.warning("Telegram init failed (%s) – alerts disabled", exc)
                self._enabled = False
                self._bot = None
                self._dp = None
        else:
            logger.warning("Telegram not configured – alerts disabled")

    def _register_handlers(self) -> None:
        dp = self._dp

        @dp.message(Command("positions"))
        async def cmd_positions(message: types.Message) -> None:
            await self._send_positions(message.chat.id)

        @dp.message(Command("pnl"))
        async def cmd_pnl(message: types.Message) -> None:
            positions = await self._tracker.get_open_positions()
            total_invested = sum(p.size_usd for p in positions)
            total_pnl = sum(p.unrealized_pnl for p in positions)
            pct = (total_pnl / total_invested * 100) if total_invested else 0
            sign = "+" if total_pnl >= 0 else ""
            text = (
                f"📊 *Portfolio P&L*\n"
                f"Open positions: {len(positions)}\n"
                f"Total invested: ${total_invested:.2f}\n"
                f"Unrealized P&L: {sign}${total_pnl:.2f} ({sign}{pct:.1f}%)"
            )
            await message.answer(text, parse_mode="Markdown")

        @dp.message(Command("status"))
        async def cmd_status(message: types.Message) -> None:
            await message.answer("✅ Bot is running")

        @dp.callback_query()
        async def handle_callback(callback: types.CallbackQuery) -> None:
            data = callback.data or ""
            if data.startswith("close:"):
                pos_id = int(data.split(":")[1])
                await self._tracker.close_position(pos_id, exit_price=0.0)
                await callback.answer("Position marked for closure")
                await callback.message.edit_text(
                    f"🔴 Position #{pos_id} marked closed."
                )

    async def _send_positions(self, chat_id: int | str) -> None:
        positions = await self._tracker.get_open_positions()
        if not positions:
            await self._bot.send_message(chat_id, "No open positions.")
            return

        for p in positions:
            sign = "+" if p.unrealized_pnl >= 0 else ""
            text = (
                f"📌 *#{p.id}* {p.question[:50]}\n"
                f"Side: {p.side} | Entry: ${p.entry_price:.4f} | Now: ${p.current_price:.4f}\n"
                f"Size: ${p.size_usd:.2f} | P&L: {sign}${p.unrealized_pnl:.2f} ({sign}{p.unrealized_pnl_pct:.1%})"
            )
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Close position", callback_data=f"close:{p.id}")]
                ]
            )
            await self._bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=keyboard)

    # ------------------------------------------------------------------ #
    # Public alert methods called by the main loop                        #
    # ------------------------------------------------------------------ #

    async def alert_trade_executed(self, position: Position, ev: float, kelly: float) -> None:
        if not self._enabled:
            return
        sign = "+" if ev >= 0 else ""
        text = (
            f"🟢 *TRADE EXECUTED*\n"
            f"Market: {position.question[:60]}\n"
            f"Side: BUY {position.side}\n"
            f"Price: ${position.entry_price:.4f}\n"
            f"Size: ${position.size_usd:.2f}\n"
            f"Kelly: {kelly:.1%} (Quarter)\n"
            f"EV: {sign}${ev:.4f}/share"
        )
        await self._send(text)

    async def alert_skipped(self, question: str, reason: str) -> None:
        if not self._enabled:
            return
        text = (
            f"⚠️ *ALERT: {reason}*\n"
            f"Market: {question[:60]}\n"
            f"Action: SKIPPED"
        )
        await self._send(text)

    async def alert_scan_complete(
        self,
        markets_scanned: int,
        edges_found: int,
        trades_placed: int,
        next_scan_minutes: int,
    ) -> None:
        if not self._enabled:
            return
        skipped = markets_scanned - edges_found
        text = (
            f"🔄 *SCAN COMPLETE*\n"
            f"Markets: {markets_scanned} | Edges: {edges_found} | Skipped: {skipped}\n"
            f"Trades placed: {trades_placed}\n"
            f"Next scan in {next_scan_minutes} min…"
        )
        await self._send(text)

    async def alert_portfolio(self, positions: list[Position]) -> None:
        if not self._enabled or not positions:
            return
        total_invested = sum(p.size_usd for p in positions)
        total_pnl = sum(p.unrealized_pnl for p in positions)
        pct = (total_pnl / total_invested * 100) if total_invested else 0
        sign = "+" if total_pnl >= 0 else ""
        text = (
            f"📊 *PORTFOLIO UPDATE*\n"
            f"Open positions: {len(positions)}\n"
            f"Total invested: ${total_invested:.2f}\n"
            f"Unrealized P&L: {sign}${total_pnl:.2f} ({sign}{pct:.1f}%)"
        )
        await self._send(text)

    async def alert_error(self, context: str, error: Exception) -> None:
        if not self._enabled:
            return
        tb = traceback.format_exc()[-500:]
        text = f"🚨 *ERROR* in {context}\n`{error}`\n```{tb}```"
        await self._send(text)

    async def _send(self, text: str) -> None:
        try:
            await self._bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)

    async def start_polling(self) -> None:
        """Start the Telegram command listener (runs as background task)."""
        if not self._enabled:
            return
        try:
            await self._dp.start_polling(self._bot)
        except Exception as exc:
            logger.error("Telegram polling error: %s", exc)

    async def close(self) -> None:
        if self._bot:
            await self._bot.session.close()

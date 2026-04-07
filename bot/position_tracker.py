"""
Layer 4 – Position Tracker
SQLite-backed store for open and closed positions.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import aiosqlite

from bot.logger import setup_logger
from config import config

logger = setup_logger(__name__)


@dataclass
class Position:
    id: Optional[int]
    condition_id: str
    question: str
    side: str                 # "YES" or "NO"
    token_id: str
    entry_price: float
    current_price: float
    size_usd: float
    order_id: str
    timestamp: float
    closed: bool = False
    exit_price: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        shares = self.size_usd / self.entry_price
        return shares * (self.current_price - self.entry_price)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS positions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id  TEXT NOT NULL,
    question      TEXT NOT NULL,
    side          TEXT NOT NULL,
    token_id      TEXT NOT NULL,
    entry_price   REAL NOT NULL,
    current_price REAL NOT NULL,
    size_usd      REAL NOT NULL,
    order_id      TEXT NOT NULL,
    timestamp     REAL NOT NULL,
    closed        INTEGER NOT NULL DEFAULT 0,
    exit_price    REAL NOT NULL DEFAULT 0
);
"""


class PositionTracker:
    def __init__(self) -> None:
        self._db_path = config.DB_PATH

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(CREATE_TABLE)
            await db.commit()
        logger.info("PositionTracker initialised (db: %s)", self._db_path)

    async def open_position(self, pos: Position) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """INSERT INTO positions
                   (condition_id, question, side, token_id, entry_price,
                    current_price, size_usd, order_id, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pos.condition_id, pos.question, pos.side, pos.token_id,
                    pos.entry_price, pos.current_price, pos.size_usd,
                    pos.order_id, pos.timestamp,
                ),
            )
            await db.commit()
            row_id = cursor.lastrowid
            logger.info("Opened position #%d: %s %s @ %.2f", row_id, pos.side, pos.question[:40], pos.entry_price)
            return row_id

    async def update_price(self, position_id: int, current_price: float) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE positions SET current_price = ? WHERE id = ?",
                (current_price, position_id),
            )
            await db.commit()

    async def close_position(self, position_id: int, exit_price: float) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE positions SET closed = 1, exit_price = ? WHERE id = ?",
                (exit_price, position_id),
            )
            await db.commit()
        logger.info("Closed position #%d at %.4f", position_id, exit_price)

    async def get_open_positions(self) -> list[Position]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM positions WHERE closed = 0 ORDER BY timestamp DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_position(r) for r in rows]

    async def get_all_positions(self) -> list[Position]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM positions ORDER BY timestamp DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_position(r) for r in rows]

    async def position_exists(self, condition_id: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT 1 FROM positions WHERE condition_id = ? AND closed = 0",
                (condition_id,),
            ) as cursor:
                return await cursor.fetchone() is not None


def _row_to_position(row) -> Position:
    return Position(
        id=row["id"],
        condition_id=row["condition_id"],
        question=row["question"],
        side=row["side"],
        token_id=row["token_id"],
        entry_price=row["entry_price"],
        current_price=row["current_price"],
        size_usd=row["size_usd"],
        order_id=row["order_id"],
        timestamp=row["timestamp"],
        closed=bool(row["closed"]),
        exit_price=row["exit_price"],
    )

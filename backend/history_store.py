# backend/history_store.py
"""SQLite storage for stock historical data."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class HistoryStore:
    """SQLite-based storage for stock OHLCV history."""

    def __init__(self, db_path: str = "data/stock_history.db"):
        """
        Initialize history store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_prices (
                    symbol      TEXT NOT NULL,
                    date        TEXT NOT NULL,
                    open        REAL,
                    high        REAL,
                    low         REAL,
                    close       REAL,
                    volume      INTEGER,
                    PRIMARY KEY (symbol, date)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_status (
                    symbol          TEXT PRIMARY KEY,
                    last_sync       TEXT NOT NULL,
                    months_loaded   INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_date
                ON daily_prices(symbol, date DESC)
            """)

            conn.commit()

    def count_days(self, symbol: str) -> int:
        """Count number of trading days stored for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE symbol = ?",
                (symbol,)
            )
            return cursor.fetchone()[0]

    def get_last_date(self, symbol: str) -> Optional[str]:
        """Get the most recent date stored for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT MAX(date) FROM daily_prices WHERE symbol = ?",
                (symbol,)
            )
            result = cursor.fetchone()[0]
            return result

    def get_sync_status(self, symbol: str) -> Optional[dict]:
        """Get sync status for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT last_sync, months_loaded FROM sync_status WHERE symbol = ?",
                (symbol,)
            )
            row = cursor.fetchone()
            if row:
                return {"last_sync": row[0], "months_loaded": row[1]}
            return None

    def update_sync_status(self, symbol: str, months_loaded: int):
        """Update sync status for a symbol."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sync_status (symbol, last_sync, months_loaded)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    last_sync = excluded.last_sync,
                    months_loaded = excluded.months_loaded
            """, (symbol, now, months_loaded))
            conn.commit()

    def upsert(
        self,
        symbol: str,
        date: str,
        open: Optional[float],
        high: Optional[float],
        low: Optional[float],
        close: Optional[float],
        volume: Optional[int]
    ):
        """Insert or update a single day's data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO daily_prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
            """, (symbol, date, open, high, low, close, volume))
            conn.commit()

    def bulk_insert(self, symbol: str, rows: list[dict]):
        """
        Bulk insert multiple days of data.

        Args:
            symbol: Stock symbol
            rows: List of dicts with keys: date, open, high, low, close, volume
        """
        if not rows:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO daily_prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
            """, [
                (symbol, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
                for r in rows
            ])
            conn.commit()

        logger.debug(f"Inserted {len(rows)} rows for {symbol}")

    def load_dataframe(self, symbol: str, min_days: int = 60) -> Optional[pd.DataFrame]:
        """
        Load historical data as DataFrame.

        Args:
            symbol: Stock symbol
            min_days: Minimum days to load (for MA calculation)

        Returns:
            DataFrame with columns: Date, Open, High, Low, Close, Volume
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT date as Date, open as Open, high as High,
                       low as Low, close as Close, volume as Volume
                FROM daily_prices
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT ?
            """, conn, params=(symbol, min_days + 30))  # Extra buffer

        if df.empty:
            return None

        # Convert date string to datetime
        df["Date"] = pd.to_datetime(df["Date"])

        # Sort ascending for MA calculation
        df = df.sort_values("Date").reset_index(drop=True)

        return df

    def delete_symbol(self, symbol: str):
        """Delete all data for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM daily_prices WHERE symbol = ?", (symbol,))
            conn.execute("DELETE FROM sync_status WHERE symbol = ?", (symbol,))
            conn.commit()

    def get_all_symbols(self) -> list[str]:
        """Get list of all symbols with stored data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT symbol FROM daily_prices ORDER BY symbol"
            )
            return [row[0] for row in cursor.fetchall()]

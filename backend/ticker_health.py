# backend/ticker_health.py
"""Ticker health management with SQLite persistence."""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from backend.config import MARKET_OPEN, MARKET_CLOSE

logger = logging.getLogger(__name__)

# Quarantine settings
FAILURE_THRESHOLD = 2  # Quarantine after this many consecutive failures
RETRY_INTERVAL_DAYS = 7  # Retry quarantined tickers after this many days

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "ticker_health.db"

# Failure reason classification
FAILURE_REASONS = {
    "no_data": "No data returned from yfinance",
    "json_parse": "Invalid JSON response",
    "timeout": "Request timeout",
    "delisted": "Symbol may be delisted",
    "unknown": "Unknown error",
}


def classify_failure(error_msg: str) -> str:
    """Classify error message into a failure reason."""
    error_lower = error_msg.lower()
    if "no data returned" in error_lower or "no price data" in error_lower:
        return "no_data"
    if "expecting value" in error_lower:
        return "json_parse"
    if "delisted" in error_lower:
        return "delisted"
    if "timeout" in error_lower:
        return "timeout"
    return "unknown"


class TickerHealth:
    """Manages ticker health status with SQLite persistence."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the ticker health manager."""
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticker_status (
                    symbol TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'active',
                    consecutive_failures INTEGER DEFAULT 0,
                    last_failure_at TIMESTAMP,
                    last_success_at TIMESTAMP,
                    quarantined_at TIMESTAMP,
                    next_retry_at TIMESTAMP,
                    failure_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failure_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    error_message TEXT,
                    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def record_failure(self, symbol: str, reason: str) -> None:
        """
        Record a fetch failure for a symbol.

        Quarantines the symbol after FAILURE_THRESHOLD consecutive failures.
        """
        failure_reason = classify_failure(reason)
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            # Log the failure
            conn.execute(
                "INSERT INTO failure_log (symbol, error_message, occurred_at) VALUES (?, ?, ?)",
                (symbol, reason, now)
            )

            # Get current status
            row = conn.execute(
                "SELECT consecutive_failures, status FROM ticker_status WHERE symbol = ?",
                (symbol,)
            ).fetchone()

            if row is None:
                # New symbol
                consecutive_failures = 1
                conn.execute(
                    """INSERT INTO ticker_status
                       (symbol, status, consecutive_failures, last_failure_at, failure_reason, created_at)
                       VALUES (?, 'active', ?, ?, ?, ?)""",
                    (symbol, consecutive_failures, now, failure_reason, now)
                )
            else:
                consecutive_failures = row[0] + 1
                current_status = row[1]

                if consecutive_failures >= FAILURE_THRESHOLD and current_status == 'active':
                    # Quarantine the symbol
                    next_retry = now + timedelta(days=RETRY_INTERVAL_DAYS)
                    conn.execute(
                        """UPDATE ticker_status SET
                           status = 'quarantined',
                           consecutive_failures = ?,
                           last_failure_at = ?,
                           quarantined_at = ?,
                           next_retry_at = ?,
                           failure_reason = ?
                           WHERE symbol = ?""",
                        (consecutive_failures, now, now, next_retry, failure_reason, symbol)
                    )
                    logger.warning(
                        f"{symbol}: Quarantined after {consecutive_failures} failures - {failure_reason}. "
                        f"Next retry: {next_retry.strftime('%Y-%m-%d')}"
                    )
                else:
                    # Update failure count
                    conn.execute(
                        """UPDATE ticker_status SET
                           consecutive_failures = ?,
                           last_failure_at = ?,
                           failure_reason = ?
                           WHERE symbol = ?""",
                        (consecutive_failures, now, failure_reason, symbol)
                    )
                    if current_status == 'active':
                        logger.info(
                            f"{symbol}: Fetch failed ({consecutive_failures}/{FAILURE_THRESHOLD}) - {failure_reason}"
                        )

            conn.commit()

    def record_success(self, symbol: str) -> None:
        """Record a successful fetch for a symbol."""
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status FROM ticker_status WHERE symbol = ?",
                (symbol,)
            ).fetchone()

            if row is None:
                # New symbol, just record it
                conn.execute(
                    """INSERT INTO ticker_status
                       (symbol, status, consecutive_failures, last_success_at, created_at)
                       VALUES (?, 'active', 0, ?, ?)""",
                    (symbol, now, now)
                )
            else:
                was_quarantined = row[0] == 'quarantined'
                conn.execute(
                    """UPDATE ticker_status SET
                       status = 'active',
                       consecutive_failures = 0,
                       last_success_at = ?,
                       quarantined_at = NULL,
                       next_retry_at = NULL
                       WHERE symbol = ?""",
                    (now, symbol)
                )
                if was_quarantined:
                    logger.info(f"{symbol}: Recovered from quarantine")

            conn.commit()

    def is_quarantined(self, symbol: str) -> bool:
        """Check if a symbol is currently quarantined."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status FROM ticker_status WHERE symbol = ?",
                (symbol,)
            ).fetchone()
            return row is not None and row[0] == 'quarantined'

    def get_active_symbols(self, symbols: list[str]) -> list[str]:
        """Filter out quarantined symbols from a list."""
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ','.join('?' * len(symbols))
            rows = conn.execute(
                f"SELECT symbol FROM ticker_status WHERE symbol IN ({placeholders}) AND status = 'quarantined'",
                symbols
            ).fetchall()
            quarantined = {row[0] for row in rows}

        active = [s for s in symbols if s not in quarantined]
        if quarantined:
            logger.debug(f"Filtered out {len(quarantined)} quarantined symbols")
        return active

    def get_retry_candidates(self) -> list[str]:
        """
        Get quarantined symbols that are ready for retry.

        Only returns candidates during market hours.
        """
        now = datetime.now()
        current_time = now.time()

        # Only retry during market hours
        if not (MARKET_OPEN <= current_time <= MARKET_CLOSE):
            return []

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT symbol FROM ticker_status
                   WHERE status = 'quarantined' AND next_retry_at <= ?""",
                (now,)
            ).fetchall()

        candidates = [row[0] for row in rows]
        if candidates:
            logger.info(f"Retrying {len(candidates)} quarantined symbols (weekly market-hours retry)")
        return candidates

    def update_retry_schedule(self, symbol: str) -> None:
        """Update the next retry date for a quarantined symbol after a failed retry."""
        now = datetime.now()
        next_retry = now + timedelta(days=RETRY_INTERVAL_DAYS)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE ticker_status SET next_retry_at = ? WHERE symbol = ?",
                (next_retry, symbol)
            )
            conn.commit()

        logger.info(f"{symbol}: Retry failed, remains quarantined. Next retry: {next_retry.strftime('%Y-%m-%d')}")

    def get_status_summary(self) -> dict:
        """Return summary of ticker health status."""
        with sqlite3.connect(self.db_path) as conn:
            active = conn.execute(
                "SELECT COUNT(*) FROM ticker_status WHERE status = 'active'"
            ).fetchone()[0]
            quarantined = conn.execute(
                "SELECT COUNT(*) FROM ticker_status WHERE status = 'quarantined'"
            ).fetchone()[0]
            total_failures = conn.execute(
                "SELECT COUNT(*) FROM failure_log"
            ).fetchone()[0]

        return {
            "active": active,
            "quarantined": quarantined,
            "total_failures": total_failures,
        }

    def reset_all_quarantine(self) -> int:
        """
        Reset all quarantined symbols to active status.

        Use this when a systemic failure (API outage, network issue)
        caused all tickers to be incorrectly quarantined.

        Returns:
            Number of symbols reset
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE ticker_status SET
                   status = 'active',
                   consecutive_failures = 0,
                   quarantined_at = NULL,
                   next_retry_at = NULL
                   WHERE status = 'quarantined'"""
            )
            count = cursor.rowcount
            conn.commit()

        if count > 0:
            logger.info(f"Reset {count} quarantined symbols to active")
        return count

    def should_quarantine(self, symbol: str, total_symbols: int, failed_count: int) -> bool:
        """
        Determine if a symbol should be quarantined.

        Prevents quarantine during systemic failures (>50% tickers failing).

        Args:
            symbol: The symbol being evaluated
            total_symbols: Total number of symbols being screened
            failed_count: Number of symbols that failed in this screening cycle

        Returns:
            True if quarantine is appropriate, False if likely systemic issue
        """
        if total_symbols == 0:
            return True

        failure_rate = failed_count / total_symbols
        if failure_rate > 0.5:
            logger.warning(
                f"Systemic failure detected ({failed_count}/{total_symbols} = {failure_rate:.0%}). "
                f"Skipping quarantine for {symbol}."
            )
            return False
        return True

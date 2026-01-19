# backend/twse_data_engine.py
"""Data engine using TWSE API instead of Yahoo Finance."""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from backend.config import MA_PERIODS
from backend.history_store import HistoryStore
from backend.rate_limiter import RateLimiter
from backend.ticker_health import TickerHealth

logger = logging.getLogger(__name__)

# TWSE API endpoints
TWSE_REALTIME_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
TWSE_HISTORY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"

# Request settings
REQUEST_TIMEOUT = 10
RETRY_COUNT = 2
RETRY_DELAY = 5


class TWSEDataEngine:
    """
    Data engine using TWSE official API.

    Replaces the yfinance-based DataEngine with same interface.
    """

    def __init__(self, db_path: str = "data/stock_history.db"):
        """Initialize the TWSE data engine."""
        self.store = HistoryStore(db_path)
        self.rate_limiter = RateLimiter(max_requests=3, period=5.0)
        self._health = TickerHealth()
        self._cache: dict[str, pd.DataFrame] = {}
        self._realtime_cache: dict[str, dict] = {}

    def _strip_suffix(self, symbol: str) -> str:
        """Remove .TW or .TWO suffix from symbol."""
        return re.sub(r"\.(TW|TWO)$", "", symbol, flags=re.IGNORECASE)

    def _parse_roc_date(self, roc_date: str) -> str:
        """
        Convert ROC date (民國) to ISO date.

        Args:
            roc_date: Date in format "114/01/15" (ROC year)

        Returns:
            Date in format "2025-01-15"
        """
        parts = roc_date.split("/")
        if len(parts) != 3:
            raise ValueError(f"Invalid ROC date format: {roc_date}")

        roc_year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])

        # ROC year + 1911 = Gregorian year
        year = roc_year + 1911

        return f"{year:04d}-{month:02d}-{day:02d}"

    def _parse_number(self, value: str) -> Optional[float]:
        """Parse number string with commas."""
        if not value or value == "--" or value == "-":
            return None
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None

    def _parse_int(self, value: str) -> Optional[int]:
        """Parse integer string with commas."""
        if not value or value == "--" or value == "-":
            return None
        try:
            return int(value.replace(",", ""))
        except ValueError:
            return None

    def _fetch_history_month(self, symbol: str, year: int, month: int) -> list[dict]:
        """
        Fetch one month of historical data from TWSE.

        Args:
            symbol: Stock symbol without suffix (e.g., "2330")
            year: Year (e.g., 2026)
            month: Month (1-12)

        Returns:
            List of dicts with OHLCV data
        """
        date_str = f"{year}{month:02d}01"

        params = {
            "response": "json",
            "date": date_str,
            "stockNo": symbol,
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        }

        for attempt in range(RETRY_COUNT + 1):
            try:
                self.rate_limiter.acquire()

                response = requests.get(
                    TWSE_HISTORY_URL,
                    params=params,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()

                data = response.json()

                if data.get("stat") != "OK":
                    logger.warning(f"TWSE returned non-OK for {symbol}: {data.get('stat')}")
                    return []

                rows = []
                for row in data.get("data", []):
                    try:
                        # Format: [日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌價差, 成交筆數]
                        date = self._parse_roc_date(row[0])
                        volume = self._parse_int(row[1])
                        open_price = self._parse_number(row[3])
                        high = self._parse_number(row[4])
                        low = self._parse_number(row[5])
                        close = self._parse_number(row[6])

                        if close is not None:
                            rows.append({
                                "date": date,
                                "open": open_price,
                                "high": high,
                                "low": low,
                                "close": close,
                                "volume": volume,
                            })
                    except (IndexError, ValueError) as e:
                        logger.debug(f"Skipping row for {symbol}: {e}")
                        continue

                logger.info(f"Fetched {len(rows)} days for {symbol} ({year}/{month:02d})")
                return rows

            except requests.RequestException as e:
                logger.warning(f"Request failed for {symbol} (attempt {attempt + 1}): {e}")
                if attempt < RETRY_COUNT:
                    import time
                    time.sleep(RETRY_DELAY)

        return []

    def ensure_history(self, symbol: str, min_days: int = 60) -> bool:
        """
        Ensure sufficient historical data exists for MA calculation.

        Args:
            symbol: Stock symbol (with or without .TW suffix)
            min_days: Minimum trading days needed

        Returns:
            True if data is available, False otherwise
        """
        clean_symbol = self._strip_suffix(symbol)

        existing_days = self.store.count_days(clean_symbol)

        if existing_days >= min_days:
            logger.debug(f"{clean_symbol} has {existing_days} days, sufficient")
            return True

        logger.info(f"{clean_symbol} has {existing_days} days, fetching more...")

        # Calculate months to fetch (4 months ~ 80 trading days, ensures 60+ days)
        months_needed = 4
        now = datetime.now()

        all_rows = []
        for i in range(months_needed):
            target = now - timedelta(days=30 * i)
            rows = self._fetch_history_month(clean_symbol, target.year, target.month)
            all_rows.extend(rows)

        if not all_rows:
            logger.error(f"Failed to fetch history for {clean_symbol}")
            return False

        # Store in database
        self.store.bulk_insert(clean_symbol, all_rows)
        self.store.update_sync_status(clean_symbol, months_needed)

        new_count = self.store.count_days(clean_symbol)
        logger.info(f"{clean_symbol} now has {new_count} days")

        return new_count >= min_days

    def fetch_realtime_batch(self, symbols: list[str]) -> dict[str, dict]:
        """
        Fetch real-time quotes for multiple stocks.

        Args:
            symbols: List of stock symbols (with or without .TW suffix)

        Returns:
            Dict mapping symbol to quote data
        """
        results = {}

        # Clean symbols and prepare batches
        clean_symbols = [self._strip_suffix(s) for s in symbols]
        batch_size = 10
        batches = [
            clean_symbols[i:i + batch_size]
            for i in range(0, len(clean_symbols), batch_size)
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        }

        for batch in batches:
            try:
                self.rate_limiter.acquire()

                # Build query string: tse_2330.tw|tse_2317.tw|...
                ex_ch = "|".join(f"tse_{s}.tw" for s in batch)
                url = f"{TWSE_REALTIME_URL}?ex_ch={ex_ch}&json=1&delay=0"

                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()

                data = response.json()

                for item in data.get("msgArray", []):
                    symbol = item.get("c", "")
                    if not symbol:
                        continue

                    price = self._parse_number(item.get("z"))
                    if price is None:
                        # Try yesterday's close if no trade yet
                        price = self._parse_number(item.get("y"))

                    results[symbol] = {
                        "price": price,
                        "open": self._parse_number(item.get("o")),
                        "high": self._parse_number(item.get("h")),
                        "low": self._parse_number(item.get("l")),
                        "yesterday_close": self._parse_number(item.get("y")),
                        "volume": self._parse_int(item.get("v")),
                        "name": item.get("n", ""),
                        "time": item.get("t", ""),
                    }

            except requests.RequestException as e:
                logger.error(f"Realtime fetch failed for batch: {e}")
                continue

        self._realtime_cache.update(results)
        return results

    def update_today_price(self, symbol: str, realtime_data: dict):
        """
        Update today's price in the database using realtime data.

        Args:
            symbol: Stock symbol (without suffix)
            realtime_data: Dict with price, open, high, low, volume
        """
        if realtime_data.get("price") is None:
            return

        today = datetime.now().strftime("%Y-%m-%d")

        self.store.upsert(
            symbol=symbol,
            date=today,
            open=realtime_data.get("open"),
            high=realtime_data.get("high"),
            low=realtime_data.get("low"),
            close=realtime_data.get("price"),
            volume=realtime_data.get("volume"),
        )

    def calculate_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate moving averages for the given DataFrame.

        Args:
            df: DataFrame with 'Close' column

        Returns:
            DataFrame with added MA columns (ma5, ma10, ma20, ma60)
        """
        result = df.copy()

        for period in MA_PERIODS:
            col_name = f"ma{period}"
            result[col_name] = result["Close"].rolling(window=period).mean()

        return result

    def fetch_and_process(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch stock data and calculate moving averages.

        Same interface as the original DataEngine.

        Args:
            symbol: Stock symbol (e.g., "2330.TW" or "2330")

        Returns:
            Processed DataFrame with MAs, or None if fetch fails
        """
        clean_symbol = self._strip_suffix(symbol)

        # Ensure we have historical data
        if not self.ensure_history(clean_symbol):
            self._health.record_failure(symbol, "Failed to fetch history from TWSE")
            return None

        # Fetch realtime quote if not cached
        if clean_symbol not in self._realtime_cache:
            self.fetch_realtime_batch([clean_symbol])

        # Update today's price if available
        if clean_symbol in self._realtime_cache:
            self.update_today_price(clean_symbol, self._realtime_cache[clean_symbol])

        # Load from database
        df = self.store.load_dataframe(clean_symbol)

        if df is None or df.empty:
            self._health.record_failure(symbol, "No data in database")
            return None

        # Calculate moving averages
        df = self.calculate_moving_averages(df)

        self._cache[symbol] = df
        self._health.record_success(symbol)

        return df

    def get_cached(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get cached data for a symbol."""
        return self._cache.get(symbol)

    def get_realtime(self, symbol: str) -> Optional[dict]:
        """Get cached realtime data for a symbol."""
        clean_symbol = self._strip_suffix(symbol)
        return self._realtime_cache.get(clean_symbol)

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._realtime_cache.clear()

    def prefetch_realtime(self, symbols: list[str]):
        """
        Pre-fetch realtime quotes for all symbols.

        Call this before processing to batch the requests efficiently.
        """
        self.fetch_realtime_batch(symbols)

# backend/twse_sector_fetcher.py
"""TWSE sector stock fetcher with caching and rate limiting."""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from backend.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Shared rate limiter for all TWSE requests
_rate_limiter = RateLimiter(max_requests=3, period=5.0)

# Request headers to avoid being blocked
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.twse.com.tw/",
}

# TWSE API endpoints
TWSE_MI_INDEX = "https://www.twse.com.tw/exchangeReport/MI_INDEX"
TWSE_STOCK_DAY = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG"

CACHE_FILE = Path(__file__).parent.parent / "data" / "sector_cache.json"
CACHE_MAX_AGE_DAYS = 7

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2


def _make_request(url: str, params: dict = None, retries: int = MAX_RETRIES) -> Optional[dict]:
    """
    Make a rate-limited request with retries.

    Args:
        url: Request URL
        params: Query parameters
        retries: Number of retries remaining

    Returns:
        JSON response or None if failed
    """
    for attempt in range(retries):
        try:
            _rate_limiter.acquire()

            response = requests.get(
                url,
                params=params,
                headers=REQUEST_HEADERS,
                timeout=15
            )

            if response.status_code != 200:
                logger.warning(f"TWSE returned status {response.status_code}")
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                continue

            # Check if response is valid JSON
            text = response.text.strip()
            if not text or text.startswith("<"):
                logger.warning(f"TWSE returned non-JSON response")
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                continue

            return response.json()

        except requests.RequestException as e:
            logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)

    return None


class TwseSectorFetcher:
    """Fetches and caches stock lists from TWSE."""

    def __init__(self):
        """Initialize the fetcher."""
        self._cache: Optional[dict] = None

    def is_cache_expired(self) -> bool:
        """Check if cache file is expired or missing."""
        if not CACHE_FILE.exists():
            return True

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            cached_time = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
            return datetime.now() - cached_time > timedelta(days=CACHE_MAX_AGE_DAYS)
        except Exception:
            return True

    def _get_recent_trading_date(self) -> str:
        """Get the most recent trading date (skip weekends)."""
        now = datetime.now()
        # If weekend, go back to Friday
        weekday = now.weekday()
        if weekday == 5:  # Saturday
            now -= timedelta(days=1)
        elif weekday == 6:  # Sunday
            now -= timedelta(days=2)
        return now.strftime("%Y%m%d")

    def fetch_top_trading_from_mi_index(self) -> list[str]:
        """
        Fetch top trading stocks from MI_INDEX endpoint.

        Returns:
            List of stock symbols with .TW suffix
        """
        date_str = self._get_recent_trading_date()
        logger.info(f"Fetching MI_INDEX for date: {date_str}")

        params = {
            "response": "json",
            "date": date_str,
            "type": "ALLBUT0999",  # All stocks except ETF
        }

        data = _make_request(TWSE_MI_INDEX, params)

        if not data:
            return []

        if data.get("stat") != "OK":
            logger.warning(f"MI_INDEX returned: {data.get('stat')}")
            return []

        stocks = []
        # data9 contains the main stock list
        for row in data.get("data9", []):
            try:
                if len(row) >= 5:
                    symbol = row[0].strip()
                    # Filter: only regular stocks (4 digits, not starting with 00)
                    if len(symbol) == 4 and symbol.isdigit() and not symbol.startswith("00"):
                        # Get trading value (index 4) for sorting
                        trading_value_str = row[4].replace(",", "")
                        trading_value = int(trading_value_str) if trading_value_str.isdigit() else 0
                        stocks.append((symbol, trading_value))
            except (IndexError, ValueError):
                continue

        # Sort by trading value descending
        stocks.sort(key=lambda x: x[1], reverse=True)

        # Return top symbols with .TW suffix
        result = [f"{s[0]}.TW" for s in stocks[:150]]
        logger.info(f"Fetched {len(result)} stocks from MI_INDEX")
        return result

    def refresh_cache(self) -> bool:
        """Refresh the stock cache."""
        try:
            symbols = self.fetch_top_trading_from_mi_index()

            if not symbols:
                logger.warning("No symbols fetched, keeping old cache")
                return False

            cache_data = {
                "updated_at": datetime.now().isoformat(),
                "symbols": symbols,
            }

            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            self._cache = cache_data
            logger.info(f"Cache refreshed with {len(symbols)} symbols")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            return False

    def load_cache(self) -> dict:
        """Load cache from file."""
        if self._cache:
            return self._cache

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
            return self._cache
        except Exception:
            return {"symbols": []}

    def get_all_symbols(self) -> list[str]:
        """
        Get all symbols from cache.

        Returns:
            List of stock symbols
        """
        if self.is_cache_expired():
            self.refresh_cache()

        cache = self.load_cache()
        return cache.get("symbols", [])


    def fetch_from_bwibbu(self) -> list[str]:
        """
        Fetch stock list from BWIBBU (本益比/殖利率/股價淨值比) endpoint.
        This endpoint is more reliable and works outside market hours.

        Returns:
            List of stock symbols sorted by trading activity
        """
        params = {
            "response": "json",
            "selectType": "ALL",
        }

        url = "https://www.twse.com.tw/exchangeReport/BWIBBU_d"
        data = _make_request(url, params)

        if not data:
            return []

        if data.get("stat") != "OK":
            logger.warning(f"BWIBBU returned: {data.get('stat')}")
            return []

        stocks = []
        for row in data.get("data", []):
            try:
                if len(row) >= 1:
                    symbol = row[0].strip()
                    # Filter: only regular stocks (4 digits, not starting with 00)
                    if len(symbol) == 4 and symbol.isdigit() and not symbol.startswith("00"):
                        stocks.append(f"{symbol}.TW")
            except (IndexError, ValueError):
                continue

        logger.info(f"Fetched {len(stocks)} stocks from BWIBBU")
        return stocks


# Convenience function for backward compatibility
def fetch_top_trading_value_stocks(count: int = 100) -> list[str]:
    """
    Fetch top trading value stocks.

    Args:
        count: Maximum number of stocks to return

    Returns:
        List of stock symbols with .TW suffix
    """
    fetcher = TwseSectorFetcher()
    symbols = fetcher.get_all_symbols()

    if symbols:
        return symbols[:count] if len(symbols) > count else symbols

    # Try MI_INDEX first (market hours only)
    logger.info("Cache empty, trying MI_INDEX...")
    symbols = fetcher.fetch_top_trading_from_mi_index()

    if symbols:
        # Save to cache
        fetcher._cache = {"updated_at": datetime.now().isoformat(), "symbols": symbols}
        return symbols[:count] if len(symbols) > count else symbols

    # Fallback to BWIBBU (works outside market hours)
    logger.info("MI_INDEX failed, trying BWIBBU...")
    symbols = fetcher.fetch_from_bwibbu()

    if symbols:
        # Save to cache
        fetcher._cache = {"updated_at": datetime.now().isoformat(), "symbols": symbols}
        return symbols[:count] if len(symbols) > count else symbols

    logger.warning("All TWSE fetch methods failed")
    return []

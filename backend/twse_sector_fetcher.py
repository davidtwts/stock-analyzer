# backend/twse_sector_fetcher.py
"""TWSE sector stock fetcher with caching."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# TWSE sector codes
SECTOR_CODES = {
    "半導體": "24",
    "金融": "17",
    "電子零組件": "26",
    "傳產": "01",  # Cement as example, will expand
}

# Additional traditional industry sectors
TRADITIONAL_SECTORS = ["01", "02", "03", "04", "05", "21", "22"]

CACHE_FILE = Path(__file__).parent.parent / "data" / "sector_cache.json"
CACHE_MAX_AGE_DAYS = 7


class TwseSectorFetcher:
    """Fetches and caches stock lists by sector from TWSE."""

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

    def fetch_sector(self, sector_name: str) -> list[str]:
        """
        Fetch stocks for a specific sector from TWSE.

        Args:
            sector_name: Chinese sector name

        Returns:
            List of stock symbols with .TW suffix
        """
        sector_code = SECTOR_CODES.get(sector_name)
        if not sector_code:
            logger.warning(f"Unknown sector: {sector_name}")
            return []

        try:
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json&type={sector_code}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                logger.error(f"TWSE request failed: {response.status_code}")
                return []

            data = response.json()
            stocks = []

            for row in data.get("data", []):
                if len(row) >= 1:
                    symbol = row[0].strip()
                    if symbol.isdigit() and not symbol.startswith("00"):
                        stocks.append(f"{symbol}.TW")

            logger.info(f"Fetched {len(stocks)} stocks for sector {sector_name}")
            return stocks

        except Exception as e:
            logger.error(f"Error fetching sector {sector_name}: {e}")
            return []

    def fetch_all_sectors(self) -> dict[str, list[str]]:
        """Fetch all configured sectors."""
        result = {}
        for sector_name in SECTOR_CODES:
            result[sector_name] = self.fetch_sector(sector_name)
        return result

    def refresh_cache(self) -> bool:
        """Refresh the sector cache."""
        try:
            sectors = self.fetch_all_sectors()

            # Flatten to unique symbols
            all_symbols = set()
            for stocks in sectors.values():
                all_symbols.update(stocks)

            cache_data = {
                "updated_at": datetime.now().isoformat(),
                "sectors": sectors,
                "symbols": sorted(all_symbols),
            }

            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            self._cache = cache_data
            logger.info(f"Cache refreshed with {len(all_symbols)} unique symbols")
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
            return {"symbols": [], "sectors": {}}

    def get_all_symbols(self) -> list[str]:
        """
        Get all symbols from all sectors.

        Returns:
            List of stock symbols
        """
        if self.is_cache_expired():
            self.refresh_cache()

        cache = self.load_cache()
        return cache.get("symbols", [])


# Convenience function for backward compatibility
def fetch_top_trading_value_stocks(count: int = 100) -> list[str]:
    """
    Fetch top trading value stocks.

    This maintains backward compatibility with the existing function
    while also including sector-based stocks.
    """
    fetcher = TwseSectorFetcher()
    symbols = fetcher.get_all_symbols()

    if symbols:
        return symbols[:count] if len(symbols) > count else symbols

    # Fallback: try original TWSE API
    try:
        url = "https://www.twse.com.tw/exchangeReport/MI_INDEX20?response=json"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            stocks = []
            for row in data.get("data", [])[:count]:
                if len(row) >= 1:
                    symbol = row[0].strip()
                    if symbol.isdigit() and not symbol.startswith("00"):
                        stocks.append(f"{symbol}.TW")
            return stocks
    except Exception as e:
        logger.error(f"Error fetching top trading stocks: {e}")

    return []

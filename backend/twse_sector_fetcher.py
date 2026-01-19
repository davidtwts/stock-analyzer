# backend/twse_sector_fetcher.py
"""TWSE sector stock fetcher with caching."""

import json
import logging
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Session 偽裝：模擬真實瀏覽器
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# 防封鎖配置
REQUEST_DELAY_MIN = 1.0   # TWSE 較寬鬆，可以短一點
REQUEST_DELAY_MAX = 3.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

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
        self._session = self._create_session()
        self._last_request_time = 0.0

    def _create_session(self) -> requests.Session:
        """創建帶偽裝的 Session."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.twse.com.tw/",
        })
        return session

    def _random_delay(self):
        """隨機延遲，避免固定間隔被偵測."""
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        elapsed = time.time() - self._last_request_time
        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug(f"TWSE rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

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
        Fetch stocks for a specific sector from TWSE with retry.

        Args:
            sector_name: Chinese sector name

        Returns:
            List of stock symbols with .TW suffix
        """
        sector_code = SECTOR_CODES.get(sector_name)
        if not sector_code:
            logger.warning(f"Unknown sector: {sector_name}")
            return []

        for attempt in range(MAX_RETRIES):
            try:
                # 隨機延遲 + 速率限制
                self._random_delay()

                # 偶爾更換 User-Agent
                if random.random() < 0.3:
                    self._session.headers["User-Agent"] = random.choice(USER_AGENTS)

                url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json&type={sector_code}"
                response = self._session.get(url, timeout=15)

                # 處理速率限制
                if response.status_code == 429:
                    backoff_time = REQUEST_DELAY_MAX * (BACKOFF_FACTOR ** attempt)
                    logger.warning(
                        f"TWSE rate limited, attempt {attempt + 1}/{MAX_RETRIES}. "
                        f"Backing off {backoff_time:.1f}s"
                    )
                    time.sleep(backoff_time)
                    continue

                if response.status_code != 200:
                    logger.error(f"TWSE request failed: {response.status_code}")
                    return []

                data = response.json()
                stocks = []

                for row in data.get("data", []):
                    if len(row) >= 1:
                        symbol = row[0].strip()
                        # 過濾 ETF (00)、權證 (01-08)、特別股
                        if symbol.startswith(('00', '01', '02', '03', '04', '05', '06', '07', '08')):
                            continue
                        if len(symbol) > 4:  # 過濾 2330-KY 或特別股
                            continue
                        if symbol.isdigit():
                            stocks.append(f"{symbol}.TW")

                logger.info(f"Fetched {len(stocks)} stocks for sector {sector_name}")
                return stocks

            except Exception as e:
                error_str = str(e).lower()
                if "timeout" in error_str or "connection" in error_str:
                    backoff_time = REQUEST_DELAY_MAX * (BACKOFF_FACTOR ** attempt)
                    logger.warning(f"TWSE connection error, retrying in {backoff_time:.1f}s: {e}")
                    time.sleep(backoff_time)
                    continue

                logger.error(f"Error fetching sector {sector_name}: {e}")
                return []

        logger.error(f"All {MAX_RETRIES} attempts failed for sector {sector_name}")
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

    # Fallback: try original TWSE API (使用 fetcher 的 session)
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

            url = "https://www.twse.com.tw/exchangeReport/MI_INDEX20?response=json"
            response = fetcher._session.get(url, timeout=15)

            if response.status_code == 429:
                backoff_time = REQUEST_DELAY_MAX * (BACKOFF_FACTOR ** attempt)
                logger.warning(f"TWSE fallback rate limited, backing off {backoff_time:.1f}s")
                time.sleep(backoff_time)
                continue

            if response.status_code == 200:
                data = response.json()
                stocks = []
                for row in data.get("data", [])[:count]:
                    if len(row) >= 1:
                        symbol = row[0].strip()
                        # 過濾 ETF (00)、權證 (01-08)、特別股
                        if symbol.startswith(('00', '01', '02', '03', '04', '05', '06', '07', '08')):
                            continue
                        if len(symbol) > 4:  # 過濾 2330-KY 或特別股
                            continue
                        if symbol.isdigit():
                            stocks.append(f"{symbol}.TW")
                return stocks

        except Exception as e:
            logger.error(f"Error fetching top trading stocks: {e}")

    return []

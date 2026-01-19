# backend/data_engine.py
"""Data engine for fetching stock data from Yahoo Finance."""

import logging
import random
import time
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from backend.config import MA_PERIODS, FETCH_PERIOD
from backend.ticker_health import TickerHealth

logger = logging.getLogger(__name__)

# Session 偽裝：模擬真實瀏覽器
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# 防封鎖配置
REQUEST_DELAY_MIN = 2.0   # 最小延遲秒數
REQUEST_DELAY_MAX = 5.0   # 最大延遲秒數
MAX_RETRIES = 3           # 最大重試次數
BACKOFF_FACTOR = 2        # 指數退避倍數


class DataEngine:
    """Handles stock data fetching and processing."""

    def __init__(self):
        """Initialize the data engine."""
        self._cache: dict[str, pd.DataFrame] = {}
        self._health = TickerHealth()
        self._session = self._create_session()
        self._last_request_time = 0.0

    def _create_session(self) -> requests.Session:
        """創建帶偽裝的 Session."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        })
        return session

    def _random_delay(self):
        """隨機延遲，避免固定間隔被偵測."""
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        # 確保距離上次請求有足夠間隔
        elapsed = time.time() - self._last_request_time
        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def fetch_stock(self, symbol: str, period: str = FETCH_PERIOD) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a single stock with retry and backoff.

        Args:
            symbol: Stock symbol (e.g., "2330.TW")
            period: Data period (e.g., "6mo", "1y")

        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        for attempt in range(MAX_RETRIES):
            try:
                # 隨機延遲 + 速率限制
                self._random_delay()

                # 偶爾更換 User-Agent
                if random.random() < 0.3:
                    self._session.headers["User-Agent"] = random.choice(USER_AGENTS)

                # 使用帶偽裝的 session
                ticker = yf.Ticker(symbol, session=self._session)
                df = ticker.history(period=period)

                if df.empty:
                    logger.warning(f"No data returned for {symbol}")
                    self._health.record_failure(symbol, "No data returned")
                    return None

                # Reset index to make Date a column
                df = df.reset_index()

                logger.info(f"Fetched {len(df)} rows for {symbol}")
                self._health.record_success(symbol)
                return df

            except Exception as e:
                error_str = str(e).lower()

                # 檢測 429 Too Many Requests 或其他速率限制錯誤
                if "429" in error_str or "too many" in error_str or "rate limit" in error_str:
                    backoff_time = REQUEST_DELAY_MAX * (BACKOFF_FACTOR ** attempt)
                    logger.warning(
                        f"Rate limited on {symbol}, attempt {attempt + 1}/{MAX_RETRIES}. "
                        f"Backing off {backoff_time:.1f}s"
                    )
                    time.sleep(backoff_time)
                    continue

                # 其他錯誤直接失敗
                logger.error(f"Failed to fetch {symbol}: {e}")
                self._health.record_failure(symbol, str(e))
                return None

        # 所有重試都失敗
        logger.error(f"All {MAX_RETRIES} attempts failed for {symbol}")
        self._health.record_failure(symbol, "Max retries exceeded")
        return None

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

        Args:
            symbol: Stock symbol

        Returns:
            Processed DataFrame with MAs, or None if fetch fails
        """
        df = self.fetch_stock(symbol)

        if df is None:
            return None

        df = self.calculate_moving_averages(df)
        self._cache[symbol] = df

        return df

    def get_cached(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get cached data for a symbol."""
        return self._cache.get(symbol)

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()

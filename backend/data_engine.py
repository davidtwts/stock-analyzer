# backend/data_engine.py
"""Data engine for fetching stock data from Yahoo Finance."""

import logging
from typing import Optional

import pandas as pd
import yfinance as yf

from backend.config import MA_PERIODS, FETCH_PERIOD
from backend.ticker_health import TickerHealth

logger = logging.getLogger(__name__)


class DataEngine:
    """Handles stock data fetching and processing."""

    def __init__(self):
        """Initialize the data engine."""
        self._cache: dict[str, pd.DataFrame] = {}
        self._health = TickerHealth()

    def fetch_stock(self, symbol: str, period: str = FETCH_PERIOD) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a single stock.

        Args:
            symbol: Stock symbol (e.g., "2330.TW")
            period: Data period (e.g., "6mo", "1y")

        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        try:
            ticker = yf.Ticker(symbol)
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
            logger.error(f"Failed to fetch {symbol}: {e}")
            self._health.record_failure(symbol, str(e))
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

# backend/screener.py
"""Stock screener with MA alignment and risk/reward strategies."""

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from backend.config import (
    MIN_RISK_REWARD,
    STOCK_NAMES,
    MIN_AVG_VOLUME,
    VOLUME_BREAKOUT_RATIO,
    MIN_PRICE,
    MAX_PRICE,
)
from backend.data_engine import DataEngine

logger = logging.getLogger(__name__)


@dataclass
class ScreenResult:
    """Result for a screened stock."""
    symbol: str
    name: str
    price: float
    change_pct: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    volume: int
    avg_volume: float
    volume_ratio: float
    slope_5ma: Optional[float] = None
    slope_10ma: Optional[float] = None
    slope_20ma: Optional[float] = None


class Screener:
    """Stock screener with configurable strategies."""

    def __init__(self, data_engine: Optional[DataEngine] = None):
        """Initialize screener with optional data engine."""
        self.data_engine = data_engine or DataEngine()

    def check_price_range(self, price: float) -> bool:
        """
        Check if stock price is within acceptable range.

        Args:
            price: Current stock price

        Returns:
            True if within range, False otherwise
        """
        return MIN_PRICE <= price <= MAX_PRICE

    def check_volume(self, df: pd.DataFrame) -> dict:
        """
        Check if stock meets volume criteria.

        Criteria:
        - 20-day average volume >= MIN_AVG_VOLUME
        - Current volume >= VOLUME_BREAKOUT_RATIO * 20-day avg

        Args:
            df: DataFrame with Volume column

        Returns:
            Dict with volume, avg_volume, volume_ratio, and passed status
        """
        if df.empty or "Volume" not in df.columns:
            return {"passed": False, "volume": 0, "avg_volume": 0, "volume_ratio": 0}

        # Get current volume and 20-day average
        current_volume = int(df.iloc[-1]["Volume"])
        avg_volume = df["Volume"].tail(20).mean()

        if avg_volume == 0:
            return {"passed": False, "volume": current_volume, "avg_volume": 0, "volume_ratio": 0}

        volume_ratio = current_volume / avg_volume

        # Check criteria
        passed = (
            avg_volume >= MIN_AVG_VOLUME and
            volume_ratio >= VOLUME_BREAKOUT_RATIO
        )

        return {
            "passed": passed,
            "volume": current_volume,
            "avg_volume": round(avg_volume, 0),
            "volume_ratio": round(volume_ratio, 2),
        }

    def check_ma_alignment(self, df: pd.DataFrame) -> bool:
        """
        Check if stock has bullish MA alignment.

        Condition: 5MA > 10MA > 20MA > 60MA

        Args:
            df: DataFrame with ma5, ma10, ma20, ma60 columns

        Returns:
            True if bullish alignment, False otherwise
        """
        if df.empty:
            return False

        latest = df.iloc[-1]

        # Check all MA values exist
        ma_cols = ["ma5", "ma10", "ma20", "ma60"]
        for col in ma_cols:
            if col not in df.columns or pd.isna(latest[col]):
                return False

        # Check bullish alignment
        return (
            latest["ma5"] > latest["ma10"] >
            latest["ma20"] > latest["ma60"]
        )

    def calculate_risk_reward(
        self,
        df: pd.DataFrame,
        current_price: float
    ) -> dict:
        """
        Calculate risk/reward ratio.

        Stop loss: min(20MA, recent 20-day low)
        Take profit: current + 3 * risk

        Args:
            df: DataFrame with price data
            current_price: Current stock price

        Returns:
            Dict with stop_loss, take_profit, risk_reward_ratio
        """
        latest = df.iloc[-1]

        # Get 20MA value
        ma20 = latest.get("ma20", current_price * 0.95)
        if pd.isna(ma20):
            ma20 = current_price * 0.95

        # Get recent 20-day low
        recent_low = df["Low"].tail(20).min()

        # Stop loss is the lower of MA20 and recent low
        stop_loss = min(ma20, recent_low)

        # Calculate risk
        risk = current_price - stop_loss

        if risk <= 0:
            # Price below stop loss, invalid setup
            return {
                "stop_loss": stop_loss,
                "take_profit": current_price,
                "risk_reward_ratio": 0,
            }

        # Take profit with 3:1 ratio
        take_profit = current_price + (risk * 3)
        risk_reward_ratio = 3.0

        return {
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "risk_reward_ratio": round(risk_reward_ratio, 2),
        }

    def calculate_ma_slopes(self, df: pd.DataFrame) -> dict:
        """
        Calculate MA slopes as percentage change per day.

        Lookback periods match MA periods:
        - 5MA: 5 days
        - 10MA: 10 days
        - 20MA: 20 days

        Args:
            df: DataFrame with ma5, ma10, ma20 columns

        Returns:
            Dict with slope_5ma, slope_10ma, slope_20ma (% per day)
        """
        slopes = {
            "slope_5ma": None,
            "slope_10ma": None,
            "slope_20ma": None,
        }

        ma_configs = [
            ("ma5", "slope_5ma", 5),
            ("ma10", "slope_10ma", 10),
            ("ma20", "slope_20ma", 20),
        ]

        for ma_col, slope_key, lookback in ma_configs:
            if ma_col not in df.columns or len(df) < lookback + 1:
                continue

            current = df.iloc[-1][ma_col]
            past = df.iloc[-(lookback + 1)][ma_col]

            if pd.isna(current) or pd.isna(past) or past == 0:
                continue

            # Percentage change per day
            slope = ((current - past) / past / lookback) * 100
            slopes[slope_key] = round(slope, 3)

        return slopes

    def screen_stock(self, symbol: str) -> Optional[ScreenResult]:
        """
        Screen a single stock.

        Args:
            symbol: Stock symbol

        Returns:
            ScreenResult if passes criteria, None otherwise
        """
        df = self.data_engine.fetch_and_process(symbol)

        if df is None or len(df) < 60:
            logger.warning(f"{symbol}: Insufficient data")
            return None

        latest = df.iloc[-1]
        current_price = latest["Close"]

        # Check price range
        if not self.check_price_range(current_price):
            logger.debug(f"{symbol}: Price {current_price} outside range [{MIN_PRICE}, {MAX_PRICE}]")
            return None

        # Check volume criteria
        vol = self.check_volume(df)
        if not vol["passed"]:
            logger.debug(f"{symbol}: Volume criteria not met (avg={vol['avg_volume']}, ratio={vol['volume_ratio']})")
            return None

        # Check MA alignment
        if not self.check_ma_alignment(df):
            logger.debug(f"{symbol}: MA alignment not met")
            return None

        # Calculate risk/reward (no filtering - client handles this now)
        rr = self.calculate_risk_reward(df, current_price)

        # Calculate change percentage
        if len(df) >= 2:
            prev_close = df.iloc[-2]["Close"]
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            change_pct = 0

        # Calculate MA slopes
        slopes = self.calculate_ma_slopes(df)

        return ScreenResult(
            symbol=symbol,
            name=STOCK_NAMES.get(symbol, symbol),
            price=round(current_price, 2),
            change_pct=round(change_pct, 2),
            ma5=round(latest["ma5"], 2),
            ma10=round(latest["ma10"], 2),
            ma20=round(latest["ma20"], 2),
            ma60=round(latest["ma60"], 2),
            stop_loss=rr["stop_loss"],
            take_profit=rr["take_profit"],
            risk_reward_ratio=rr["risk_reward_ratio"],
            volume=vol["volume"],
            avg_volume=vol["avg_volume"],
            volume_ratio=vol["volume_ratio"],
            slope_5ma=slopes["slope_5ma"],
            slope_10ma=slopes["slope_10ma"],
            slope_20ma=slopes["slope_20ma"],
        )

    def screen_all(self, symbols: list[str]) -> list[ScreenResult]:
        """
        Screen multiple stocks.

        Args:
            symbols: List of stock symbols

        Returns:
            List of ScreenResult for stocks passing criteria
        """
        # Filter out quarantined symbols
        active_symbols = self.data_engine._health.get_active_symbols(symbols)
        skipped = len(symbols) - len(active_symbols)
        if skipped > 0:
            logger.info(f"Screening {len(active_symbols)} active symbols (skipped {skipped} quarantined)")

        results = []

        for symbol in active_symbols:
            try:
                result = self.screen_stock(symbol)
                if result:
                    results.append(result)
                    logger.info(f"{symbol}: PASSED - R/R {result.risk_reward_ratio}")
            except Exception as e:
                logger.error(f"{symbol}: Error - {e}")

        return results

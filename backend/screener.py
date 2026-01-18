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

        # Calculate risk/reward
        rr = self.calculate_risk_reward(df, current_price)

        if rr["risk_reward_ratio"] < MIN_RISK_REWARD:
            logger.debug(f"{symbol}: R/R ratio {rr['risk_reward_ratio']} < {MIN_RISK_REWARD}")
            return None

        # Calculate change percentage
        if len(df) >= 2:
            prev_close = df.iloc[-2]["Close"]
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            change_pct = 0

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
        )

    def screen_all(self, symbols: list[str]) -> list[ScreenResult]:
        """
        Screen multiple stocks.

        Args:
            symbols: List of stock symbols

        Returns:
            List of ScreenResult for stocks passing criteria
        """
        results = []

        for symbol in symbols:
            try:
                result = self.screen_stock(symbol)
                if result:
                    results.append(result)
                    logger.info(f"{symbol}: PASSED - R/R {result.risk_reward_ratio}")
            except Exception as e:
                logger.error(f"{symbol}: Error - {e}")

        return results

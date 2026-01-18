# backend/tests/test_screener.py
"""Tests for stock screener."""

import pytest
import pandas as pd

from backend.screener import Screener


class TestScreener:
    """Test cases for Screener."""

    def test_check_ma_alignment_bullish(self):
        """Test detection of bullish MA alignment."""
        screener = Screener()

        # Create bullish alignment: 5MA > 10MA > 20MA > 60MA
        data = {
            "Close": [100],
            "ma5": [105],
            "ma10": [103],
            "ma20": [100],
            "ma60": [95],
        }
        df = pd.DataFrame(data)

        assert screener.check_ma_alignment(df) == True

    def test_check_ma_alignment_bearish(self):
        """Test detection of bearish MA alignment."""
        screener = Screener()

        # Create bearish alignment: 5MA < 10MA < 20MA < 60MA
        data = {
            "Close": [100],
            "ma5": [95],
            "ma10": [100],
            "ma20": [103],
            "ma60": [105],
        }
        df = pd.DataFrame(data)

        assert screener.check_ma_alignment(df) == False

    def test_calculate_risk_reward(self):
        """Test risk/reward calculation."""
        screener = Screener()

        # Create sample data
        data = {
            "Close": [100, 102, 101, 103, 105],
            "Low": [98, 100, 99, 101, 103],
            "ma20": [None, None, None, None, 100],
        }
        df = pd.DataFrame(data)
        current_price = 105

        result = screener.calculate_risk_reward(df, current_price)

        assert "stop_loss" in result
        assert "take_profit" in result
        assert "risk_reward_ratio" in result
        assert result["stop_loss"] < current_price
        assert result["take_profit"] > current_price

    def test_risk_reward_ratio_calculation(self):
        """Test that R/R ratio is calculated correctly."""
        screener = Screener()

        data = {
            "Close": [100] * 20,
            "Low": [95] * 20,
            "ma20": [None] * 19 + [90],
        }
        df = pd.DataFrame(data)
        current_price = 100

        result = screener.calculate_risk_reward(df, current_price)

        # Stop loss should be min(ma20=90, recent_low=95) = 90
        # Risk = 100 - 90 = 10
        # Take profit = 100 + (10 * 3) = 130
        # R/R = 30 / 10 = 3.0
        assert result["stop_loss"] == 90
        assert result["take_profit"] == 130
        assert result["risk_reward_ratio"] == 3.0

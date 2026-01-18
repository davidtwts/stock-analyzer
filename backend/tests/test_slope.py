# backend/tests/test_slope.py
"""Tests for MA slope calculation."""

import pandas as pd
import pytest
from backend.screener import Screener


class TestMaSlope:
    """Test MA slope calculations."""

    def test_calculate_ma_slope_rising(self):
        """Test slope calculation for rising MA."""
        screener = Screener()

        # Create mock data: 5MA rising from 100 to 102.5 over 5 days
        # slope = (102.5 - 100) / 100 / 5 * 100 = 0.5% per day
        data = {
            "ma5": [100.0, 100.5, 101.0, 101.5, 102.0, 102.5],
            "ma10": [95.0, 95.3, 95.6, 95.9, 96.2, 96.5],
            "ma20": [90.0, 90.15, 90.30, 90.45, 90.60, 90.75],
        }
        df = pd.DataFrame(data)

        slopes = screener.calculate_ma_slopes(df)

        assert abs(slopes["slope_5ma"] - 0.5) < 0.01
        assert abs(slopes["slope_10ma"] - 0.316) < 0.01
        assert abs(slopes["slope_20ma"] - 0.167) < 0.01

    def test_calculate_ma_slope_flat(self):
        """Test slope calculation for flat MA."""
        screener = Screener()

        data = {
            "ma5": [100.0] * 10,
            "ma10": [100.0] * 10,
            "ma20": [100.0] * 10,
        }
        df = pd.DataFrame(data)

        slopes = screener.calculate_ma_slopes(df)

        assert slopes["slope_5ma"] == 0.0
        assert slopes["slope_10ma"] == 0.0
        assert slopes["slope_20ma"] == 0.0

    def test_calculate_ma_slope_insufficient_data(self):
        """Test slope returns None for insufficient data."""
        screener = Screener()

        # Only 3 rows, not enough for 5-day lookback
        data = {"ma5": [100.0, 101.0, 102.0]}
        df = pd.DataFrame(data)

        slopes = screener.calculate_ma_slopes(df)

        assert slopes["slope_5ma"] is None

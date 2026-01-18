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

        # Need 21 rows for 20-day lookback (lookback + 1 = 21)
        # 5MA: rising from 100 to 102.5 over 5 days = 0.5% per day
        # 10MA: rising from 95 to 98 over 10 days = (98-95)/95/10*100 = 0.316% per day
        # 20MA: rising from 90 to 93 over 20 days = (93-90)/90/20*100 = 0.167% per day
        num_rows = 21

        # Generate linear sequences ending at target values
        ma5_data = [100.0 + (102.5 - 100.0) * i / 5 for i in range(-15, 6)]  # last 6 values: 100 to 102.5
        ma10_data = [95.0 + (98.0 - 95.0) * i / 10 for i in range(-10, 11)]  # last 11 values: 95 to 98
        ma20_data = [90.0 + (93.0 - 90.0) * i / 20 for i in range(0, 21)]  # 21 values: 90 to 93

        data = {
            "ma5": ma5_data,
            "ma10": ma10_data,
            "ma20": ma20_data,
        }
        df = pd.DataFrame(data)

        slopes = screener.calculate_ma_slopes(df)

        assert abs(slopes["slope_5ma"] - 0.5) < 0.01
        assert abs(slopes["slope_10ma"] - 0.316) < 0.01
        assert abs(slopes["slope_20ma"] - 0.167) < 0.01

    def test_calculate_ma_slope_flat(self):
        """Test slope calculation for flat MA."""
        screener = Screener()

        # Need 21 rows for 20-day lookback
        data = {
            "ma5": [100.0] * 21,
            "ma10": [100.0] * 21,
            "ma20": [100.0] * 21,
        }
        df = pd.DataFrame(data)

        slopes = screener.calculate_ma_slopes(df)

        assert slopes["slope_5ma"] == 0.0
        assert slopes["slope_10ma"] == 0.0
        assert slopes["slope_20ma"] == 0.0

    def test_calculate_ma_slope_insufficient_data(self):
        """Test slope returns None for insufficient data."""
        screener = Screener()

        # Only 3 rows, not enough for any lookback period
        data = {"ma5": [100.0, 101.0, 102.0]}
        df = pd.DataFrame(data)

        slopes = screener.calculate_ma_slopes(df)

        # All slopes should be None: 5MA needs 6 rows, 10MA needs 11, 20MA needs 21
        assert slopes["slope_5ma"] is None
        assert slopes["slope_10ma"] is None
        assert slopes["slope_20ma"] is None

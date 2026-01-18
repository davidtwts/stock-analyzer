# backend/tests/test_data_engine.py
"""Tests for data engine."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime

from backend.data_engine import DataEngine


class TestDataEngine:
    """Test cases for DataEngine."""

    def test_fetch_single_stock_returns_dataframe(self):
        """Test that fetch returns a DataFrame with required columns."""
        engine = DataEngine()

        # Create mock data that simulates yfinance response
        mock_data = pd.DataFrame({
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [104.0, 105.0, 106.0],
            "Volume": [1000000, 1100000, 1200000],
        }, index=pd.DatetimeIndex([
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3)
        ], name="Date"))

        with patch("backend.data_engine.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = mock_data
            df = engine.fetch_stock("2330.TW", period="1mo")

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert all(col in df.columns for col in ["Open", "High", "Low", "Close", "Volume"])

    def test_calculate_moving_averages(self):
        """Test MA calculation adds correct columns."""
        engine = DataEngine()

        # Create sample data
        data = {
            "Close": [100, 102, 101, 103, 105, 104, 106, 108, 107, 109] * 7
        }
        df = pd.DataFrame(data)

        result = engine.calculate_moving_averages(df)

        assert "ma5" in result.columns
        assert "ma10" in result.columns
        assert "ma20" in result.columns
        assert "ma60" in result.columns

    def test_fetch_stock_handles_invalid_symbol(self):
        """Test graceful handling of invalid symbol."""
        engine = DataEngine()

        # Mock yfinance to return empty DataFrame for invalid symbol
        with patch("backend.data_engine.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()
            df = engine.fetch_stock("INVALID.TW", period="1mo")

        assert df is None or len(df) == 0

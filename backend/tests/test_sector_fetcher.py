# backend/tests/test_sector_fetcher.py
"""Tests for TWSE sector fetcher."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend.twse_sector_fetcher import (
    TwseSectorFetcher,
    SECTOR_CODES,
    CACHE_FILE,
)


class TestTwseSectorFetcher:
    """Test TWSE sector fetching functionality."""

    def test_sector_codes_defined(self):
        """Test that sector codes are properly defined."""
        assert "半導體" in SECTOR_CODES
        assert "金融" in SECTOR_CODES
        assert "電子零組件" in SECTOR_CODES
        assert "傳產" in SECTOR_CODES

    @patch('backend.twse_sector_fetcher.requests.get')
    def test_fetch_sector_stocks(self, mock_get):
        """Test fetching stocks for a sector."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                ["2330", "台積電", "半導體"],
                ["2454", "聯發科", "半導體"],
            ]
        }
        mock_get.return_value = mock_response

        fetcher = TwseSectorFetcher()
        stocks = fetcher.fetch_sector("半導體")

        assert "2330.TW" in stocks
        assert "2454.TW" in stocks

    @patch('backend.twse_sector_fetcher.CACHE_FILE')
    def test_cache_expiry_check(self, mock_cache_file):
        """Test cache expiry logic."""
        # Mock cache file that doesn't exist
        mock_cache_file.exists.return_value = False

        fetcher = TwseSectorFetcher()

        # Test with no cache file
        assert fetcher.is_cache_expired() is True

    @patch.object(TwseSectorFetcher, 'is_cache_expired', return_value=False)
    def test_get_all_symbols_returns_list(self, mock_expired):
        """Test get_all_symbols returns a list."""
        fetcher = TwseSectorFetcher()
        # Mock the cache to avoid network calls
        fetcher._cache = {"symbols": ["2330.TW", "2317.TW"]}

        symbols = fetcher.get_all_symbols()

        assert isinstance(symbols, list)
        assert len(symbols) == 2

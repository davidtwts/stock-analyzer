# backend/tests/test_ticker_health.py
"""Tests for ticker health management."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.ticker_health import (
    TickerHealth,
    classify_failure,
    FAILURE_THRESHOLD,
    RETRY_INTERVAL_DAYS,
)


@pytest.fixture
def health():
    """Create a TickerHealth instance with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_health.db"
        yield TickerHealth(db_path=db_path)


class TestClassifyFailure:
    """Tests for failure classification."""

    def test_no_data_classification(self):
        assert classify_failure("No data returned for 2330.TW") == "no_data"
        assert classify_failure("No price data found") == "no_data"

    def test_json_parse_classification(self):
        assert classify_failure("Expecting value: line 1 column 1") == "json_parse"

    def test_delisted_classification(self):
        assert classify_failure("symbol may be delisted") == "delisted"

    def test_timeout_classification(self):
        assert classify_failure("Request timeout") == "timeout"

    def test_unknown_classification(self):
        assert classify_failure("Some random error") == "unknown"


class TestRecordFailure:
    """Tests for recording failures."""

    def test_first_failure_increments_count(self, health):
        """First failure sets count to 1, status stays active."""
        health.record_failure("2330.TW", "No data returned")

        assert not health.is_quarantined("2330.TW")
        summary = health.get_status_summary()
        assert summary["active"] == 1
        assert summary["quarantined"] == 0

    def test_quarantine_after_threshold_failures(self, health):
        """Symbol is quarantined after FAILURE_THRESHOLD consecutive failures."""
        for i in range(FAILURE_THRESHOLD):
            health.record_failure("2330.TW", "No data returned")

        assert health.is_quarantined("2330.TW")
        summary = health.get_status_summary()
        assert summary["quarantined"] == 1

    def test_failure_logged_to_history(self, health):
        """Each failure is logged to the failure_log table."""
        health.record_failure("2330.TW", "Error 1")
        health.record_failure("2330.TW", "Error 2")

        summary = health.get_status_summary()
        assert summary["total_failures"] == 2


class TestRecordSuccess:
    """Tests for recording successes."""

    def test_success_resets_failure_count(self, health):
        """Successful fetch resets consecutive failure count."""
        health.record_failure("2330.TW", "Error")
        health.record_success("2330.TW")

        # Another failure should be count 1, not 2
        health.record_failure("2330.TW", "Error")
        assert not health.is_quarantined("2330.TW")

    def test_success_recovers_from_quarantine(self, health):
        """Successful fetch recovers a quarantined symbol."""
        # Quarantine the symbol
        for _ in range(FAILURE_THRESHOLD):
            health.record_failure("2330.TW", "Error")
        assert health.is_quarantined("2330.TW")

        # Recover with success
        health.record_success("2330.TW")
        assert not health.is_quarantined("2330.TW")

    def test_new_symbol_success(self, health):
        """Recording success for a new symbol creates an active record."""
        health.record_success("2330.TW")

        assert not health.is_quarantined("2330.TW")
        summary = health.get_status_summary()
        assert summary["active"] == 1


class TestGetActiveSymbols:
    """Tests for filtering active symbols."""

    def test_filters_quarantined_symbols(self, health):
        """Quarantined symbols are excluded from the active list."""
        # Quarantine one symbol
        for _ in range(FAILURE_THRESHOLD):
            health.record_failure("0050.TW", "Error")

        # Keep another active
        health.record_success("2330.TW")

        symbols = ["2330.TW", "0050.TW", "2317.TW"]
        active = health.get_active_symbols(symbols)

        assert "2330.TW" in active
        assert "2317.TW" in active  # Unknown symbols are considered active
        assert "0050.TW" not in active

    def test_empty_list_returns_empty(self, health):
        """Empty input returns empty output."""
        assert health.get_active_symbols([]) == []

    def test_all_active_returns_all(self, health):
        """If no symbols are quarantined, all are returned."""
        symbols = ["2330.TW", "2317.TW"]
        assert health.get_active_symbols(symbols) == symbols


class TestGetRetryCandidates:
    """Tests for retry candidate selection."""

    def test_returns_candidates_past_retry_date(self, health):
        """Returns quarantined symbols past their retry date."""
        import sqlite3
        from datetime import time

        # Quarantine a symbol
        for _ in range(FAILURE_THRESHOLD):
            health.record_failure("2330.TW", "Error")

        # Manually set next_retry_at to the past
        past = datetime.now() - timedelta(days=1)
        with sqlite3.connect(health.db_path) as conn:
            conn.execute(
                "UPDATE ticker_status SET next_retry_at = ? WHERE symbol = ?",
                (past, "2330.TW")
            )
            conn.commit()

        # Mock market hours to always be open
        with patch('backend.ticker_health.MARKET_OPEN', time(0, 0)), \
             patch('backend.ticker_health.MARKET_CLOSE', time(23, 59)):
            candidates = health.get_retry_candidates()
            assert "2330.TW" in candidates

    def test_respects_market_hours(self, health):
        """Returns empty list outside market hours."""
        import sqlite3
        from datetime import time

        # Quarantine a symbol
        for _ in range(FAILURE_THRESHOLD):
            health.record_failure("2330.TW", "Error")

        # Set next_retry_at to the past
        past = datetime.now() - timedelta(days=1)
        with sqlite3.connect(health.db_path) as conn:
            conn.execute(
                "UPDATE ticker_status SET next_retry_at = ? WHERE symbol = ?",
                (past, "2330.TW")
            )
            conn.commit()

        # Mock market hours to never be open (market closed at midnight)
        with patch('backend.ticker_health.MARKET_OPEN', time(0, 0)), \
             patch('backend.ticker_health.MARKET_CLOSE', time(0, 1)):
            # Current time is likely not between 00:00 and 00:01
            candidates = health.get_retry_candidates()
            # Should be empty since market is "closed"
            assert candidates == []


class TestUpdateRetrySchedule:
    """Tests for updating retry schedule."""

    def test_updates_next_retry_date(self, health):
        """Updates the next retry date after a failed retry."""
        # Quarantine a symbol
        for _ in range(FAILURE_THRESHOLD):
            health.record_failure("2330.TW", "Error")

        # Update retry schedule
        health.update_retry_schedule("2330.TW")

        # Verify next_retry_at is set to ~RETRY_INTERVAL_DAYS in the future
        import sqlite3
        with sqlite3.connect(health.db_path) as conn:
            row = conn.execute(
                "SELECT next_retry_at FROM ticker_status WHERE symbol = ?",
                ("2330.TW",)
            ).fetchone()

        next_retry = datetime.fromisoformat(row[0])
        expected = datetime.now() + timedelta(days=RETRY_INTERVAL_DAYS)
        # Allow 1 minute tolerance
        assert abs((next_retry - expected).total_seconds()) < 60


class TestStatusSummary:
    """Tests for status summary."""

    def test_returns_correct_counts(self, health):
        """Returns accurate counts of active and quarantined symbols."""
        # Create some active symbols
        health.record_success("2330.TW")
        health.record_success("2317.TW")

        # Create a quarantined symbol
        for _ in range(FAILURE_THRESHOLD):
            health.record_failure("0050.TW", "Error")

        summary = health.get_status_summary()
        assert summary["active"] == 2
        assert summary["quarantined"] == 1
        assert summary["total_failures"] == FAILURE_THRESHOLD

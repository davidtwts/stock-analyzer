# backend/tests/test_line_notifier.py
"""Tests for LINE Messaging API integration."""

import pytest
from unittest.mock import patch, MagicMock
from backend.line_notifier import LineNotifier, format_stock_alert


class TestLineNotifier:
    """Test LINE Messaging API functionality."""

    def test_format_stock_alert(self):
        """Test alert message formatting."""
        stock = {
            "symbol": "2330.TW",
            "name": "台積電",
            "price": 580.0,
            "change_pct": 1.25,
            "slope_5ma": 0.52,
            "slope_10ma": 0.31,
            "slope_20ma": 0.18,
            "risk_reward": 3.2,
            "volume_ratio": 1.8,
        }

        message = format_stock_alert(stock)

        assert "台積電" in message
        assert "580" in message
        assert "1.25%" in message
        assert "0.52%" in message

    @patch('backend.line_notifier.requests.post')
    def test_send_notification_success(self, mock_post):
        """Test successful notification send."""
        mock_post.return_value = MagicMock(status_code=200)

        notifier = LineNotifier(channel_token="test_token", user_id="test_user")
        result = notifier.send("Test message")

        assert result is True
        mock_post.assert_called_once()

    @patch('backend.line_notifier.requests.post')
    def test_send_notification_no_token(self, mock_post):
        """Test notification skipped when no channel token."""
        notifier = LineNotifier(channel_token=None, user_id="test_user")
        result = notifier.send("Test message")

        assert result is False
        mock_post.assert_not_called()

    @patch('backend.line_notifier.requests.post')
    def test_send_notification_no_user_id(self, mock_post):
        """Test notification skipped when no user ID."""
        notifier = LineNotifier(channel_token="test_token", user_id=None)
        result = notifier.send("Test message")

        assert result is False
        mock_post.assert_not_called()

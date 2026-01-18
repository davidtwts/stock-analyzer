# backend/line_notifier.py
"""LINE Messaging API integration for stock alerts."""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# LINE Messaging API endpoint
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def format_stock_alert(stock: dict) -> str:
    """Format a stock dict into a LINE alert message."""
    change_symbol = "▲" if stock["change_pct"] >= 0 else "▼"

    return f"""📈 新符合條件股票

{stock['symbol'].replace('.TW', '')} {stock['name']}
價格: ${stock['price']} ({change_symbol}{abs(stock['change_pct']):.2f}%)
斜率: 5MA {stock.get('slope_5ma', 0):.2f}% | 10MA {stock.get('slope_10ma', 0):.2f}% | 20MA {stock.get('slope_20ma', 0):.2f}%
損益比: {stock['risk_reward']:.1f}:1
量比: {stock['volume_ratio']:.1f}x"""


def format_volume_spike_alert(stock: dict, volume_5min: int, volume_ratio: float) -> str:
    """Format a volume spike alert message."""
    change_symbol = "▲" if stock.get("change_pct", 0) >= 0 else "▼"

    return f"""⚡ 成交量異常

{stock['symbol'].replace('.TW', '')} {stock['name']}
5分鐘成交量: {volume_5min:,}張 ({volume_ratio:.1f}x 平均)
現價: ${stock['price']} ({change_symbol}{abs(stock.get('change_pct', 0)):.2f}%)"""


class LineNotifier:
    """LINE Messaging API client."""

    def __init__(self, channel_token: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize LINE Messaging API client.

        Args:
            channel_token: LINE Channel Access Token (or LINE_CHANNEL_TOKEN env var)
            user_id: LINE User ID to send messages to (or LINE_USER_ID env var)
        """
        self.channel_token = channel_token or os.environ.get("LINE_CHANNEL_TOKEN")
        self.user_id = user_id or os.environ.get("LINE_USER_ID")

    def send(self, message: str) -> bool:
        """Send a push message via LINE Messaging API."""
        if not self.channel_token:
            logger.debug("LINE_CHANNEL_TOKEN not set, skipping notification")
            return False

        if not self.user_id:
            logger.debug("LINE_USER_ID not set, skipping notification")
            return False

        headers = {
            "Authorization": f"Bearer {self.channel_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        }

        try:
            response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("LINE message sent successfully")
                return True
            else:
                logger.error(f"LINE message failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"LINE message error: {e}")
            return False

    def send_stock_alert(self, stock: dict) -> bool:
        """Send a new stock match alert."""
        message = format_stock_alert(stock)
        return self.send(message)

    def send_volume_spike_alert(self, stock: dict, volume_5min: int, volume_ratio: float) -> bool:
        """Send a volume spike alert."""
        message = format_volume_spike_alert(stock, volume_5min, volume_ratio)
        return self.send(message)

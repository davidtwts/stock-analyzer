# backend/line_notifier.py
"""LINE Notify integration for stock alerts."""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


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
    """LINE Notify client."""

    def __init__(self, token: Optional[str] = None):
        """Initialize LINE Notifier."""
        self.token = token or os.environ.get("LINE_NOTIFY_TOKEN")

    def send(self, message: str) -> bool:
        """Send a notification via LINE Notify."""
        if not self.token:
            logger.debug("LINE_NOTIFY_TOKEN not set, skipping notification")
            return False

        headers = {"Authorization": f"Bearer {self.token}"}
        data = {"message": message}

        try:
            response = requests.post(LINE_NOTIFY_URL, headers=headers, data=data)
            if response.status_code == 200:
                logger.info("LINE notification sent successfully")
                return True
            else:
                logger.error(f"LINE notification failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"LINE notification error: {e}")
            return False

    def send_stock_alert(self, stock: dict) -> bool:
        """Send a new stock match alert."""
        message = format_stock_alert(stock)
        return self.send(message)

    def send_volume_spike_alert(self, stock: dict, volume_5min: int, volume_ratio: float) -> bool:
        """Send a volume spike alert."""
        message = format_volume_spike_alert(stock, volume_5min, volume_ratio)
        return self.send(message)

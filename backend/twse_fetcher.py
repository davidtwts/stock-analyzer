# backend/twse_fetcher.py
"""Fetch top trading value stocks from TWSE."""

import logging
from datetime import datetime
from typing import Optional

import requests

from backend.config import TOP_TRADING_VALUE_COUNT

logger = logging.getLogger(__name__)

# TWSE API for daily trading summary
TWSE_API_URL = "https://www.twse.com.tw/exchangeReport/MI_INDEX"


def fetch_top_trading_value_stocks(count: int = TOP_TRADING_VALUE_COUNT) -> list[str]:
    """
    Fetch top N stocks by trading value from TWSE.

    Args:
        count: Number of top stocks to return (default: 100)

    Returns:
        List of stock symbols (e.g., ['2330.TW', '2317.TW', ...])
    """
    try:
        # Get today's date in TWSE format
        today = datetime.now().strftime("%Y%m%d")

        params = {
            "response": "json",
            "date": today,
            "type": "ALLBUT0999",  # All stocks except ETF
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        }

        response = requests.get(TWSE_API_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        if data.get("stat") != "OK":
            logger.warning(f"TWSE API returned non-OK status: {data.get('stat')}")
            return []

        # Parse the data - fields are in data9 for listed stocks
        # Format: [代號, 名稱, 成交股數, 成交筆數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌, 漲跌價差, ...]
        stocks_data = data.get("data9", [])

        if not stocks_data:
            logger.warning("No stock data found in TWSE response")
            return []

        # Parse and sort by trading value (index 4)
        parsed_stocks = []
        for row in stocks_data:
            try:
                symbol = row[0].strip()
                # Trading value is in index 4, formatted with commas
                trading_value_str = row[4].replace(",", "")
                trading_value = int(trading_value_str)
                parsed_stocks.append((symbol, trading_value))
            except (IndexError, ValueError) as e:
                continue

        # Sort by trading value (descending)
        parsed_stocks.sort(key=lambda x: x[1], reverse=True)

        # Get top N symbols with .TW suffix
        top_symbols = [f"{s[0]}.TW" for s in parsed_stocks[:count]]

        logger.info(f"Fetched top {len(top_symbols)} stocks by trading value")
        return top_symbols

    except requests.RequestException as e:
        logger.error(f"Failed to fetch TWSE data: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing TWSE data: {e}")
        return []


def get_stock_name_from_twse(symbol: str) -> Optional[str]:
    """
    Get stock name from TWSE (if not in predefined list).

    Args:
        symbol: Stock symbol (e.g., '2330.TW')

    Returns:
        Stock name or None
    """
    # This would require another API call, for now return None
    # The main screening will use the name from yfinance if available
    return None

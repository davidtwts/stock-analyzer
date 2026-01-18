# Stock Screener Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the stock screener with MA slope filtering, optional R/R toggle, sector expansion, LINE alerts, and watchlist volume spike alerts.

**Architecture:** Backend calculates MA slopes and returns all MA-aligned stocks (no server-side filtering for slope/R/R). Frontend handles dynamic filtering via sliders/toggles. LINE Notify integration for alerts. Watchlist stored in localStorage with backend monitoring for volume spikes.

**Tech Stack:** Python/FastAPI (backend), Vue 3/Tailwind (frontend), LINE Notify API, TWSE scraping

---

## Task 1: MA Slope Calculation - Tests

**Files:**
- Create: `backend/tests/test_slope.py`

**Step 1: Write the failing test for slope calculation**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/test_slope.py -v`

Expected: FAIL with "AttributeError: 'Screener' object has no attribute 'calculate_ma_slopes'"

**Step 3: Commit test**

```bash
git add backend/tests/test_slope.py
git commit -m "test: add MA slope calculation tests"
```

---

## Task 2: MA Slope Calculation - Implementation

**Files:**
- Modify: `backend/screener.py`

**Step 1: Add calculate_ma_slopes method to Screener class**

Add after `calculate_risk_reward` method (around line 179):

```python
    def calculate_ma_slopes(self, df: pd.DataFrame) -> dict:
        """
        Calculate MA slopes as percentage change per day.

        Lookback periods match MA periods:
        - 5MA: 5 days
        - 10MA: 10 days
        - 20MA: 20 days

        Args:
            df: DataFrame with ma5, ma10, ma20 columns

        Returns:
            Dict with slope_5ma, slope_10ma, slope_20ma (% per day)
        """
        slopes = {
            "slope_5ma": None,
            "slope_10ma": None,
            "slope_20ma": None,
        }

        ma_configs = [
            ("ma5", "slope_5ma", 5),
            ("ma10", "slope_10ma", 10),
            ("ma20", "slope_20ma", 20),
        ]

        for ma_col, slope_key, lookback in ma_configs:
            if ma_col not in df.columns or len(df) < lookback + 1:
                continue

            current = df.iloc[-1][ma_col]
            past = df.iloc[-(lookback + 1)][ma_col]

            if pd.isna(current) or pd.isna(past) or past == 0:
                continue

            # Percentage change per day
            slope = ((current - past) / past / lookback) * 100
            slopes[slope_key] = round(slope, 3)

        return slopes
```

**Step 2: Run test to verify it passes**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/test_slope.py -v`

Expected: 3 passed

**Step 3: Run all tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/ -v`

Expected: All tests pass

**Step 4: Commit implementation**

```bash
git add backend/screener.py
git commit -m "feat: add MA slope calculation"
```

---

## Task 3: Update ScreenResult and screen_stock

**Files:**
- Modify: `backend/screener.py`

**Step 1: Add slope fields to ScreenResult dataclass**

Update the ScreenResult dataclass (around line 24) to add:

```python
@dataclass
class ScreenResult:
    """Result for a screened stock."""
    symbol: str
    name: str
    price: float
    change_pct: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    volume: int
    avg_volume: float
    volume_ratio: float
    slope_5ma: Optional[float] = None
    slope_10ma: Optional[float] = None
    slope_20ma: Optional[float] = None
```

**Step 2: Update screen_stock to calculate and include slopes**

In `screen_stock` method, before creating ScreenResult (around line 230), add:

```python
        # Calculate MA slopes
        slopes = self.calculate_ma_slopes(df)
```

Then update the ScreenResult creation to include slopes:

```python
        return ScreenResult(
            symbol=symbol,
            name=STOCK_NAMES.get(symbol, symbol),
            price=round(current_price, 2),
            change_pct=round(change_pct, 2),
            ma5=round(latest["ma5"], 2),
            ma10=round(latest["ma10"], 2),
            ma20=round(latest["ma20"], 2),
            ma60=round(latest["ma60"], 2),
            stop_loss=rr["stop_loss"],
            take_profit=rr["take_profit"],
            risk_reward_ratio=rr["risk_reward_ratio"],
            volume=vol["volume"],
            avg_volume=vol["avg_volume"],
            volume_ratio=vol["volume_ratio"],
            slope_5ma=slopes["slope_5ma"],
            slope_10ma=slopes["slope_10ma"],
            slope_20ma=slopes["slope_20ma"],
        )
```

**Step 3: Run all tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/ -v`

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/screener.py
git commit -m "feat: add slope fields to ScreenResult"
```

---

## Task 4: Update API Response

**Files:**
- Modify: `backend/main.py`

**Step 1: Add slope fields to API response**

In `get_stocks` endpoint (around line 108), update the stock dict to include:

```python
            {
                "symbol": r.symbol,
                "name": r.name,
                "price": r.price,
                "change_pct": r.change_pct,
                "ma5": r.ma5,
                "ma10": r.ma10,
                "ma20": r.ma20,
                "ma60": r.ma60,
                "stop_loss": r.stop_loss,
                "take_profit": r.take_profit,
                "risk_reward": r.risk_reward_ratio,
                "volume": r.volume,
                "avg_volume": r.avg_volume,
                "volume_ratio": r.volume_ratio,
                "slope_5ma": r.slope_5ma,
                "slope_10ma": r.slope_10ma,
                "slope_20ma": r.slope_20ma,
            }
```

**Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: add slope fields to API response"
```

---

## Task 5: Remove Server-Side R/R Filtering

**Files:**
- Modify: `backend/screener.py`

**Step 1: Remove R/R check in screen_stock**

In `screen_stock` method, comment out or remove the R/R check (around lines 219-221):

```python
        # Remove this block - R/R filtering moves to client-side
        # if rr["risk_reward_ratio"] < MIN_RISK_REWARD:
        #     logger.debug(f"{symbol}: R/R ratio {rr['risk_reward_ratio']} < {MIN_RISK_REWARD}")
        #     return None
```

**Step 2: Run all tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/ -v`

Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/screener.py
git commit -m "feat: remove server-side R/R filtering (move to client)"
```

---

## Task 6: Frontend - Add Filter State

**Files:**
- Modify: `frontend/app.js`

**Step 1: Add filter state variables**

After line 13 (`const marketStatus = ref('closed');`), add:

```javascript
        // Filter state
        const allStocks = ref([]);  // Raw stocks from API
        const slopeFilters = ref({
            slope_5ma: 0.5,
            slope_10ma: 0.3,
            slope_20ma: 0.15,
        });
        const rrFilterEnabled = ref(true);
        const filtersExpanded = ref(true);
```

**Step 2: Add computed filteredStocks**

After the `marketStatusClass` computed (around line 24), add:

```javascript
        const filteredStocks = computed(() => {
            return allStocks.value.filter(stock => {
                // Slope filters
                if (stock.slope_5ma !== null && stock.slope_5ma < slopeFilters.value.slope_5ma) {
                    return false;
                }
                if (stock.slope_10ma !== null && stock.slope_10ma < slopeFilters.value.slope_10ma) {
                    return false;
                }
                if (stock.slope_20ma !== null && stock.slope_20ma < slopeFilters.value.slope_20ma) {
                    return false;
                }
                // R/R filter
                if (rrFilterEnabled.value && stock.risk_reward < 3.0) {
                    return false;
                }
                return true;
            });
        });
```

**Step 3: Update fetchStocks to use allStocks**

Update the `fetchStocks` function:

```javascript
        const fetchStocks = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/stocks`);
                const data = await res.json();
                allStocks.value = data.stocks;
                lastUpdate.value = data.updated_at;
                marketStatus.value = data.market_status;
            } catch (err) {
                console.error('Failed to fetch stocks:', err);
            } finally {
                loading.value = false;
            }
        };
```

**Step 4: Add resetFilters function**

After `selectStock` function:

```javascript
        const resetFilters = () => {
            slopeFilters.value = {
                slope_5ma: 0.5,
                slope_10ma: 0.3,
                slope_20ma: 0.15,
            };
            rrFilterEnabled.value = true;
        };
```

**Step 5: Update return statement**

Update the return statement to include new variables:

```javascript
        return {
            stocks: filteredStocks,  // Change from stocks to filteredStocks
            allStocks,
            selectedStock,
            loading,
            lastUpdate,
            nextUpdate,
            marketStatus,
            marketStatusClass,
            slopeFilters,
            rrFilterEnabled,
            filtersExpanded,
            formatTime,
            formatVolume,
            refresh,
            selectStock,
            resetFilters,
        };
```

**Step 6: Commit**

```bash
git add frontend/app.js
git commit -m "feat: add client-side slope and R/R filtering"
```

---

## Task 7: Frontend - Add Filter Panel UI

**Files:**
- Modify: `frontend/index.html`

**Step 1: Add filter panel before stock list**

In the sidebar (after line 35, before the h2 with "符合條件"), add:

```html
                    <!-- Filter Panel -->
                    <div class="mb-4 bg-gray-700 rounded-lg overflow-hidden">
                        <button
                            @click="filtersExpanded = !filtersExpanded"
                            class="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-gray-600"
                        >
                            <span class="font-medium">🎚️ 斜率篩選</span>
                            <span>{{ filtersExpanded ? '▼' : '▶' }}</span>
                        </button>

                        <div v-show="filtersExpanded" class="px-3 pb-3 space-y-3">
                            <!-- 5MA Slope -->
                            <div>
                                <label class="flex justify-between text-sm text-gray-400 mb-1">
                                    <span>5MA 斜率</span>
                                    <span>≥ {{ slopeFilters.slope_5ma.toFixed(2) }}%</span>
                                </label>
                                <input
                                    type="range"
                                    v-model.number="slopeFilters.slope_5ma"
                                    min="0" max="1.5" step="0.05"
                                    class="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer"
                                >
                            </div>

                            <!-- 10MA Slope -->
                            <div>
                                <label class="flex justify-between text-sm text-gray-400 mb-1">
                                    <span>10MA 斜率</span>
                                    <span>≥ {{ slopeFilters.slope_10ma.toFixed(2) }}%</span>
                                </label>
                                <input
                                    type="range"
                                    v-model.number="slopeFilters.slope_10ma"
                                    min="0" max="1.0" step="0.05"
                                    class="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer"
                                >
                            </div>

                            <!-- 20MA Slope -->
                            <div>
                                <label class="flex justify-between text-sm text-gray-400 mb-1">
                                    <span>20MA 斜率</span>
                                    <span>≥ {{ slopeFilters.slope_20ma.toFixed(2) }}%</span>
                                </label>
                                <input
                                    type="range"
                                    v-model.number="slopeFilters.slope_20ma"
                                    min="0" max="0.5" step="0.05"
                                    class="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer"
                                >
                            </div>

                            <!-- R/R Filter Toggle -->
                            <div class="flex items-center justify-between pt-2 border-t border-gray-600">
                                <label class="text-sm text-gray-400">損益比 ≥ 3:1</label>
                                <button
                                    @click="rrFilterEnabled = !rrFilterEnabled"
                                    :class="rrFilterEnabled ? 'bg-blue-600' : 'bg-gray-600'"
                                    class="relative w-12 h-6 rounded-full transition-colors"
                                >
                                    <span
                                        :class="rrFilterEnabled ? 'translate-x-6' : 'translate-x-1'"
                                        class="absolute top-1 left-0 w-4 h-4 bg-white rounded-full transition-transform"
                                    ></span>
                                </button>
                            </div>

                            <!-- Reset Button -->
                            <button
                                @click="resetFilters"
                                class="w-full py-1 text-sm text-gray-400 hover:text-white border border-gray-600 rounded"
                            >
                                重置預設
                            </button>
                        </div>
                    </div>
```

**Step 2: Update stock count display**

Change line 37 from:

```html
                    <h2 class="text-lg font-semibold mb-3">
                        📋 符合條件 ({{ stocks.length }}檔)
                    </h2>
```

To:

```html
                    <h2 class="text-lg font-semibold mb-3">
                        📋 符合條件 ({{ stocks.length }}/{{ allStocks.length }}檔)
                    </h2>
```

**Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add slope filter panel UI"
```

---

## Task 8: LINE Notifier - Tests

**Files:**
- Create: `backend/tests/test_line_notifier.py`

**Step 1: Write tests for LINE notifier**

```python
# backend/tests/test_line_notifier.py
"""Tests for LINE Notify integration."""

import pytest
from unittest.mock import patch, MagicMock
from backend.line_notifier import LineNotifier, format_stock_alert


class TestLineNotifier:
    """Test LINE notification functionality."""

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

    @patch('requests.post')
    def test_send_notification_success(self, mock_post):
        """Test successful notification send."""
        mock_post.return_value = MagicMock(status_code=200)

        notifier = LineNotifier("test_token")
        result = notifier.send("Test message")

        assert result is True
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_notification_no_token(self, mock_post):
        """Test notification skipped when no token."""
        notifier = LineNotifier(None)
        result = notifier.send("Test message")

        assert result is False
        mock_post.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/test_line_notifier.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'backend.line_notifier'"

**Step 3: Commit test**

```bash
git add backend/tests/test_line_notifier.py
git commit -m "test: add LINE notifier tests"
```

---

## Task 9: LINE Notifier - Implementation

**Files:**
- Create: `backend/line_notifier.py`

**Step 1: Create LINE notifier module**

```python
# backend/line_notifier.py
"""LINE Notify integration for stock alerts."""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


def format_stock_alert(stock: dict) -> str:
    """
    Format a stock dict into a LINE alert message.

    Args:
        stock: Stock data dict with symbol, name, price, etc.

    Returns:
        Formatted message string
    """
    change_symbol = "▲" if stock["change_pct"] >= 0 else "▼"

    return f"""📈 新符合條件股票

{stock['symbol'].replace('.TW', '')} {stock['name']}
價格: ${stock['price']} ({change_symbol}{abs(stock['change_pct']):.2f}%)
斜率: 5MA {stock.get('slope_5ma', 0):.2f}% | 10MA {stock.get('slope_10ma', 0):.2f}% | 20MA {stock.get('slope_20ma', 0):.2f}%
損益比: {stock['risk_reward']:.1f}:1
量比: {stock['volume_ratio']:.1f}x"""


def format_volume_spike_alert(stock: dict, volume_5min: int, volume_ratio: float) -> str:
    """
    Format a volume spike alert message.

    Args:
        stock: Stock data dict
        volume_5min: 5-minute volume
        volume_ratio: Ratio to average

    Returns:
        Formatted message string
    """
    change_symbol = "▲" if stock.get("change_pct", 0) >= 0 else "▼"

    return f"""⚡ 成交量異常

{stock['symbol'].replace('.TW', '')} {stock['name']}
5分鐘成交量: {volume_5min:,}張 ({volume_ratio:.1f}x 平均)
現價: ${stock['price']} ({change_symbol}{abs(stock.get('change_pct', 0)):.2f}%)"""


class LineNotifier:
    """LINE Notify client."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize LINE Notifier.

        Args:
            token: LINE Notify token. If None, reads from LINE_NOTIFY_TOKEN env var.
        """
        self.token = token or os.environ.get("LINE_NOTIFY_TOKEN")

    def send(self, message: str) -> bool:
        """
        Send a notification via LINE Notify.

        Args:
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
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
```

**Step 2: Run tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/test_line_notifier.py -v`

Expected: 3 passed

**Step 3: Commit**

```bash
git add backend/line_notifier.py
git commit -m "feat: add LINE Notify integration"
```

---

## Task 10: Integrate LINE Alerts into Screening

**Files:**
- Modify: `backend/main.py`

**Step 1: Add LINE notifier import and state**

After other imports (around line 24), add:

```python
from backend.line_notifier import LineNotifier
```

After `cached_results` declaration (around line 38), add:

```python
previous_symbols: set[str] = set()
line_notifier = LineNotifier()
```

**Step 2: Update run_screening to send alerts**

Update the `run_screening` function:

```python
def run_screening():
    """Run the stock screening process."""
    global cached_results, last_update, previous_symbols

    # First try to get top trading value stocks from TWSE
    top_stocks = fetch_top_trading_value_stocks(TOP_TRADING_VALUE_COUNT)

    # Fallback to Taiwan 50 if TWSE fetch fails
    if not top_stocks:
        logger.warning("Failed to fetch TWSE data, falling back to Taiwan 50")
        top_stocks = TAIWAN_50

    logger.info(f"Screening {len(top_stocks)} stocks...")
    cached_results = screener.screen_all(top_stocks)
    last_update = datetime.now()
    logger.info(f"Found {len(cached_results)} stocks matching criteria")

    # Check for new matches and send LINE alerts
    current_symbols = {r.symbol for r in cached_results}
    new_symbols = current_symbols - previous_symbols

    for result in cached_results:
        if result.symbol in new_symbols:
            stock_dict = {
                "symbol": result.symbol,
                "name": result.name,
                "price": result.price,
                "change_pct": result.change_pct,
                "slope_5ma": result.slope_5ma,
                "slope_10ma": result.slope_10ma,
                "slope_20ma": result.slope_20ma,
                "risk_reward": result.risk_reward_ratio,
                "volume_ratio": result.volume_ratio,
            }
            line_notifier.send_stock_alert(stock_dict)
            logger.info(f"Sent LINE alert for new match: {result.symbol}")

    previous_symbols = current_symbols
```

**Step 3: Run all tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/ -v`

Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: integrate LINE alerts for new screening matches"
```

---

## Task 11: TWSE Sector Fetcher - Tests

**Files:**
- Create: `backend/tests/test_sector_fetcher.py`

**Step 1: Write tests for sector fetcher**

```python
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

    def test_cache_expiry_check(self):
        """Test cache expiry logic."""
        fetcher = TwseSectorFetcher()

        # Test with no cache file
        assert fetcher.is_cache_expired() is True

    def test_get_all_symbols_returns_list(self):
        """Test get_all_symbols returns a list."""
        fetcher = TwseSectorFetcher()
        # Mock the cache to avoid network calls
        fetcher._cache = {"symbols": ["2330.TW", "2317.TW"]}

        symbols = fetcher.get_all_symbols()

        assert isinstance(symbols, list)
        assert len(symbols) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/test_sector_fetcher.py -v`

Expected: FAIL with import errors

**Step 3: Commit test**

```bash
git add backend/tests/test_sector_fetcher.py
git commit -m "test: add TWSE sector fetcher tests"
```

---

## Task 12: TWSE Sector Fetcher - Implementation

**Files:**
- Create: `backend/twse_sector_fetcher.py` (replace existing basic version)

**Step 1: Read existing twse_fetcher.py to understand current structure**

Run: `cat ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements/backend/twse_fetcher.py`

**Step 2: Create comprehensive sector fetcher**

```python
# backend/twse_sector_fetcher.py
"""TWSE sector stock fetcher with caching."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# TWSE sector codes
SECTOR_CODES = {
    "半導體": "24",
    "金融": "17",
    "電子零組件": "26",
    "傳產": "01",  # Cement as example, will expand
}

# Additional traditional industry sectors
TRADITIONAL_SECTORS = ["01", "02", "03", "04", "05", "21", "22"]

CACHE_FILE = Path(__file__).parent.parent / "data" / "sector_cache.json"
CACHE_MAX_AGE_DAYS = 7


class TwseSectorFetcher:
    """Fetches and caches stock lists by sector from TWSE."""

    def __init__(self):
        """Initialize the fetcher."""
        self._cache: Optional[dict] = None

    def is_cache_expired(self) -> bool:
        """Check if cache file is expired or missing."""
        if not CACHE_FILE.exists():
            return True

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            cached_time = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
            return datetime.now() - cached_time > timedelta(days=CACHE_MAX_AGE_DAYS)
        except Exception:
            return True

    def fetch_sector(self, sector_name: str) -> list[str]:
        """
        Fetch stocks for a specific sector from TWSE.

        Args:
            sector_name: Chinese sector name

        Returns:
            List of stock symbols with .TW suffix
        """
        sector_code = SECTOR_CODES.get(sector_name)
        if not sector_code:
            logger.warning(f"Unknown sector: {sector_name}")
            return []

        try:
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json&type={sector_code}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                logger.error(f"TWSE request failed: {response.status_code}")
                return []

            data = response.json()
            stocks = []

            for row in data.get("data", []):
                if len(row) >= 1:
                    symbol = row[0].strip()
                    if symbol.isdigit():
                        stocks.append(f"{symbol}.TW")

            logger.info(f"Fetched {len(stocks)} stocks for sector {sector_name}")
            return stocks

        except Exception as e:
            logger.error(f"Error fetching sector {sector_name}: {e}")
            return []

    def fetch_all_sectors(self) -> dict[str, list[str]]:
        """Fetch all configured sectors."""
        result = {}
        for sector_name in SECTOR_CODES:
            result[sector_name] = self.fetch_sector(sector_name)
        return result

    def refresh_cache(self) -> bool:
        """Refresh the sector cache."""
        try:
            sectors = self.fetch_all_sectors()

            # Flatten to unique symbols
            all_symbols = set()
            for stocks in sectors.values():
                all_symbols.update(stocks)

            cache_data = {
                "updated_at": datetime.now().isoformat(),
                "sectors": sectors,
                "symbols": sorted(all_symbols),
            }

            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            self._cache = cache_data
            logger.info(f"Cache refreshed with {len(all_symbols)} unique symbols")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            return False

    def load_cache(self) -> dict:
        """Load cache from file."""
        if self._cache:
            return self._cache

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
            return self._cache
        except Exception:
            return {"symbols": [], "sectors": {}}

    def get_all_symbols(self) -> list[str]:
        """
        Get all symbols from all sectors.

        Returns:
            List of stock symbols
        """
        if self.is_cache_expired():
            self.refresh_cache()

        cache = self.load_cache()
        return cache.get("symbols", [])


# Convenience function for backward compatibility
def fetch_top_trading_value_stocks(count: int = 100) -> list[str]:
    """
    Fetch top trading value stocks.

    This maintains backward compatibility with the existing function
    while also including sector-based stocks.
    """
    fetcher = TwseSectorFetcher()
    symbols = fetcher.get_all_symbols()

    if symbols:
        return symbols[:count] if len(symbols) > count else symbols

    # Fallback: try original TWSE API
    try:
        url = "https://www.twse.com.tw/exchangeReport/MI_INDEX20?response=json"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            stocks = []
            for row in data.get("data", [])[:count]:
                if len(row) >= 1:
                    symbol = row[0].strip()
                    if symbol.isdigit():
                        stocks.append(f"{symbol}.TW")
            return stocks
    except Exception as e:
        logger.error(f"Error fetching top trading stocks: {e}")

    return []
```

**Step 3: Run tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/test_sector_fetcher.py -v`

Expected: Tests pass (some may be skipped if network mocking isn't perfect)

**Step 4: Run all tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/ -v`

Expected: All tests pass

**Step 5: Commit**

```bash
git add backend/twse_sector_fetcher.py backend/tests/test_sector_fetcher.py
git commit -m "feat: add comprehensive TWSE sector fetcher with caching"
```

---

## Task 13: Watchlist API - Tests

**Files:**
- Create: `backend/tests/test_watchlist.py`

**Step 1: Write watchlist API tests**

```python
# backend/tests/test_watchlist.py
"""Tests for watchlist functionality."""

import pytest
from fastapi.testclient import TestClient


class TestWatchlistAPI:
    """Test watchlist endpoints."""

    def test_watchlist_structure(self):
        """Test watchlist data structure."""
        watchlist_item = {
            "symbol": "2330.TW",
            "alert_enabled": True,
        }

        assert "symbol" in watchlist_item
        assert "alert_enabled" in watchlist_item
        assert isinstance(watchlist_item["alert_enabled"], bool)
```

**Step 2: Commit test**

```bash
git add backend/tests/test_watchlist.py
git commit -m "test: add watchlist API tests"
```

---

## Task 14: Watchlist API Endpoints

**Files:**
- Modify: `backend/main.py`

**Step 1: Add watchlist state and endpoints**

After `line_notifier` declaration, add:

```python
# Watchlist state (in production, this would be in a database)
watchlist: dict[str, dict] = {}  # symbol -> {alert_enabled: bool, ...}
```

Add new endpoints before the static file routes:

```python
@app.get("/api/watchlist")
async def get_watchlist():
    """Get current watchlist."""
    return {"watchlist": list(watchlist.values())}


@app.post("/api/watchlist/{symbol}")
async def add_to_watchlist(symbol: str, alert_enabled: bool = True):
    """Add a stock to watchlist."""
    if not symbol.endswith(".TW"):
        symbol = f"{symbol}.TW"

    watchlist[symbol] = {
        "symbol": symbol,
        "name": STOCK_NAMES.get(symbol, symbol),
        "alert_enabled": alert_enabled,
    }
    return {"status": "ok", "item": watchlist[symbol]}


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Remove a stock from watchlist."""
    if not symbol.endswith(".TW"):
        symbol = f"{symbol}.TW"

    if symbol in watchlist:
        del watchlist[symbol]
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Stock not in watchlist")


@app.patch("/api/watchlist/{symbol}/alert")
async def toggle_watchlist_alert(symbol: str, enabled: bool):
    """Toggle alert for a watchlist item."""
    if not symbol.endswith(".TW"):
        symbol = f"{symbol}.TW"

    if symbol not in watchlist:
        raise HTTPException(status_code=404, detail="Stock not in watchlist")

    watchlist[symbol]["alert_enabled"] = enabled
    return {"status": "ok", "item": watchlist[symbol]}
```

**Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: add watchlist API endpoints"
```

---

## Task 15: Frontend Watchlist UI

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/index.html`

**Step 1: Add watchlist state to app.js**

After `filtersExpanded` ref, add:

```javascript
        // Watchlist state
        const watchlist = ref([]);
        const watchlistExpanded = ref(false);
        const showAddStock = ref(false);
        const newStockSymbol = ref('');
```

Add watchlist functions after `resetFilters`:

```javascript
        const fetchWatchlist = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/watchlist`);
                const data = await res.json();
                watchlist.value = data.watchlist;
            } catch (err) {
                console.error('Failed to fetch watchlist:', err);
            }
        };

        const addToWatchlist = async () => {
            if (!newStockSymbol.value) return;
            try {
                await fetch(`${API_BASE}/api/watchlist/${newStockSymbol.value}`, {
                    method: 'POST',
                });
                await fetchWatchlist();
                newStockSymbol.value = '';
                showAddStock.value = false;
            } catch (err) {
                console.error('Failed to add to watchlist:', err);
            }
        };

        const removeFromWatchlist = async (symbol) => {
            try {
                await fetch(`${API_BASE}/api/watchlist/${symbol}`, {
                    method: 'DELETE',
                });
                await fetchWatchlist();
            } catch (err) {
                console.error('Failed to remove from watchlist:', err);
            }
        };

        const toggleWatchlistAlert = async (symbol, enabled) => {
            try {
                await fetch(`${API_BASE}/api/watchlist/${symbol}/alert?enabled=${enabled}`, {
                    method: 'PATCH',
                });
                await fetchWatchlist();
            } catch (err) {
                console.error('Failed to toggle alert:', err);
            }
        };
```

Update `onMounted` to fetch watchlist:

```javascript
        onMounted(async () => {
            await fetchStocks();
            await fetchStatus();
            await fetchWatchlist();
            refreshInterval = setInterval(async () => {
                await fetchStocks();
                await fetchStatus();
            }, 300000);
            window.addEventListener('resize', handleResize);
        });
```

Update return statement to include watchlist:

```javascript
        return {
            stocks: filteredStocks,
            allStocks,
            selectedStock,
            loading,
            lastUpdate,
            nextUpdate,
            marketStatus,
            marketStatusClass,
            slopeFilters,
            rrFilterEnabled,
            filtersExpanded,
            watchlist,
            watchlistExpanded,
            showAddStock,
            newStockSymbol,
            formatTime,
            formatVolume,
            refresh,
            selectStock,
            resetFilters,
            addToWatchlist,
            removeFromWatchlist,
            toggleWatchlistAlert,
        };
```

**Step 2: Add watchlist UI to index.html**

After the filter panel div, add:

```html
                    <!-- Watchlist Panel -->
                    <div class="mb-4 bg-gray-700 rounded-lg overflow-hidden">
                        <button
                            @click="watchlistExpanded = !watchlistExpanded"
                            class="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-gray-600"
                        >
                            <span class="font-medium">⭐ 自選股監控</span>
                            <span>{{ watchlistExpanded ? '▼' : '▶' }}</span>
                        </button>

                        <div v-show="watchlistExpanded" class="px-3 pb-3">
                            <div v-if="watchlist.length === 0" class="text-sm text-gray-400 py-2">
                                尚無自選股
                            </div>
                            <div v-else class="space-y-2 mb-2">
                                <div
                                    v-for="item in watchlist"
                                    :key="item.symbol"
                                    class="flex items-center justify-between bg-gray-600 rounded px-2 py-1"
                                >
                                    <span class="text-sm">
                                        {{ item.symbol.replace('.TW', '') }} {{ item.name }}
                                    </span>
                                    <div class="flex items-center gap-2">
                                        <button
                                            @click="toggleWatchlistAlert(item.symbol, !item.alert_enabled)"
                                            :class="item.alert_enabled ? 'text-yellow-400' : 'text-gray-500'"
                                            class="text-lg"
                                        >
                                            {{ item.alert_enabled ? '🔔' : '🔕' }}
                                        </button>
                                        <button
                                            @click="removeFromWatchlist(item.symbol)"
                                            class="text-red-400 hover:text-red-300"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div v-if="showAddStock" class="flex gap-2 mt-2">
                                <input
                                    v-model="newStockSymbol"
                                    placeholder="股票代號"
                                    class="flex-1 bg-gray-600 rounded px-2 py-1 text-sm"
                                    @keyup.enter="addToWatchlist"
                                >
                                <button
                                    @click="addToWatchlist"
                                    class="bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded text-sm"
                                >
                                    加入
                                </button>
                            </div>
                            <button
                                v-else
                                @click="showAddStock = true"
                                class="w-full py-1 text-sm text-gray-400 hover:text-white border border-gray-600 rounded mt-2"
                            >
                                + 新增股票
                            </button>
                        </div>
                    </div>
```

**Step 3: Commit**

```bash
git add frontend/app.js frontend/index.html
git commit -m "feat: add watchlist UI with alert toggles"
```

---

## Task 16: Final Integration Test

**Step 1: Run all backend tests**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m pytest backend/tests/ -v`

Expected: All tests pass

**Step 2: Start the server locally and test manually**

Run: `cd ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements && python3 -m uvicorn backend.main:app --reload --port 8000`

Test in browser: Open `http://localhost:8000`

Verify:
- [ ] Slope filter sliders appear and work
- [ ] R/R toggle works
- [ ] Stock count shows filtered/total
- [ ] Watchlist panel appears
- [ ] Can add/remove stocks from watchlist
- [ ] Alert toggles work

**Step 3: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final integration fixes"
```

---

## Task 17: Merge to Main

**Step 1: Switch to main branch**

Run: `cd /Users/cengdewei/Desktop/stock-analyzer && git checkout main`

**Step 2: Merge feature branch**

Run: `git merge feature/screener-enhancements`

**Step 3: Push to remote**

Run: `git push origin main`

**Step 4: Clean up worktree**

Run: `git worktree remove ~/.config/superpowers/worktrees/stock-analyzer/feature-enhancements`

---

## Summary

| Task | Feature | Files |
|------|---------|-------|
| 1-4 | MA Slope Calculation | screener.py, main.py |
| 5 | Remove Server R/R Filter | screener.py |
| 6-7 | Frontend Filters | app.js, index.html |
| 8-10 | LINE Alerts | line_notifier.py, main.py |
| 11-12 | Sector Expansion | twse_sector_fetcher.py |
| 13-15 | Watchlist | main.py, app.js, index.html |
| 16-17 | Integration & Merge | - |

# Stock Screener Stage 1.5 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a real-time Taiwan stock screener with FastAPI backend and Vue.js dashboard.

**Architecture:** FastAPI serves stock data via REST API, APScheduler refreshes data every 5 minutes during market hours, Vue.js frontend displays filtered stocks with K-line charts using Lightweight Charts.

**Tech Stack:** Python 3.9+, FastAPI, yfinance, pandas, APScheduler, Vue 3, Tailwind CSS, Lightweight Charts

---

## Task 1: Project Setup & Dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/__init__.py`
- Create: `backend/config.py`

**Step 1: Create requirements.txt**

```txt
fastapi==0.109.0
uvicorn==0.27.0
yfinance==0.2.36
pandas==2.1.4
apscheduler==3.10.4
python-dateutil==2.8.2
```

**Step 2: Create empty __init__.py**

```python
# backend/__init__.py
```

**Step 3: Create config.py with Taiwan 50 stocks**

```python
# backend/config.py
"""Configuration for stock screener."""

from datetime import time

# Taiwan 50 component stocks (top 30 for faster iteration)
TAIWAN_50 = [
    "2330.TW",  # 台積電
    "2317.TW",  # 鴻海
    "2454.TW",  # 聯發科
    "2308.TW",  # 台達電
    "2881.TW",  # 富邦金
    "2882.TW",  # 國泰金
    "2303.TW",  # 聯電
    "1301.TW",  # 台塑
    "2886.TW",  # 兆豐金
    "3711.TW",  # 日月光投控
    "2891.TW",  # 中信金
    "1303.TW",  # 南亞
    "2884.TW",  # 玉山金
    "2357.TW",  # 華碩
    "2382.TW",  # 廣達
    "2412.TW",  # 中華電
    "2892.TW",  # 第一金
    "3045.TW",  # 台灣大
    "2002.TW",  # 中鋼
    "1216.TW",  # 統一
    "2207.TW",  # 和泰車
    "5880.TW",  # 合庫金
    "2301.TW",  # 光寶科
    "2880.TW",  # 華南金
    "3008.TW",  # 大立光
    "2327.TW",  # 國巨
    "4904.TW",  # 遠傳
    "2395.TW",  # 研華
    "6505.TW",  # 台塑化
    "2912.TW",  # 統一超
]

# Stock name mapping
STOCK_NAMES = {
    "2330.TW": "台積電",
    "2317.TW": "鴻海",
    "2454.TW": "聯發科",
    "2308.TW": "台達電",
    "2881.TW": "富邦金",
    "2882.TW": "國泰金",
    "2303.TW": "聯電",
    "1301.TW": "台塑",
    "2886.TW": "兆豐金",
    "3711.TW": "日月光投控",
    "2891.TW": "中信金",
    "1303.TW": "南亞",
    "2884.TW": "玉山金",
    "2357.TW": "華碩",
    "2382.TW": "廣達",
    "2412.TW": "中華電",
    "2892.TW": "第一金",
    "3045.TW": "台灣大",
    "2002.TW": "中鋼",
    "1216.TW": "統一",
    "2207.TW": "和泰車",
    "5880.TW": "合庫金",
    "2301.TW": "光寶科",
    "2880.TW": "華南金",
    "3008.TW": "大立光",
    "2327.TW": "國巨",
    "4904.TW": "遠傳",
    "2395.TW": "研華",
    "6505.TW": "台塑化",
    "2912.TW": "統一超",
}

# Moving average periods
MA_PERIODS = [5, 10, 20, 60]

# Risk/Reward ratio threshold
MIN_RISK_REWARD = 3.0

# Market hours (Taiwan: 09:00-13:30)
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(13, 30)

# Update interval (seconds)
UPDATE_INTERVAL = 300  # 5 minutes

# Data fetch period
FETCH_PERIOD = "6mo"
```

**Step 4: Install dependencies**

Run: `cd /Users/cengdewei/Desktop/stock-analyzer/backend && pip install -r requirements.txt`

**Step 5: Commit**

```bash
git add backend/
git commit -m "chore: add project dependencies and config"
```

---

## Task 2: Data Engine - yfinance Integration

**Files:**
- Create: `backend/data_engine.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_data_engine.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_data_engine.py
"""Tests for data engine."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from backend.data_engine import DataEngine


class TestDataEngine:
    """Test cases for DataEngine."""

    def test_fetch_single_stock_returns_dataframe(self):
        """Test that fetch returns a DataFrame with required columns."""
        engine = DataEngine()

        # Use a real stock for integration test
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

        df = engine.fetch_stock("INVALID.TW", period="1mo")

        assert df is None or len(df) == 0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/cengdewei/Desktop/stock-analyzer && python -m pytest backend/tests/test_data_engine.py -v`

Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Write data_engine.py implementation**

```python
# backend/data_engine.py
"""Data engine for fetching stock data from Yahoo Finance."""

import logging
from typing import Optional

import pandas as pd
import yfinance as yf

from backend.config import MA_PERIODS, FETCH_PERIOD

logger = logging.getLogger(__name__)


class DataEngine:
    """Handles stock data fetching and processing."""

    def __init__(self):
        """Initialize the data engine."""
        self._cache: dict[str, pd.DataFrame] = {}

    def fetch_stock(self, symbol: str, period: str = FETCH_PERIOD) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a single stock.

        Args:
            symbol: Stock symbol (e.g., "2330.TW")
            period: Data period (e.g., "6mo", "1y")

        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return None

            # Reset index to make Date a column
            df = df.reset_index()

            logger.info(f"Fetched {len(df)} rows for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            return None

    def calculate_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate moving averages for the given DataFrame.

        Args:
            df: DataFrame with 'Close' column

        Returns:
            DataFrame with added MA columns (ma5, ma10, ma20, ma60)
        """
        result = df.copy()

        for period in MA_PERIODS:
            col_name = f"ma{period}"
            result[col_name] = result["Close"].rolling(window=period).mean()

        return result

    def fetch_and_process(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch stock data and calculate moving averages.

        Args:
            symbol: Stock symbol

        Returns:
            Processed DataFrame with MAs, or None if fetch fails
        """
        df = self.fetch_stock(symbol)

        if df is None:
            return None

        df = self.calculate_moving_averages(df)
        self._cache[symbol] = df

        return df

    def get_cached(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get cached data for a symbol."""
        return self._cache.get(symbol)

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
```

**Step 4: Create tests/__init__.py**

```python
# backend/tests/__init__.py
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/cengdewei/Desktop/stock-analyzer && python -m pytest backend/tests/test_data_engine.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/
git commit -m "feat: add data engine with yfinance integration"
```

---

## Task 3: Screener - Strategy Logic

**Files:**
- Create: `backend/screener.py`
- Create: `backend/tests/test_screener.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_screener.py
"""Tests for stock screener."""

import pytest
import pandas as pd

from backend.screener import Screener


class TestScreener:
    """Test cases for Screener."""

    def test_check_ma_alignment_bullish(self):
        """Test detection of bullish MA alignment."""
        screener = Screener()

        # Create bullish alignment: 5MA > 10MA > 20MA > 60MA
        data = {
            "Close": [100] * 70,
            "ma5": [105],
            "ma10": [103],
            "ma20": [100],
            "ma60": [95],
        }
        df = pd.DataFrame(data)

        assert screener.check_ma_alignment(df) is True

    def test_check_ma_alignment_bearish(self):
        """Test detection of bearish MA alignment."""
        screener = Screener()

        # Create bearish alignment: 5MA < 10MA < 20MA < 60MA
        data = {
            "Close": [100] * 70,
            "ma5": [95],
            "ma10": [100],
            "ma20": [103],
            "ma60": [105],
        }
        df = pd.DataFrame(data)

        assert screener.check_ma_alignment(df) is False

    def test_calculate_risk_reward(self):
        """Test risk/reward calculation."""
        screener = Screener()

        # Create sample data
        data = {
            "Close": [100, 102, 101, 103, 105],
            "Low": [98, 100, 99, 101, 103],
            "ma20": [None, None, None, None, 100],
        }
        df = pd.DataFrame(data)
        current_price = 105

        result = screener.calculate_risk_reward(df, current_price)

        assert "stop_loss" in result
        assert "take_profit" in result
        assert "risk_reward_ratio" in result
        assert result["stop_loss"] < current_price
        assert result["take_profit"] > current_price

    def test_risk_reward_ratio_calculation(self):
        """Test that R/R ratio is calculated correctly."""
        screener = Screener()

        data = {
            "Close": [100] * 20,
            "Low": [95] * 20,
            "ma20": [None] * 19 + [90],
        }
        df = pd.DataFrame(data)
        current_price = 100

        result = screener.calculate_risk_reward(df, current_price)

        # Stop loss should be min(ma20=90, recent_low=95) = 90
        # Risk = 100 - 90 = 10
        # Take profit = 100 + (10 * 3) = 130
        # R/R = 30 / 10 = 3.0
        assert result["stop_loss"] == 90
        assert result["take_profit"] == 130
        assert result["risk_reward_ratio"] == 3.0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/cengdewei/Desktop/stock-analyzer && python -m pytest backend/tests/test_screener.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write screener.py implementation**

```python
# backend/screener.py
"""Stock screener with MA alignment and risk/reward strategies."""

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from backend.config import MIN_RISK_REWARD, STOCK_NAMES
from backend.data_engine import DataEngine

logger = logging.getLogger(__name__)


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


class Screener:
    """Stock screener with configurable strategies."""

    def __init__(self, data_engine: Optional[DataEngine] = None):
        """Initialize screener with optional data engine."""
        self.data_engine = data_engine or DataEngine()

    def check_ma_alignment(self, df: pd.DataFrame) -> bool:
        """
        Check if stock has bullish MA alignment.

        Condition: 5MA > 10MA > 20MA > 60MA

        Args:
            df: DataFrame with ma5, ma10, ma20, ma60 columns

        Returns:
            True if bullish alignment, False otherwise
        """
        if df.empty:
            return False

        latest = df.iloc[-1]

        # Check all MA values exist
        ma_cols = ["ma5", "ma10", "ma20", "ma60"]
        for col in ma_cols:
            if col not in df.columns or pd.isna(latest[col]):
                return False

        # Check bullish alignment
        return (
            latest["ma5"] > latest["ma10"] >
            latest["ma20"] > latest["ma60"]
        )

    def calculate_risk_reward(
        self,
        df: pd.DataFrame,
        current_price: float
    ) -> dict:
        """
        Calculate risk/reward ratio.

        Stop loss: min(20MA, recent 20-day low)
        Take profit: current + 3 * risk

        Args:
            df: DataFrame with price data
            current_price: Current stock price

        Returns:
            Dict with stop_loss, take_profit, risk_reward_ratio
        """
        latest = df.iloc[-1]

        # Get 20MA value
        ma20 = latest.get("ma20", current_price * 0.95)
        if pd.isna(ma20):
            ma20 = current_price * 0.95

        # Get recent 20-day low
        recent_low = df["Low"].tail(20).min()

        # Stop loss is the lower of MA20 and recent low
        stop_loss = min(ma20, recent_low)

        # Calculate risk
        risk = current_price - stop_loss

        if risk <= 0:
            # Price below stop loss, invalid setup
            return {
                "stop_loss": stop_loss,
                "take_profit": current_price,
                "risk_reward_ratio": 0,
            }

        # Take profit with 3:1 ratio
        take_profit = current_price + (risk * 3)
        risk_reward_ratio = 3.0

        return {
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "risk_reward_ratio": round(risk_reward_ratio, 2),
        }

    def screen_stock(self, symbol: str) -> Optional[ScreenResult]:
        """
        Screen a single stock.

        Args:
            symbol: Stock symbol

        Returns:
            ScreenResult if passes criteria, None otherwise
        """
        df = self.data_engine.fetch_and_process(symbol)

        if df is None or len(df) < 60:
            logger.warning(f"{symbol}: Insufficient data")
            return None

        # Check MA alignment
        if not self.check_ma_alignment(df):
            logger.debug(f"{symbol}: MA alignment not met")
            return None

        latest = df.iloc[-1]
        current_price = latest["Close"]

        # Calculate risk/reward
        rr = self.calculate_risk_reward(df, current_price)

        if rr["risk_reward_ratio"] < MIN_RISK_REWARD:
            logger.debug(f"{symbol}: R/R ratio {rr['risk_reward_ratio']} < {MIN_RISK_REWARD}")
            return None

        # Calculate change percentage
        if len(df) >= 2:
            prev_close = df.iloc[-2]["Close"]
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            change_pct = 0

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
        )

    def screen_all(self, symbols: list[str]) -> list[ScreenResult]:
        """
        Screen multiple stocks.

        Args:
            symbols: List of stock symbols

        Returns:
            List of ScreenResult for stocks passing criteria
        """
        results = []

        for symbol in symbols:
            try:
                result = self.screen_stock(symbol)
                if result:
                    results.append(result)
                    logger.info(f"{symbol}: PASSED - R/R {result.risk_reward_ratio}")
            except Exception as e:
                logger.error(f"{symbol}: Error - {e}")

        return results
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/cengdewei/Desktop/stock-analyzer && python -m pytest backend/tests/test_screener.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/
git commit -m "feat: add screener with MA alignment and R/R strategy"
```

---

## Task 4: FastAPI Backend

**Files:**
- Create: `backend/main.py`
- Create: `backend/scheduler.py`

**Step 1: Create scheduler.py**

```python
# backend/scheduler.py
"""Background scheduler for periodic data updates."""

import logging
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import MARKET_OPEN, MARKET_CLOSE, UPDATE_INTERVAL

logger = logging.getLogger(__name__)


class StockScheduler:
    """Manages scheduled stock data updates."""

    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler = BackgroundScheduler()
        self._update_callback: Optional[Callable] = None
        self._last_update: Optional[datetime] = None
        self._next_update: Optional[datetime] = None

    def is_market_open(self) -> bool:
        """Check if Taiwan market is currently open."""
        now = datetime.now().time()
        weekday = datetime.now().weekday()

        # Closed on weekends
        if weekday >= 5:
            return False

        return MARKET_OPEN <= now <= MARKET_CLOSE

    def set_update_callback(self, callback: Callable):
        """Set the callback function for updates."""
        self._update_callback = callback

    def _run_update(self):
        """Execute the update callback."""
        if self._update_callback:
            logger.info("Running scheduled update...")
            self._last_update = datetime.now()
            try:
                self._update_callback()
                logger.info("Update completed successfully")
            except Exception as e:
                logger.error(f"Update failed: {e}")

    def start(self):
        """Start the scheduler."""
        self.scheduler.add_job(
            self._run_update,
            trigger=IntervalTrigger(seconds=UPDATE_INTERVAL),
            id="stock_update",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"Scheduler started (interval: {UPDATE_INTERVAL}s)")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    @property
    def last_update(self) -> Optional[datetime]:
        """Get last update time."""
        return self._last_update

    @property
    def next_update(self) -> Optional[datetime]:
        """Get next scheduled update time."""
        job = self.scheduler.get_job("stock_update")
        if job:
            return job.next_run_time
        return None
```

**Step 2: Create main.py**

```python
# backend/main.py
"""FastAPI application for stock screener."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import TAIWAN_50, STOCK_NAMES
from backend.data_engine import DataEngine
from backend.screener import Screener, ScreenResult
from backend.scheduler import StockScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state
data_engine = DataEngine()
screener = Screener(data_engine)
scheduler = StockScheduler()
cached_results: list[ScreenResult] = []
last_update: Optional[datetime] = None


def run_screening():
    """Run the stock screening process."""
    global cached_results, last_update

    logger.info(f"Screening {len(TAIWAN_50)} stocks...")
    cached_results = screener.screen_all(TAIWAN_50)
    last_update = datetime.now()
    logger.info(f"Found {len(cached_results)} stocks matching criteria")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting stock screener...")
    run_screening()  # Initial screening
    scheduler.set_update_callback(run_screening)
    scheduler.start()

    yield

    # Shutdown
    scheduler.stop()
    logger.info("Stock screener stopped")


app = FastAPI(
    title="Taiwan Stock Screener",
    description="Real-time stock screening with MA alignment strategy",
    version="1.5.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stocks")
async def get_stocks():
    """Get screened stocks list."""
    return {
        "updated_at": last_update.isoformat() if last_update else None,
        "market_status": "open" if scheduler.is_market_open() else "closed",
        "count": len(cached_results),
        "stocks": [
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
            }
            for r in cached_results
        ],
    }


@app.get("/api/chart/{symbol}")
async def get_chart(symbol: str):
    """Get chart data for a specific stock."""
    # Ensure symbol has .TW suffix
    if not symbol.endswith(".TW"):
        symbol = f"{symbol}.TW"

    df = data_engine.get_cached(symbol)

    if df is None:
        # Try to fetch it
        df = data_engine.fetch_and_process(symbol)

    if df is None:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Convert to chart format
    candles = []
    for _, row in df.iterrows():
        if "Date" in df.columns:
            timestamp = int(row["Date"].timestamp())
        else:
            timestamp = int(row.name.timestamp())

        candles.append({
            "time": timestamp,
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
        })

    # MA lines
    ma_lines = {}
    for ma in ["ma5", "ma10", "ma20", "ma60"]:
        if ma in df.columns:
            ma_lines[ma] = [
                round(v, 2) if not pd.isna(v) else None
                for v in df[ma].tolist()
            ]

    return {
        "symbol": symbol,
        "name": STOCK_NAMES.get(symbol, symbol),
        "candles": candles,
        "ma_lines": ma_lines,
    }


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return {
        "last_update": last_update.isoformat() if last_update else None,
        "next_update": scheduler.next_update.isoformat() if scheduler.next_update else None,
        "market_status": "open" if scheduler.is_market_open() else "closed",
        "stocks_monitored": len(TAIWAN_50),
        "stocks_matched": len(cached_results),
    }


@app.get("/api/refresh")
async def refresh():
    """Manually trigger a refresh."""
    run_screening()
    return {"status": "ok", "updated_at": last_update.isoformat()}


# Need pandas for chart endpoint
import pandas as pd
```

**Step 3: Test the backend manually**

Run: `cd /Users/cengdewei/Desktop/stock-analyzer/backend && uvicorn main:app --reload --port 8000`

Expected: Server starts, initial screening runs, API accessible at http://localhost:8000

**Step 4: Commit**

```bash
git add backend/
git commit -m "feat: add FastAPI backend with scheduler"
```

---

## Task 5: Frontend - Vue.js Dashboard

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/app.js`
- Create: `frontend/style.css`

**Step 1: Create index.html**

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股即時篩選器</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div id="app">
        <!-- Header -->
        <header class="bg-gray-800 border-b border-gray-700 px-6 py-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <span class="text-2xl">📈</span>
                    <h1 class="text-xl font-bold">台股即時篩選器</h1>
                    <span :class="marketStatusClass" class="px-2 py-1 rounded text-sm">
                        {{ marketStatus === 'open' ? '開盤中' : '休市' }}
                    </span>
                </div>
                <div class="flex items-center gap-4 text-sm text-gray-400">
                    <span>更新: {{ formatTime(lastUpdate) }}</span>
                    <span>下次: {{ formatTime(nextUpdate) }}</span>
                    <button @click="refresh" class="bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded">
                        ⟳ 刷新
                    </button>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="flex h-[calc(100vh-73px)]">
            <!-- Stock List -->
            <aside class="w-80 bg-gray-800 border-r border-gray-700 overflow-y-auto">
                <div class="p-4">
                    <h2 class="text-lg font-semibold mb-3">
                        📋 符合條件 ({{ stocks.length }}檔)
                    </h2>
                    <div v-if="loading" class="text-center py-8 text-gray-400">
                        載入中...
                    </div>
                    <div v-else-if="stocks.length === 0" class="text-center py-8 text-gray-400">
                        目前無符合條件的股票
                    </div>
                    <div v-else class="space-y-2">
                        <div
                            v-for="stock in stocks"
                            :key="stock.symbol"
                            @click="selectStock(stock)"
                            :class="{ 'ring-2 ring-blue-500': selectedStock?.symbol === stock.symbol }"
                            class="bg-gray-700 rounded-lg p-3 cursor-pointer hover:bg-gray-600 transition"
                        >
                            <div class="flex justify-between items-start">
                                <div>
                                    <span class="font-mono text-sm text-gray-400">{{ stock.symbol.replace('.TW', '') }}</span>
                                    <span class="ml-2 font-medium">{{ stock.name }}</span>
                                </div>
                                <span :class="stock.change_pct >= 0 ? 'text-red-400' : 'text-green-400'">
                                    {{ stock.change_pct >= 0 ? '▲' : '▼' }}{{ Math.abs(stock.change_pct).toFixed(2) }}%
                                </span>
                            </div>
                            <div class="flex justify-between mt-2">
                                <span class="text-lg font-bold">${{ stock.price }}</span>
                                <span class="text-sm text-yellow-400">R/R: {{ stock.risk_reward.toFixed(1) }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </aside>

            <!-- Chart Area -->
            <section class="flex-1 flex flex-col">
                <!-- Chart -->
                <div class="flex-1 p-4">
                    <div v-if="!selectedStock" class="h-full flex items-center justify-center text-gray-500">
                        ← 點選左側股票查看 K 線圖
                    </div>
                    <div v-else class="h-full">
                        <h3 class="text-lg font-semibold mb-2">
                            {{ selectedStock.symbol.replace('.TW', '') }} {{ selectedStock.name }}
                        </h3>
                        <div id="chart" class="h-[calc(100%-2rem)] bg-gray-800 rounded-lg"></div>
                    </div>
                </div>

                <!-- Trade Info -->
                <div v-if="selectedStock" class="bg-gray-800 border-t border-gray-700 p-4">
                    <h3 class="text-lg font-semibold mb-3">📊 交易建議</h3>
                    <div class="grid grid-cols-4 gap-4">
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-sm text-gray-400">現價</div>
                            <div class="text-xl font-bold">${{ selectedStock.price }}</div>
                        </div>
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-sm text-gray-400">停損</div>
                            <div class="text-xl font-bold text-red-400">${{ selectedStock.stop_loss }}</div>
                        </div>
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-sm text-gray-400">停利</div>
                            <div class="text-xl font-bold text-green-400">${{ selectedStock.take_profit }}</div>
                        </div>
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-sm text-gray-400">損益比</div>
                            <div class="text-xl font-bold text-yellow-400">{{ selectedStock.risk_reward.toFixed(1) }}:1</div>
                        </div>
                    </div>
                    <div class="mt-3 grid grid-cols-4 gap-4 text-sm">
                        <div class="text-center">
                            <span class="text-gray-400">5MA:</span>
                            <span class="ml-1">{{ selectedStock.ma5 }}</span>
                        </div>
                        <div class="text-center">
                            <span class="text-gray-400">10MA:</span>
                            <span class="ml-1">{{ selectedStock.ma10 }}</span>
                        </div>
                        <div class="text-center">
                            <span class="text-gray-400">20MA:</span>
                            <span class="ml-1">{{ selectedStock.ma20 }}</span>
                        </div>
                        <div class="text-center">
                            <span class="text-gray-400">60MA:</span>
                            <span class="ml-1">{{ selectedStock.ma60 }}</span>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <script src="app.js"></script>
</body>
</html>
```

**Step 2: Create app.js**

```javascript
// frontend/app.js
const API_BASE = 'http://localhost:8000';

const { createApp, ref, computed, onMounted, onUnmounted, watch } = Vue;

createApp({
    setup() {
        // State
        const stocks = ref([]);
        const selectedStock = ref(null);
        const loading = ref(true);
        const lastUpdate = ref(null);
        const nextUpdate = ref(null);
        const marketStatus = ref('closed');

        let chart = null;
        let candleSeries = null;
        let maLines = {};
        let refreshInterval = null;

        // Computed
        const marketStatusClass = computed(() => {
            return marketStatus.value === 'open'
                ? 'bg-green-600'
                : 'bg-gray-600';
        });

        // Methods
        const formatTime = (isoString) => {
            if (!isoString) return '--:--';
            const date = new Date(isoString);
            return date.toLocaleTimeString('zh-TW', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        };

        const fetchStocks = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/stocks`);
                const data = await res.json();

                stocks.value = data.stocks;
                lastUpdate.value = data.updated_at;
                marketStatus.value = data.market_status;
            } catch (err) {
                console.error('Failed to fetch stocks:', err);
            } finally {
                loading.value = false;
            }
        };

        const fetchStatus = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/status`);
                const data = await res.json();
                nextUpdate.value = data.next_update;
            } catch (err) {
                console.error('Failed to fetch status:', err);
            }
        };

        const refresh = async () => {
            loading.value = true;
            try {
                await fetch(`${API_BASE}/api/refresh`);
                await fetchStocks();
                await fetchStatus();
            } catch (err) {
                console.error('Failed to refresh:', err);
            } finally {
                loading.value = false;
            }
        };

        const selectStock = async (stock) => {
            selectedStock.value = stock;
            await loadChart(stock.symbol);
        };

        const loadChart = async (symbol) => {
            try {
                const res = await fetch(`${API_BASE}/api/chart/${symbol}`);
                const data = await res.json();

                renderChart(data);
            } catch (err) {
                console.error('Failed to load chart:', err);
            }
        };

        const renderChart = (data) => {
            const container = document.getElementById('chart');
            if (!container) return;

            // Clear existing chart
            container.innerHTML = '';

            // Create new chart
            chart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {
                    background: { color: '#1f2937' },
                    textColor: '#9ca3af',
                },
                grid: {
                    vertLines: { color: '#374151' },
                    horzLines: { color: '#374151' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: '#374151',
                },
                timeScale: {
                    borderColor: '#374151',
                    timeVisible: true,
                },
            });

            // Add candlestick series
            candleSeries = chart.addCandlestickSeries({
                upColor: '#ef4444',
                downColor: '#22c55e',
                borderUpColor: '#ef4444',
                borderDownColor: '#22c55e',
                wickUpColor: '#ef4444',
                wickDownColor: '#22c55e',
            });

            candleSeries.setData(data.candles);

            // Add MA lines
            const maColors = {
                ma5: '#fbbf24',
                ma10: '#60a5fa',
                ma20: '#a78bfa',
                ma60: '#f472b6',
            };

            Object.keys(maColors).forEach(maKey => {
                if (data.ma_lines[maKey]) {
                    const lineSeries = chart.addLineSeries({
                        color: maColors[maKey],
                        lineWidth: 1,
                    });

                    const maData = data.candles.map((candle, i) => ({
                        time: candle.time,
                        value: data.ma_lines[maKey][i],
                    })).filter(d => d.value !== null);

                    lineSeries.setData(maData);
                    maLines[maKey] = lineSeries;
                }
            });

            chart.timeScale().fitContent();
        };

        // Handle resize
        const handleResize = () => {
            if (chart) {
                const container = document.getElementById('chart');
                if (container) {
                    chart.applyOptions({
                        width: container.clientWidth,
                        height: container.clientHeight,
                    });
                }
            }
        };

        // Lifecycle
        onMounted(async () => {
            await fetchStocks();
            await fetchStatus();

            // Auto refresh every 5 minutes
            refreshInterval = setInterval(async () => {
                await fetchStocks();
                await fetchStatus();
            }, 300000);

            window.addEventListener('resize', handleResize);
        });

        onUnmounted(() => {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
            window.removeEventListener('resize', handleResize);
        });

        return {
            stocks,
            selectedStock,
            loading,
            lastUpdate,
            nextUpdate,
            marketStatus,
            marketStatusClass,
            formatTime,
            refresh,
            selectStock,
        };
    },
}).mount('#app');
```

**Step 3: Create style.css**

```css
/* frontend/style.css */

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: #1f2937;
}

::-webkit-scrollbar-thumb {
    background: #4b5563;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #6b7280;
}

/* Stock card hover effect */
.stock-card {
    transition: transform 0.2s, box-shadow 0.2s;
}

.stock-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

/* Loading animation */
@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.5;
    }
}

.loading {
    animation: pulse 2s infinite;
}
```

**Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: add Vue.js frontend dashboard"
```

---

## Task 6: README and Final Setup

**Files:**
- Create: `README.md`
- Create: `data/.gitkeep`

**Step 1: Create README.md**

```markdown
# 台股即時篩選器 (Stock Screener)

> Stage 1.5: Real-Time Data Engine

即時抓取台灣 50 成分股數據，運用均線多頭排列策略篩選潛力股票。

## 功能特色

- 📊 **即時數據**: 使用 yfinance API 抓取 Yahoo Finance 台股數據
- 📈 **策略篩選**: 4 線均線多頭排列 (5MA > 10MA > 20MA > 60MA)
- 💰 **風控計算**: 自動計算 3:1 損益比的停損停利價位
- 🖥️ **視覺化介面**: Vue.js 儀表板 + K 線圖表
- ⏰ **自動更新**: 盤中每 5 分鐘自動刷新數據

## 快速開始

### 1. 安裝後端依賴

```bash
cd backend
pip install -r requirements.txt
```

### 2. 啟動後端服務

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 3. 開啟前端介面

用瀏覽器開啟 `frontend/index.html`，或使用 Live Server。

## API 端點

| 端點 | 說明 |
|------|------|
| `GET /api/stocks` | 取得篩選結果清單 |
| `GET /api/chart/{symbol}` | 取得 K 線圖數據 |
| `GET /api/status` | 取得系統狀態 |
| `GET /api/refresh` | 手動觸發刷新 |

## 篩選條件

1. **均線多頭排列**: 5MA > 10MA > 20MA > 60MA
2. **損益比**: >= 3:1
3. **數據範圍**: 台灣 50 成分股

## 技術架構

```
Frontend (Vue 3 + Tailwind + Lightweight Charts)
    ↓ HTTP API
Backend (FastAPI + APScheduler)
    ↓ yfinance
Yahoo Finance API
```

## 開發

```bash
# 執行測試
cd backend
python -m pytest tests/ -v

# 查看 API 文件
open http://localhost:8000/docs
```

## License

MIT
```

**Step 2: Create data directory**

```bash
mkdir -p data
touch data/.gitkeep
```

**Step 3: Final commit**

```bash
git add .
git commit -m "docs: add README and project setup"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project Setup | requirements.txt, config.py |
| 2 | Data Engine | data_engine.py, tests |
| 3 | Screener | screener.py, tests |
| 4 | FastAPI Backend | main.py, scheduler.py |
| 5 | Vue.js Frontend | index.html, app.js, style.css |
| 6 | Documentation | README.md |

**Total estimated commits:** 6

# backend/main.py
"""FastAPI application for stock screener."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import TAIWAN_50, STOCK_NAMES, TOP_TRADING_VALUE_COUNT

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
from backend.data_engine import DataEngine
from backend.screener import Screener, ScreenResult
from backend.scheduler import StockScheduler
from backend.twse_fetcher import fetch_top_trading_value_stocks

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting stock screener...")
    # Don't run screening on startup - let scheduler handle it
    # This allows the app to start quickly for health checks
    scheduler.set_update_callback(run_screening)
    scheduler.start()

    # Schedule first screening after 5 seconds (non-blocking)
    import threading
    def delayed_first_run():
        import time
        time.sleep(5)
        run_screening()
    threading.Thread(target=delayed_first_run, daemon=True).start()

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
                "volume": r.volume,
                "avg_volume": r.avg_volume,
                "volume_ratio": r.volume_ratio,
                "slope_5ma": r.slope_5ma,
                "slope_10ma": r.slope_10ma,
                "slope_20ma": r.slope_20ma,
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


# Serve frontend static files
@app.get("/")
async def serve_index():
    """Serve the frontend index.html."""
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# backend/main.py
"""FastAPI application for stock screener."""

import hashlib
import hmac
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Header
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
from backend.twse_sector_fetcher import fetch_top_trading_value_stocks
from backend.line_notifier import LineNotifier

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
previous_symbols: set[str] = set()

# Multi-user state
# linking_codes: code -> {created_at, user_token}
linking_codes: dict[str, dict] = {}
# user_profiles: user_token -> {line_user_id, linked_at}
user_profiles: dict[str, dict] = {}
# user_watchlists: user_token -> {symbol -> {alert_enabled, ...}}
user_watchlists: dict[str, dict] = {}

# LINE Channel Secret for webhook signature verification
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")


def send_alert_to_user(user_token: str, stock_dict: dict):
    """Send stock alert to a specific user."""
    profile = user_profiles.get(user_token)
    if not profile or not profile.get("line_user_id"):
        return False

    notifier = LineNotifier(user_id=profile["line_user_id"])
    return notifier.send_stock_alert(stock_dict)


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

    # Check for new matches and send LINE alerts to users
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

            # Send to all users who have this stock in watchlist with alerts enabled
            for user_token, watchlist in user_watchlists.items():
                if result.symbol in watchlist:
                    item = watchlist[result.symbol]
                    if item.get("alert_enabled", False):
                        if send_alert_to_user(user_token, stock_dict):
                            logger.info(f"Sent alert for {result.symbol} to user {user_token[:8]}...")

    previous_symbols = current_symbols


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


# ============ User & LINE Linking Endpoints ============

@app.post("/api/user/register")
async def register_user():
    """Register a new user and get a user token."""
    user_token = secrets.token_urlsafe(32)
    user_watchlists[user_token] = {}
    return {"user_token": user_token}


@app.get("/api/user/link-code")
async def get_link_code(user_token: str = Header(alias="X-User-Token")):
    """Generate a linking code for LINE account binding."""
    if not user_token:
        raise HTTPException(status_code=401, detail="User token required")

    # Generate 6-digit code
    code = f"{secrets.randbelow(1000000):06d}"
    linking_codes[code] = {
        "user_token": user_token,
        "created_at": datetime.now(),
    }

    return {"code": code, "expires_in": 300}  # 5 minutes


@app.get("/api/user/profile")
async def get_user_profile(user_token: str = Header(alias="X-User-Token")):
    """Get user profile including LINE linking status."""
    if not user_token:
        raise HTTPException(status_code=401, detail="User token required")

    profile = user_profiles.get(user_token, {})
    return {
        "linked": bool(profile.get("line_user_id")),
        "linked_at": profile.get("linked_at"),
    }


@app.post("/webhook/line")
async def line_webhook(request: Request):
    """LINE webhook endpoint for receiving messages."""
    body = await request.body()

    # Verify signature if channel secret is set
    if LINE_CHANNEL_SECRET:
        signature = request.headers.get("X-Line-Signature", "")
        hash_value = hmac.new(
            LINE_CHANNEL_SECRET.encode(),
            body,
            hashlib.sha256
        ).digest()
        import base64
        expected_signature = base64.b64encode(hash_value).decode()

        if signature != expected_signature:
            logger.warning("Invalid LINE webhook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse events
    import json
    data = json.loads(body)

    for event in data.get("events", []):
        if event.get("type") == "message":
            user_id = event.get("source", {}).get("userId")
            message = event.get("message", {})

            if message.get("type") == "text":
                text = message.get("text", "").strip()

                # Check if it's a linking code (6 digits)
                if text.isdigit() and len(text) == 6:
                    code_data = linking_codes.get(text)

                    if code_data:
                        user_token = code_data["user_token"]

                        # Check if code is expired (5 minutes)
                        age = (datetime.now() - code_data["created_at"]).seconds
                        if age < 300:
                            # Link the account
                            user_profiles[user_token] = {
                                "line_user_id": user_id,
                                "linked_at": datetime.now().isoformat(),
                            }

                            # Initialize watchlist if not exists
                            if user_token not in user_watchlists:
                                user_watchlists[user_token] = {}

                            # Remove used code
                            del linking_codes[text]

                            # Reply to user
                            notifier = LineNotifier(user_id=user_id)
                            notifier.send("✅ LINE 帳號綁定成功！\n您現在可以接收自選股通知了。")

                            logger.info(f"Linked LINE user {user_id} to token {user_token[:8]}...")
                        else:
                            # Code expired
                            notifier = LineNotifier(user_id=user_id)
                            notifier.send("❌ 驗證碼已過期，請重新取得驗證碼。")
                    else:
                        # Invalid code
                        notifier = LineNotifier(user_id=user_id)
                        notifier.send("❌ 驗證碼無效，請確認後重新輸入。")

    return {"status": "ok"}


# ============ User Watchlist Endpoints ============

@app.get("/api/watchlist")
async def get_watchlist(user_token: str = Header(None, alias="X-User-Token")):
    """Get user's watchlist."""
    if not user_token or user_token not in user_watchlists:
        return {"watchlist": []}

    watchlist = user_watchlists[user_token]
    return {"watchlist": list(watchlist.values())}


@app.post("/api/watchlist/{symbol}")
async def add_to_watchlist(
    symbol: str,
    alert_enabled: bool = True,
    user_token: str = Header(None, alias="X-User-Token")
):
    """Add a stock to user's watchlist."""
    if not user_token:
        raise HTTPException(status_code=401, detail="User token required")

    if user_token not in user_watchlists:
        user_watchlists[user_token] = {}

    if not symbol.endswith(".TW"):
        symbol = f"{symbol}.TW"

    user_watchlists[user_token][symbol] = {
        "symbol": symbol,
        "name": STOCK_NAMES.get(symbol, symbol),
        "alert_enabled": alert_enabled,
    }
    return {"status": "ok", "item": user_watchlists[user_token][symbol]}


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    user_token: str = Header(None, alias="X-User-Token")
):
    """Remove a stock from user's watchlist."""
    if not user_token or user_token not in user_watchlists:
        raise HTTPException(status_code=401, detail="User token required")

    if not symbol.endswith(".TW"):
        symbol = f"{symbol}.TW"

    watchlist = user_watchlists[user_token]
    if symbol in watchlist:
        del watchlist[symbol]
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Stock not in watchlist")


@app.patch("/api/watchlist/{symbol}/alert")
async def toggle_watchlist_alert(
    symbol: str,
    enabled: bool,
    user_token: str = Header(None, alias="X-User-Token")
):
    """Toggle alert for a watchlist item."""
    if not user_token or user_token not in user_watchlists:
        raise HTTPException(status_code=401, detail="User token required")

    if not symbol.endswith(".TW"):
        symbol = f"{symbol}.TW"

    watchlist = user_watchlists[user_token]
    if symbol not in watchlist:
        raise HTTPException(status_code=404, detail="Stock not in watchlist")

    watchlist[symbol]["alert_enabled"] = enabled
    return {"status": "ok", "item": watchlist[symbol]}


# Serve frontend static files
@app.get("/")
async def serve_index():
    """Serve the frontend index.html."""
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

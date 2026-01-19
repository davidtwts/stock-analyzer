# TWSE Data Engine Design

**Date:** 2026-01-19
**Status:** Approved
**Purpose:** Replace yfinance with TWSE API to avoid rate limiting bans

## Background

Yahoo Finance blocked the application due to excessive requests (50+ stocks every 5 minutes). TWSE official API provides:
- Real-time quotes (no 15-min delay)
- Official data source (less likely to be banned)
- Batch query support

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Historical data storage | SQLite | Offline MA calculation, minimize API calls |
| History initialization | Auto-fetch on first access | Simple, no manual setup needed |
| Batch size | 10 stocks per request | Conservative, avoids rate limits |
| Update frequency | 5 minutes | Maintain current real-time capability |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Stock Screener                        │
├─────────────────────────────────────────────────────────┤
│  TWSEDataEngine (new)                                    │
│  ├── HistoryStore (SQLite)    ← Store OHLCV history     │
│  ├── RealtimeFetcher          ← Batch real-time quotes  │
│  └── RateLimiter              ← Enforce 3 req/5 sec     │
├─────────────────────────────────────────────────────────┤
│  Existing modules (unchanged interface)                  │
│  ├── Screener                 ← MA calculation + filter │
│  ├── Scheduler                ← 5-min trigger           │
│  └── LineNotifier             ← Notifications           │
└─────────────────────────────────────────────────────────┘
```

## Database Schema

**File:** `data/stock_history.db`

```sql
-- Daily OHLCV data
CREATE TABLE daily_prices (
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,      -- YYYY-MM-DD
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    PRIMARY KEY (symbol, date)
);

-- Sync tracking
CREATE TABLE sync_status (
    symbol      TEXT PRIMARY KEY,
    last_sync   TEXT NOT NULL,
    months_loaded INTEGER DEFAULT 0
);

CREATE INDEX idx_symbol_date ON daily_prices(symbol, date DESC);
```

## Rate Limiter

TWSE enforces 3 requests per 5 seconds.

```python
class RateLimiter:
    def __init__(self, max_requests=3, period=5.0):
        self.max_requests = max_requests
        self.period = period
        self.timestamps = []

    def acquire(self):
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < self.period]

        if len(self.timestamps) >= self.max_requests:
            sleep_time = self.period - (now - self.timestamps[0])
            time.sleep(sleep_time)

        self.timestamps.append(time.time())
```

## Real-time Quote Fetching

Batch query up to 10 stocks per request:

```python
def fetch_realtime_batch(symbols: list[str]) -> dict:
    results = {}
    batches = [symbols[i:i+10] for i in range(0, len(symbols), 10)]

    for batch in batches:
        rate_limiter.acquire()
        ex_ch = "|".join(f"tse_{s}.tw" for s in batch)
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}"

        response = requests.get(url, timeout=10)
        data = response.json()

        for item in data.get("msgArray", []):
            results[item["c"]] = {
                "price": float(item["z"]) if item["z"] != "-" else None,
                "volume": int(item["v"]),
                "open": float(item["o"]) if item["o"] != "-" else None,
                "high": float(item["h"]) if item["h"] != "-" else None,
                "low": float(item["l"]) if item["l"] != "-" else None,
            }

    return results
```

## History Fetching

Auto-fetch 3 months of history when needed:

```python
def ensure_history(self, symbol: str, min_days: int = 60) -> bool:
    existing_days = self.store.count_days(symbol)

    if existing_days >= min_days:
        return True

    months_needed = 3

    for i in range(months_needed):
        self.rate_limiter.acquire()
        target_date = datetime.now() - timedelta(days=30 * i)
        date_str = target_date.strftime("%Y%m01")

        url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
        params = {"response": "json", "date": date_str, "stockNo": symbol}

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("stat") == "OK":
            self._parse_and_store(symbol, data["data"])

    return True
```

## Error Handling

| Error Type | Handling |
|------------|----------|
| Network timeout | Retry 2x with 5s interval |
| Empty TWSE response | Mark ticker as quarantine |
| Rate limit triggered | Auto-wait and retry |
| SQLite write failure | Log error, continue |

## Files to Create

- `backend/twse_data_engine.py` - Main engine class
- `backend/history_store.py` - SQLite operations
- `backend/rate_limiter.py` - Request throttling

## Files to Modify

- `backend/main.py` - Use TWSEDataEngine instead of DataEngine
- `backend/requirements.txt` - Optional: keep yfinance as fallback

## Migration Notes

1. TWSEDataEngine maintains same interface as DataEngine
2. `fetch_and_process(symbol)` returns same DataFrame format
3. Existing Screener code requires no changes
4. First run will be slower (fetching 3 months history per stock)

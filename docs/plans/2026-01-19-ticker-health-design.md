# Ticker Health: Self-Healing Data Fetching

**Date:** 2026-01-19
**Status:** Approved

## Problem

Deployed stock screener logs show repeated failures for ETF tickers (00xxx.TW format). yfinance cannot reliably fetch data for Taiwan ETFs, causing noise in logs and wasted API calls.

**Failing tickers (all ETFs):**
- 00646, 00652, 00657, 00660, 00661, 00662
- 00894-00905, 00907

## Solution

Two-layer approach:

1. **ETF Filter (Primary)** - Filter out 5-digit ETF codes at fetch time
2. **Quarantine System (Safety Net)** - Auto-quarantine any future failing tickers

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Quarantine trigger | 2 consecutive failures | Moderate - avoids false positives from transient errors |
| Retry schedule | Weekly during market hours | Smart recovery - some tickers fail outside trading hours |
| Storage | SQLite | Supports queries, history tracking, survives restarts |
| Notifications | Logging only | Simple, check logs if needed |
| ETF handling | Filter out entirely | Root cause of all current failures |

## Data Model

**SQLite Database:** `data/ticker_health.db`

```sql
CREATE TABLE ticker_status (
    symbol TEXT PRIMARY KEY,
    status TEXT DEFAULT 'active',        -- 'active', 'quarantined'
    consecutive_failures INTEGER DEFAULT 0,
    last_failure_at TIMESTAMP,
    last_success_at TIMESTAMP,
    quarantined_at TIMESTAMP,
    next_retry_at TIMESTAMP,
    failure_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE failure_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    error_message TEXT,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Status Flow:**
```
active → (2 failures) → quarantined → (weekly retry) → active/quarantined
```

## Module Interface

**New file:** `backend/ticker_health.py`

```python
class TickerHealth:
    def __init__(self, db_path: str = "data/ticker_health.db")

    def record_failure(self, symbol: str, reason: str) -> None
    def record_success(self, symbol: str) -> None
    def is_quarantined(self, symbol: str) -> bool
    def get_active_symbols(self, symbols: list[str]) -> list[str]
    def get_retry_candidates(self) -> list[str]
    def get_status_summary(self) -> dict
```

## Integration Points

### 1. ETF Filter (`twse_sector_fetcher.py`)

```python
# Line 79 - reject ETFs (5-digit codes starting with 00)
if symbol.isdigit() and not symbol.startswith("00"):
    stocks.append(f"{symbol}.TW")
```

### 2. DataEngine (`data_engine.py`)

```python
from backend.ticker_health import TickerHealth

class DataEngine:
    def __init__(self):
        self._cache: dict[str, pd.DataFrame] = {}
        self._health = TickerHealth()

    def fetch_stock(self, symbol: str, period: str = FETCH_PERIOD):
        # ... existing fetch logic ...

        if df.empty:
            self._health.record_failure(symbol, "No data returned")
            return None

        self._health.record_success(symbol)
        return df
```

### 3. Screener (`screener.py`)

```python
def screen_all(self, symbols: list[str]) -> list[dict]:
    active_symbols = self.data_engine._health.get_active_symbols(symbols)
    logger.info(f"Screening {len(active_symbols)} active "
                f"(skipped {len(symbols) - len(active_symbols)} quarantined)")
    # ... rest uses active_symbols ...
```

### 4. Scheduler (`scheduler.py`)

```python
def _run_weekly_retry(self):
    if not self.is_market_open():
        return

    candidates = self.data_engine._health.get_retry_candidates()
    for symbol in candidates:
        self.data_engine.fetch_and_process(symbol)
```

## Failure Classification

```python
FAILURE_REASONS = {
    "no_data": "No data returned from yfinance",
    "json_parse": "Invalid JSON response",
    "timeout": "Request timeout",
    "delisted": "Symbol may be delisted",
    "unknown": "Unknown error",
}
```

## Logging Format

```
# On failure (count 1):
INFO - 00652.TW: Fetch failed (1/2) - json_parse

# On quarantine:
WARNING - 00652.TW: Quarantined after 2 failures. Next retry: 2026-01-26

# On screening run:
INFO - Ticker health: 145 active, 3 quarantined, 19 filtered (ETF)

# On recovery:
INFO - 00652.TW: Recovered from quarantine
```

## File Changes

| File | Change |
|------|--------|
| `backend/ticker_health.py` | NEW (~120 lines) |
| `backend/tests/test_ticker_health.py` | NEW (~80 lines) |
| `backend/twse_sector_fetcher.py` | Add ETF filter (1 line) |
| `backend/data_engine.py` | Add health tracking (~10 lines) |
| `backend/screener.py` | Filter quarantined (~5 lines) |
| `backend/scheduler.py` | Add weekly retry job (~15 lines) |
| `data/ticker_health.db` | NEW (auto-created) |

## Test Cases

- `test_record_failure_increments_count`
- `test_quarantine_after_two_failures`
- `test_success_resets_failure_count`
- `test_get_active_symbols_filters_quarantined`
- `test_retry_candidates_respects_weekly_interval`
- `test_retry_during_market_hours_only`
- `test_recovery_after_successful_retry`

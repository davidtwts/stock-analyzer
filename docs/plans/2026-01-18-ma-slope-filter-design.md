# MA Slope Filter Design

## Overview

Add dynamic MA slope filtering to the stock screener. Users can adjust slope thresholds via frontend sliders to find stocks with stronger upward momentum.

## What It Does

Measures the slope (% change per day) of 5MA, 10MA, and 20MA. Stocks must have all three MAs rising at or above user-defined thresholds to appear in results.

## Calculation

Slope is calculated as percentage change per day over a lookback period matching the MA:

```
slope = (current_ma - ma_from_N_days_ago) / ma_from_N_days_ago / N * 100
```

| MA   | Lookback | Example                                      |
|------|----------|----------------------------------------------|
| 5MA  | 5 days   | (102.5 - 100) / 100 / 5 × 100 = 0.5% per day |
| 10MA | 10 days  | Same formula with 10-day lookback            |
| 20MA | 20 days  | Same formula with 20-day lookback            |

## API Response

New fields added to each stock object:

```json
{
  "symbol": "2330.TW",
  "price": 580.0,
  "ma5": 575.0,
  "ma10": 570.0,
  "ma20": 560.0,
  "slope_5ma": 0.52,
  "slope_10ma": 0.31,
  "slope_20ma": 0.18
}
```

Backend returns all MA-aligned stocks with slope data. No server-side slope filtering.

## Frontend UI

Collapsible filter panel at top of sidebar:

```
┌─────────────────────────────────┐
│ 🎚️ 斜率篩選                  ▼ │
├─────────────────────────────────┤
│ 5MA 斜率   ≥ [====●====] 0.5%  │
│ 10MA 斜率  ≥ [===●=====] 0.3%  │
│ 20MA 斜率  ≥ [==●======] 0.15% │
│                                 │
│ [重置預設]                      │
└─────────────────────────────────┘
```

### Slider Configuration

| MA    | Range       | Step  | Default |
|-------|-------------|-------|---------|
| 5MA   | 0% - 1.5%   | 0.05% | 0.5%    |
| 10MA  | 0% - 1.0%   | 0.05% | 0.3%    |
| 20MA  | 0% - 0.5%   | 0.05% | 0.15%   |

### Behavior

- Client-side filtering for instant response
- Stock count updates as sliders move
- "重置預設" button restores defaults

## Data Flow

```
Backend (screener.py)
  │
  ├─ Fetch stock data
  ├─ Calculate MAs (existing)
  ├─ Calculate MA slopes (NEW)
  ├─ Check MA alignment (existing)
  └─ Return all aligned stocks with slope data
          │
          ▼
Frontend (app.js)
  │
  ├─ Store raw stocks in allStocks
  ├─ Store slider values in slopeFilters
  ├─ Computed filteredStocks applies thresholds
  └─ Display filtered list
```

## Files to Modify

| File                    | Changes                              |
|-------------------------|--------------------------------------|
| `backend/screener.py`   | Add `calculate_ma_slopes()` method   |
| `backend/main.py`       | Include slope fields in API response |
| `frontend/index.html`   | Add slider panel HTML                |
| `frontend/app.js`       | Add filter state & computed property |

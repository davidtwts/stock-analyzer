# Stock Screener Enhancement Design

## Overview

Enhance the stock screener with:
1. MA slope filtering with dynamic thresholds
2. Optional R/R filter toggle
3. Expanded stock universe (sector-based)
4. LINE alerts for new matches
5. Watchlist with volume spike alerts

---

## Feature 1: MA Slope Filter

### What It Does

Measures the slope (% change per day) of 5MA, 10MA, and 20MA. Users can adjust thresholds via frontend sliders to find stocks with stronger upward momentum.

### Calculation

```
slope = (current_ma - ma_from_N_days_ago) / ma_from_N_days_ago / N * 100
```

| MA   | Lookback | Example                                      |
|------|----------|----------------------------------------------|
| 5MA  | 5 days   | (102.5 - 100) / 100 / 5 × 100 = 0.5% per day |
| 10MA | 10 days  | Same formula with 10-day lookback            |
| 20MA | 20 days  | Same formula with 20-day lookback            |

### API Response

New fields added to each stock object:

```json
{
  "symbol": "2330.TW",
  "slope_5ma": 0.52,
  "slope_10ma": 0.31,
  "slope_20ma": 0.18
}
```

### Frontend UI

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

| MA    | Range       | Step  | Default |
|-------|-------------|-------|---------|
| 5MA   | 0% - 1.5%   | 0.05% | 0.5%    |
| 10MA  | 0% - 1.0%   | 0.05% | 0.3%    |
| 20MA  | 0% - 0.5%   | 0.05% | 0.15%   |

Client-side filtering for instant response.

---

## Feature 2: Optional R/R Filter

### What It Does

Toggle to enable/disable the 3:1 risk/reward minimum requirement.

### Frontend UI

Checkbox in filter panel:
```
☑️ 僅顯示損益比 ≥ 3:1
```

- Default: enabled (current behavior)
- When disabled: show all MA-aligned stocks regardless of R/R

Backend returns all MA-aligned stocks. Frontend filters client-side.

---

## Feature 3: Sector Expansion

### What It Does

Expand stock universe from Taiwan 50 to include multiple sectors.

### Sectors Included

| Sector | Chinese |
|--------|---------|
| Semiconductors | 半導體 |
| Financials | 金融 |
| Electronic Components | 電子零組件 |
| Traditional Industries | 傳產 |

### Implementation

- Source: Fetch from TWSE website
- Update frequency: Weekly
- Cache: Local JSON file with timestamp
- On startup: use cache if < 7 days old, else refresh
- Estimated stocks: ~200-300

### Files

- Add `twse_sector_fetcher.py` - scrapes TWSE for sector stock lists
- Config maps sector names to TWSE sector codes

No sector filter UI - just expanded stock pool.

---

## Feature 4: LINE Alerts (New Matches)

### What It Does

Send LINE notification when a stock newly matches all screening criteria.

### Trigger

Stock appears in results that wasn't in previous scan.

### Message Format

```
📈 新符合條件股票

2330 台積電
價格: $580 (▲1.25%)
斜率: 5MA 0.52% | 10MA 0.31% | 20MA 0.18%
損益比: 3.2:1
量比: 1.8x
```

### Implementation

1. Add `line_notifier.py` - sends via LINE Notify API
2. Store previous scan results in memory
3. Compare current vs previous - find new matches
4. Send alert for each new match
5. LINE token stored in environment variable (`LINE_NOTIFY_TOKEN`)

### User Setup

1. Get token from https://notify-bot.line.me/
2. Set `LINE_NOTIFY_TOKEN` in Railway environment

---

## Feature 5: Watchlist Volume Spike Alerts

### What It Does

Monitor user's watchlist for sudden volume spikes and send LINE alerts.

### Configuration

| Aspect | Setting |
|--------|---------|
| Watchlist | User-managed via frontend UI |
| Alert toggle | Per-stock on/off for LINE notifications |
| Trigger | 5-min volume > 3x stock's average 5-min volume |
| Threshold | Auto-calculated per stock |

### Frontend UI

```
┌─────────────────────────────────────────────┐
│ ⭐ 自選股監控                             ▼ │
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │ 2330 台積電    [🔔 ON]  [✕ 移除]       │ │
│ │ 2317 鴻海      [🔕 OFF] [✕ 移除]       │ │
│ │ 2454 聯發科    [🔔 ON]  [✕ 移除]       │ │
│ └─────────────────────────────────────────┘ │
│ [+ 新增股票]                                │
└─────────────────────────────────────────────┘
```

### LINE Message

```
⚡ 成交量異常

2330 台積電
5分鐘成交量: 850張 (3.2x 平均)
現價: $580 (▲1.25%)
```

### Implementation

1. Watchlist stored in localStorage + optional backend sync
2. Backend monitors 5-min volume for watchlist stocks
3. Calculate rolling average of 5-min volume per stock
4. Alert if current 5-min volume > 3x average
5. Only send LINE if stock has alert enabled

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────┐
│ Backend                                                 │
│                                                         │
│ ┌─────────────────┐  ┌─────────────────┐               │
│ │ TWSE Fetcher    │  │ Screener        │               │
│ │ (weekly update) │  │ (5-min cycle)   │               │
│ └────────┬────────┘  └────────┬────────┘               │
│          │                    │                         │
│          └──────────┬─────────┘                         │
│                     ▼                                   │
│          ┌─────────────────┐                           │
│          │ LINE Notifier   │                           │
│          │ - New matches   │                           │
│          │ - Volume spikes │                           │
│          └─────────────────┘                           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Frontend                                                │
│                                                         │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│ │ Slope       │ │ R/R Toggle  │ │ Watchlist   │        │
│ │ Sliders     │ │             │ │ Manager     │        │
│ └─────────────┘ └─────────────┘ └─────────────┘        │
│         │              │              │                 │
│         └──────────────┴──────────────┘                 │
│                        │                                │
│                        ▼                                │
│              ┌─────────────────┐                        │
│              │ Filtered Stock  │                        │
│              │ List + Charts   │                        │
│              └─────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

---

## Files to Modify/Create

| File | Changes |
|------|---------|
| `backend/screener.py` | Add `calculate_ma_slopes()` method |
| `backend/main.py` | Include slope fields, remove R/R server filter |
| `backend/twse_sector_fetcher.py` | NEW: Fetch sector stock lists |
| `backend/line_notifier.py` | NEW: LINE Notify integration |
| `backend/volume_monitor.py` | NEW: 5-min volume spike detection |
| `backend/config.py` | Add sector codes, LINE settings |
| `frontend/index.html` | Add slider panel, watchlist UI |
| `frontend/app.js` | Add filter state, watchlist logic |

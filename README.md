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

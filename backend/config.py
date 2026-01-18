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

# Volume filters
MIN_AVG_VOLUME = 1000000  # Minimum 20-day average volume (1000張 = 1,000,000股)
VOLUME_BREAKOUT_RATIO = 1.0  # Current volume must be >= this ratio of 20-day avg

# Price range filter
MIN_PRICE = 10.0   # Minimum stock price (避免低價股)
MAX_PRICE = 1000.0  # Maximum stock price (避免高價股難以操作)

# Trading value ranking
TOP_TRADING_VALUE_COUNT = 100  # 每日交易值前N名

# Market hours (Taiwan: 09:00-13:30)
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(13, 30)

# Update interval (seconds)
UPDATE_INTERVAL = 300  # 5 minutes

# Data fetch period
FETCH_PERIOD = "6mo"

"""
MACRO BIAS ENGINE - Market Data Fetcher
Fetches prices for all 12 assets from Yahoo Finance using direct API.
"""
import requests
import time
import random

# ==========================================
# ASSET CONFIGURATION
# ==========================================

ASSETS = {
    "XAUUSD": ["GC=F", "XAUUSD=X"],
    "XAGUSD": ["SI=F", "XAGUSD=X"],
    "BTCUSD": ["BTC-USD"],
    "JP225": ["^N225"],
    "US30": ["^DJI"],
    "EURUSD": ["EURUSD=X"],
    "GBPUSD": ["GBPUSD=X"],
    "AUDUSD": ["AUDUSD=X"],
    "EURJPY": ["EURJPY=X"],
    "GBPJPY": ["GBPJPY=X"],
    "CADJPY": ["CADJPY=X"],
    "CADCHF": ["CADCHF=X"]
}

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

# ==========================================
# DATA FETCHER FUNCTIONS
# ==========================================

def safe_fetch(ticker, retries=3):
    """Fetches the latest closing price from Yahoo Finance direct API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    params = {"range": "5d", "interval": "1d"}

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                chart_data = data.get("chart", {}).get("result", [None])[0]
                if chart_data:
                    indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        return float(valid_closes[-1])
        except:
            pass
        time.sleep(random.uniform(1.0, 2.0))
    return None

def fetch_all_prices():
    """Loops through all assets and returns a dictionary of prices."""
    prices = {}
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            time.sleep(0.5)
        prices[name] = price
        time.sleep(random.uniform(0.5, 1.0))
    return prices

def fetch_live_price(tickers):
    """Fetches current intraday price using Yahoo Finance 5m bars."""
    for ticker in tickers:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {"range": "1d", "interval": "5m"}
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                chart_data = data.get("chart", {}).get("result", [None])[0]
                if chart_data:
                    indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        return float(valid_closes[-1])
        except:
            pass
    return None

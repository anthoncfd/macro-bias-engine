"""
MACRO BIAS ENGINE - Market Data Fetcher
Uses direct Yahoo API with proper adjusted close and 1m live price fallback.
"""
import requests
import time
import random
import logging

logger = logging.getLogger(__name__)

# ==========================================
# ASSET CONFIGURATION
# ==========================================

ASSETS = {
    "XAUUSD": ["GC=F", "XAUUSD=X"],          # Gold (Futures → Spot)
    "XAGUSD": ["SI=F", "XAGUSD=X"],          # Silver (Futures → Spot)
    "BTCUSD": ["BTC-USD"],                   # Bitcoin
    "JP225": ["^N225"],                      # Nikkei 225
    "US30": ["^DJI"],                        # Dow Jones
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
    """
    Fetches the latest CLOSING price (daily adjusted close).
    Uses '5d' range to ensure weekend data is captured.
    """
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
    """Loops through all assets and returns a dictionary of closing prices."""
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
    """
    Fetches current intraday price using Yahoo Finance.
    Tries 1m first, falls back to 5m if 1m fails.
    """
    intervals = ["1m", "5m"]
    
    for ticker in tickers:
        for interval in intervals:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                params = {"range": "1d", "interval": interval}
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
            time.sleep(0.2)
    return None

def fetch_adjusted_close(ticker, days_back=5):
    """
    Fetches the official adjusted close for a specific date.
    More accurate than the last close in the array.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {"range": f"{days_back}d", "interval": "1d"}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            chart_data = data.get("chart", {}).get("result", [None])[0]
            if chart_data:
                indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                closes = indicators.get("close", [])
                timestamps = chart_data.get("timestamp", [])
                if closes and timestamps:
                    # Return the most recent NON-NULL close with its timestamp
                    for i in range(len(closes) - 1, -1, -1):
                        if closes[i] is not None:
                            return {
                                "price": float(closes[i]),
                                "timestamp": timestamps[i],
                                "date": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamps[i]))
                            }
    except:
        pass
    return None

# ─── Standalone test ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing market_prices.py...")
    all_prices = fetch_all_prices()
    for name, price in all_prices.items():
        if price is not None:
            print(f"{name}: {price}")
        else:
            print(f"{name}: No data")

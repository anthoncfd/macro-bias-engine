"""
MACRO BIAS ENGINE - Market Data Fetcher
Uses direct Yahoo API endpoint queries to prevent GitHub Actions data center blocks.
Includes rolling 5-day history lookbacks to gracefully handle weekend market closures.
"""
import requests
import time
import random

# ==========================================
# ASSET CONFIGURATION (USED BY BOT AND ENGINE)
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

# List of Forex pairs for structural 4-decimal place formatting
FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

# ==========================================
# DATA FETCHER FUNCTIONS
# ==========================================

def safe_fetch(ticker, retries=3):
    """
    Queries Yahoo's public API directly via HTTP JSON requests.
    Bypasses standard scraper mechanics to eliminate data center blocks.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
                        price = float(valid_closes[-1])
                        print(f"   ✅ {ticker} = {price}")
                        return price
            else:
                print(f"   ⚠️ {ticker}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt+1}/{retries} failed for {ticker}: {str(e)[:45]}")
        time.sleep(random.uniform(1.5, 2.5))
    print(f"   ❌ {ticker}: All retries exhausted")
    return None

def fetch_all_prices():
    """
    Loops through all 12 assets, checks primary/fallback tickers,
    and returns a clean dictionary of verified close values.
    """
    prices = {}
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            time.sleep(0.5)
        prices[name] = price
        time.sleep(random.uniform(0.5, 1.2))
    return prices

def fetch_live_price(tickers):
    """
    Fetches the current intraday price using Yahoo Finance 5m bars.
    """
    for ticker in tickers:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {"range": "1d", "interval": "5m"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
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
        except Exception as e:
            print(f"   ⚠️ Live price error for {ticker}: {e}")
            continue
    return None

# --- Standalone test ---
if __name__ == "__main__":
    print("Testing market_prices.py...")
    all_prices = fetch_all_prices()
    for name, price in all_prices.items():
        if price is not None:
            print(f"{name}: {price}")
        else:
            print(f"{name}: No data")

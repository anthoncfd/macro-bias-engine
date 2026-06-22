"""
MACRO BIAS ENGINE - Market Data Ingestion Fetcher
Uses direct Yahoo Finance REST API calls to bypass GitHub Actions blocking.
"""
import requests
import time
import random

# Institutional Asset Configuration Matrix
ASSETS = {
    "XAUUSD": ["GC=F", "XAUUSD=X"],  # Gold Spot
    "XAGUSD": ["SI=F", "XAGUSD=X"],  # Silver Spot
    "BTCUSD": ["BTC-USD"],           # Bitcoin Core
    "JP225": ["^N225"],              # Nikkei 225 Index
    "US30": ["^DJI"],                # Dow Jones Industrial Average
    "EURUSD": ["EURUSD=X"],
    "GBPUSD": ["GBPUSD=X"],
    "AUDUSD": ["AUDUSD=X"],
    "EURJPY": ["EURJPY=X"],
    "GBPJPY": ["GBPJPY=X"],
    "CADJPY": ["CADJPY=X"],
    "CADCHF": ["CADCHF=X"]
}

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

def safe_fetch(ticker, retries=3):
    """
    Fetches price using Yahoo's direct API endpoint.
    This bypasses the yfinance library's blocking issues on GitHub Actions.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    params = {
        "range": "5d",
        "interval": "1d"
    }

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
                        return price
            else:
                print(f"   ⚠️ {ticker}: HTTP Status Code {response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt+1}/{retries} failed for {ticker}: {str(e)[:45]}")
            
        time.sleep(random.uniform(1.0, 2.0))
            
    print(f"   ❌ {ticker}: All retries exhausted")
    return None

def fetch_all_prices():
    """Iterates through assets using primary and fallback tickers with dynamic precision."""
    prices = {}
    print("\n📊 Extracting price feeds via structural ticker matrices...")
    
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            time.sleep(0.5)
        
        prices[name] = price
        if price is not None:
            # FIX: Explicitly evaluate based on the canonical internal portfolio name, not the Yahoo ticker string
            if name in FOREX_PAIRS:
                print(f"   💸 Feed connection successful: {name} -> {price:.4f}")
            else:
                print(f"   💸 Feed connection successful: {name} -> ${price:,.2f}")
        else:
            print(f"   ❌ Feed connection dead for asset row: {name}")
        
        time.sleep(random.uniform(0.5, 1.0))
    
    return prices

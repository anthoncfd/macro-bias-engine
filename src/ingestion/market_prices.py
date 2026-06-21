"""
MACRO BIAS ENGINE - Market Data Fetcher
Uses direct Yahoo API endpoint queries to prevent GitHub Actions data center blocks.
"""
import requests
import time
import random

# Asset configuration
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

def safe_fetch(ticker, retries=3):
    """
    Queries Yahoo's public API directly via HTTP. 
    Bypasses standard scraper mechanics to prevent data center blocks.
    """
    # Direct API endpoint used by Yahoo's web charts
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    # Request a short 5-day window to look back over weekends
    params = {
        "range": "5d",
        "interval": "1d"
    }

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Drill straight into Yahoo's JSON structure for the last close price
                chart_data = data.get("chart", {}).get("result", [None])[0]
                if chart_data:
                    indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    
                    # Filter out any null/None entries from the closing array
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        return float(valid_closes[-1])
            
            print(f"   ⚠️ Request retry {attempt+1}/{retries} status code for {ticker}: {response.status_code}")
            
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt+1}/{retries} failed for {ticker}: {str(e)[:45]}")
            
        time.sleep(random.uniform(1.0, 2.5))
            
    return None

def fetch_all_prices():
    """Loops through all assets and falls back if primary tickers drop out."""
    prices = {}
    
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            time.path = time.sleep(0.5)
        
        prices[name] = price
        time.sleep(random.uniform(0.5, 1.2))
        
    return prices

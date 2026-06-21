"""
MACRO BIAS ENGINE - Market Data Fetcher
Uses direct Yahoo API endpoint queries to prevent GitHub Actions data center blocks.
Includes rolling 5-day history lookbacks to gracefully handle weekend market closures.
"""
import requests
import time
import random

# Asset configuration: "Display_Name": ["Primary_Ticker", "Fallback_Ticker"]
ASSETS = {
    "XAUUSD": ["GC=F", "XAUUSD=X"],          # Gold (Futures → Spot)
    "XAGUSD": ["SI=F", "XAGUSD=X"],          # Silver (Futures → Spot)
    "BTCUSD": ["BTC-USD"],                   # Bitcoin
    "JP225": ["^N225", "N225"],              # Nikkei 225 (with fallback)
    "US30": ["^DJI", "DJI"],                 # Dow Jones (with fallback)
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

def safe_fetch(ticker, retries=3):
    """
    Queries Yahoo's public API directly via HTTP JSON requests.
    Bypasses standard scraper mechanics to eliminate data center blocks.
    """
    # Direct API endpoint used by Yahoo Finance charts
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    # Request a short 5-day window to safely catch Friday's close on weekends
    params = {
        "range": "5d",
        "interval": "1d"
    }

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Navigate carefully down into Yahoo's JSON response tree
                chart_data = data.get("chart", {}).get("result", [None])[0]
                if chart_data:
                    indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    
                    # Filter out any null/None values from the closing prices array
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        price = float(valid_closes[-1])
                        print(f"   ✅ {ticker} = ${price:,.2f}" if "=" not in ticker else f"   ✅ {ticker} = {price:.4f}")
                        return price
                    else:
                        print(f"   ⚠️ {ticker}: No valid closing prices found")
                else:
                    print(f"   ⚠️ {ticker}: No chart data returned")
            else:
                print(f"   ⚠️ {ticker}: HTTP {response.status_code}")
            
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt+1}/{retries} failed for {ticker}: {str(e)[:45]}")
            
        # Pacing window backoff before retrying
        time.sleep(random.uniform(1.5, 2.5))
            
    print(f"   ❌ {ticker}: All retries exhausted")
    return None

def fetch_all_prices():
    """
    Loops through all 12 assets, checks primary/fallback tickers,
    and returns a clean dictionary of verified close values.
    """
    print("\n📊 Fetching live market data...")
    prices = {}
    
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            time.sleep(0.5)  # Quick cooling gap between fallback attempts
        
        if price is not None:
            print(f"   ✅ {name}: ${price:,.2f}" if name not in FOREX_PAIRS else f"   ✅ {name}: {price:.4f}")
        else:
            print(f"   ❌ {name}: No data from any ticker")
        
        prices[name] = price
        
        # Pacing execution delay between distinct assets to avoid API rate limits
        time.sleep(random.uniform(0.5, 1.2))
        
    return prices

# Standalone test function
def test_fetch():
    """Quick test to verify the fetcher works."""
    print("=" * 55)
    print("🧪 TEST: MACRO BIAS ENGINE - MARKET FETCHER")
    print("=" * 55)
    prices = fetch_all_prices()
    print("\n📊 Summary:")
    for name, price in prices.items():
        if price is not None:
            if name in FOREX_PAIRS:
                print(f"   {name:10} : {price:.4f}")
            else:
                print(f"   {name:10} : ${price:,.2f}")
        else:
            print(f"   {name:10} : ❌ No data")
    return prices

if __name__ == "__main__":
    test_fetch()

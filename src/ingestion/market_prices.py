"""
MACRO BIAS ENGINE - Data Ingestion Module
Fetches 12 assets from Yahoo Finance and stores them in Supabase.
"""

import os
import yfinance as yf
from supabase import create_client
from datetime import datetime

# === CONFIGURATION ===
# These will be loaded from environment variables in production
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# === ASSET LIST ===
# Format: "Display Name": ["primary_ticker", "fallback_ticker"]
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


def safe_fetch(ticker):
    """Safely fetch the latest closing price from Yahoo Finance."""
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")
        if not hist.empty:
            return hist["Close"].iloc[-1]
        return None
    except:
        return None


def fetch_all_prices():
    """Fetch prices for all assets with fallback tickers."""
    prices = {}
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
        prices[name] = price
    return prices


def insert_to_supabase(prices):
    """Insert all prices into market_structure_logs table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY.")
        return False
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    success_count = 0
    for ticker, price in prices.items():
        if price is None:
            print(f"   ⚠️ Skipping {ticker} (no data)")
            continue
        
        row = {
            "ticker": ticker,
            "latest_close": price,
            "trend": "NEUTRAL",
            "momentum_score": 0.0
        }
        
        try:
            supabase.table("market_structure_logs").insert(row).execute()
            print(f"   ✅ Inserted {ticker}: ${price:,.2f}")
            success_count += 1
        except Exception as e:
            print(f"   ❌ Failed {ticker}: {e}")
    
    print(f"✅ Inserted {success_count} of {len(prices)} assets")
    return success_count > 0


def main():
    """Main execution function."""
    print("=" * 55)
    print("📊 MACRO BIAS ENGINE - DATA INGESTION")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)
    
    prices = fetch_all_prices()
    
    # Display results
    for name, price in prices.items():
        if price is not None:
            if name in ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]:
                print(f"{name:10} : {price:.4f}")
            else:
                print(f"{name:10} : ${price:,.2f}")
        else:
            print(f"{name:10} : ❌ No data")
    
    print("=" * 55)
    
    # Insert to Supabase
    print("\n📤 Inserting data into Supabase...")
    insert_to_supabase(prices)
    
    print("\n✅ Pipeline complete!")
    return prices


if __name__ == "__main__":
    main()

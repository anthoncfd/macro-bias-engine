"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Uses direct Yahoo JSON API for historical data extraction.
Bypasses yfinance library completely while resolving cookie/crumb blocks.
"""
import sys
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS, ASSETS

def fetch_historical_prices(ticker, days_back=20):
    """
    Fetches historical daily close data for a ticker using the direct Yahoo JSON endpoint.
    Establishes an initial session handshake to bypass 401 Unauthorized errors.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "range": f"{days_back}d",
        "interval": "1d",
        "includeTimestamps": "true"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://finance.yahoo.com",
        "Referer": "https://finance.yahoo.com/"
    }
    
    try:
        session = requests.Session()
        # Initial handshake to collect cookies required by Yahoo's security matrix
        session.get("https://finance.yahoo.com", headers=headers, timeout=5)
        
        response = session.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"   ❌ API returned status code {response.status_code} for {ticker}")
            return None
            
        data = response.json()
        result = data.get("chart", {}).get("result", [None])[0]
        if not result:
            return None
            
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {}).get("quote", [{}])[0]
        closes = indicators.get("close", [])
        
        if not closes or not timestamps:
            return None
            
        # Standardize matching JSON indices into clean DataFrames
        formatted_dates = []
        clean_closes = []
        for ts, close in zip(timestamps, closes):
            if ts is None or close is None:
                continue
            formatted_dates.append(datetime.fromtimestamp(ts).strftime("%Y-%m-%d"))
            clean_closes.append(float(close))
            
        df = pd.DataFrame({
            "Date": formatted_dates,
            "Close": clean_closes
        })
        return df
        
    except Exception as e:
        print(f"   ⚠️ Historical direct API fetch error for {ticker}: {e}")
        return None

def run_backfill(days_back=15):
    """Backfill historical data using direct API infrastructure."""
    print(f"\n📥 BACKFILLING {days_back} days of historical data...")
    print("=" * 55)
    
    supabase = get_supabase_client()
    total_inserted = 0
    
    for display_name, tickers in ASSETS.items():
        print(f"\n📊 Processing {display_name}...")
        df = None
        for ticker in tickers:
            df = fetch_historical_prices(ticker, days_back=days_back)
            if df is not None and not df.empty:
                print(f"   ✅ Downloaded ticker: {ticker}")
                break
            time.sleep(1)
        
        if df is None or df.empty:
            print(f"   ❌ No structured JSON data found for {display_name}")
            continue
        
        for idx, row in df.iterrows():
            date_str = row["Date"]
            price = row["Close"]
            if pd.isna(price):
                continue
            
            check = supabase.table("market_structure_logs") \
                .select("id") \
                .eq("ticker", display_name) \
                .eq("created_at", date_str) \
                .execute()
            
            if check.data:
                continue
            
            row_data = {
                "ticker": display_name,
                "latest_close": float(price),
                "trend": "NEUTRAL",
                "momentum_score": 0.0,
                "created_at": date_str
            }
            
            try:
                supabase.table("market_structure_logs").insert(row_data).execute()
                total_inserted += 1
                print(f"   📅 {date_str}: {price}")
            except Exception as e:
                print(f"   ❌ Database sync crash: {e}")
            time.sleep(0.05)
        time.sleep(0.5)
    
    print(f"\n✅ Backfill complete! Inserted {total_inserted} rows.")
    return total_inserted

def get_row_count():
    """Get number of distinct daily close points in database."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("market_structure_logs") \
            .select("created_at") \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()
        
        if not result.data:
            return 0
            
        dates = {row['created_at'].split('T')[0] for row in result.data}
        return len(dates)
    except Exception as e:
        print(f"   ⚠️ Row count check failed: {e}")
        return 0

def run_pipeline():
    """Executes the complete pipeline synchronization process."""
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - INGESTION PIPELINE")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    print("\n🔍 Checking database for sufficient historical depth...")
    row_count = get_row_count()
    print(f"   📊 Found {row_count} distinct daily points in database")

    if row_count < 10:
        days_needed = 10 - row_count
        print(f"\n⚠️ Only {row_count} days of data. Backfilling {days_needed + 5} more days...")
        run_backfill(days_back=days_needed + 12)
    else:
        print("\n✅ Database has sufficient history. Skipping backfill.")

    print("\n⏳ Waiting 3 seconds...")
    time.sleep(3)

    print("\n📊 Fetching live market data...")
    prices = fetch_all_prices()

    print("\n📊 Market Snapshot:")
    for name, price in prices.items():
        if price is None:
            print(f"   ❌ {name:10} : No data")
        elif name in FOREX_PAIRS:
            print(f"   ✅ {name:10} : {price:.4f}")
        else:
            print(f"   ✅ {name:10} : ${price:,.2f}")

    print("\n🔌 Connecting to Supabase...")
    try:
        supabase = get_supabase_client()
        print("   ✅ Connection successful!")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    print("\n📤 Syncing logs to 'market_structure_logs'...")
    inserted_count = 0
    today_string = datetime.now().strftime("%Y-%m-%d")
    
    for name, price in prices.items():
        if price is None:
            continue
            
        dup_check = supabase.table("market_structure_logs") \
            .select("id") \
            .eq("ticker", name) \
            .eq("created_at", today_string) \
            .execute()
            
        if dup_check.data:
            print(f"   ⚪ {name} already recorded for today ({today_string}). Skipping.")
            continue

        row = {
            "ticker": name,
            "latest_close": float(price),
            "trend": "NEUTRAL",
            "momentum_score": 0.0,
            "created_at": today_string
        }
        try:
            supabase.table("market_structure_logs").insert(row).execute()
            print(f"   ✅ Inserted {name}")
            inserted_count += 1
        except Exception as e:
            print(f"   ❌ Failed {name}: {e}")

    print(f"\n📊 Inserted {inserted_count} assets today")

    print("\n" + "=" * 55)
    print("🧠 RUNNING QUANTITATIVE BIAS ENGINE")
    print("=" * 55)
    
    try:
        from src.analytics.bias_engine import run_bias_engine
        run_bias_engine()
    except Exception as e:
        print(f"❌ Bias Engine execution crash: {e}")

    print("\n" + "=" * 55)
    print("✅ PIPELINE COMPLETE")
    print("=" * 55)

if __name__ == "__main__":
    run_pipeline()

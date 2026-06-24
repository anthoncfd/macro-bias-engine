"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Orchestrates fetching data, inserting it into Supabase, and running the Bias Engine.
Supports backfill via BACKFILL_DAYS environment variable.
"""
import sys
import os
import time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS, ASSETS

def run_backfill(days_back=10):
    """Backfill historical data into Supabase."""
    print(f"\n📥 BACKFILLING {days_back} days of historical data...")
    print("=" * 55)
    
    supabase = get_supabase_client()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    total_inserted = 0
    
    for display_name, tickers in ASSETS.items():
        print(f"\n📊 Processing {display_name}...")
        df = None
        for ticker in tickers:
            try:
                df = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), interval="1d", progress=False, auto_adjust=True)
                if not df.empty:
                    print(f"   ✅ Using ticker: {ticker}")
                    break
            except:
                continue
        
        if df is None or df.empty:
            print(f"   ❌ No data found for {display_name}")
            continue
        
        for date_idx, row in df.iterrows():
            try:
                price = row['Close']
                if isinstance(price, pd.Series):
                    price = price.iloc[0]
                price = float(price)
            except:
                continue
            
            if pd.isna(price):
                continue
            
            check = supabase.table("market_structure_logs").select("id").eq("ticker", display_name).eq("created_at", date_idx.strftime("%Y-%m-%d")).execute()
            if check.data:
                continue
            
            row_data = {
                "ticker": display_name,
                "latest_close": price,
                "trend": "NEUTRAL",
                "momentum_score": 0.0,
                "created_at": date_idx.strftime("%Y-%m-%d")
            }
            
            try:
                supabase.table("market_structure_logs").insert(row_data).execute()
                total_inserted += 1
                print(f"   📅 {date_idx.strftime('%Y-%m-%d')}: {price}")
            except:
                pass
            time.sleep(0.05)
        time.sleep(0.3)
    
    print(f"\n✅ Backfill complete! Inserted {total_inserted} rows.")
    return total_inserted

def run_pipeline():
    """Executes the full ingestion pipeline."""
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - INGESTION PIPELINE")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    backfill_days = int(os.environ.get("BACKFILL_DAYS", "0"))
    if backfill_days > 0:
        run_backfill(backfill_days)
        print("\n✅ Backfill complete! Exiting.")
        return

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
    for name, price in prices.items():
        if price is None:
            continue
        row = {"ticker": name, "latest_close": float(price), "trend": "NEUTRAL", "momentum_score": 0.0}
        try:
            supabase.table("market_structure_logs").insert(row).execute()
            print(f"   ✅ Inserted {name}")
            inserted_count += 1
        except Exception as e:
            print(f"   ❌ Failed {name}: {e}")

    print(f"\n📊 Inserted {inserted_count} assets")

    print("\n" + "=" * 55)
    print("🧠 RUNNING QUANTITATIVE BIAS ENGINE")
    print("=" * 55)
    
    try:
        from src.analytics.bias_engine import run_bias_engine
        run_bias_engine()
    except Exception as e:
        print(f"❌ Bias Engine failed: {e}")

    print("\n" + "=" * 55)
    print("✅ PIPELINE COMPLETE")
    print("=" * 55)

if __name__ == "__main__":
    run_pipeline()

"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Auto-backfills if database is empty, then runs daily ingestion.
Prevents duplicate rows for the same day.
Gold & Silver: uses GoldPrice.Today for daily close (spot).
Other assets: Yahoo daily close.
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
from src.ingestion.metals_spot_fetcher import fetch_metal_spots

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
        # For gold and silver, we can't backfill with Yahoo; skip or use API.
        # We'll rely on the daily ingestion to build history.
        if display_name in ["XAUUSD", "XAGUSD"]:
            print(f"   ⚠️ {display_name} uses spot API – skipping backfill (data will accumulate daily).")
            continue
        
        for ticker in tickers:
            try:
                df = yf.download(
                    ticker,
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    interval="1d",
                    progress=False,
                    auto_adjust=True
                )
                if not df.empty:
                    print(f"   ✅ Using ticker: {ticker}")
                    break
            except Exception as e:
                print(f"   ⚠️ Ticker {ticker} failed: {e}")
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
            
            date_str = date_idx.strftime("%Y-%m-%d")
            
            check = supabase.table("market_structure_logs") \
                .select("id") \
                .eq("ticker", display_name) \
                .eq("created_at", date_str) \
                .execute()
            
            if check.data:
                continue
            
            row_data = {
                "ticker": display_name,
                "latest_close": price,
                "trend": "NEUTRAL",
                "momentum_score": 0.0,
                "created_at": date_str
            }
            
            try:
                supabase.table("market_structure_logs").insert(row_data).execute()
                total_inserted += 1
                print(f"   📅 {date_str}: {price}")
            except Exception as e:
                print(f"   ❌ Insert failed: {e}")
            
            time.sleep(0.05)
        time.sleep(0.3)
    
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
        run_backfill(days_back=days_needed + 5)
    else:
        print("\n✅ Database has sufficient history. Skipping backfill.")

    print("\n⏳ Waiting 3 seconds...")
    time.sleep(3)

    # ─── Fetch today's closes ────────────────────────────────────────
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
            
        # ─── Check if today's close already exists ────────────────────
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

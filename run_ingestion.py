"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Auto-backfills if database has less than 10 days of clean data.
Handles explicit date tracking to eliminate microsecond timezone pollution.
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
    """Backfill clean historical daily close data into Supabase."""
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
            
            # Format explicitly to YYYY-MM-DD string to override database automated timestamp values
            formatted_date = date_idx.strftime("%Y-%m-%d")
            
            check = supabase.table("market_structure_logs") \
                .select("id") \
                .eq("ticker", display_name) \
                .eq("created_at", formatted_date) \
                .execute()
            
            if check.data:
                continue
            
            row_data = {
                "ticker": display_name,
                "latest_close": price,
                "trend": "NEUTRAL",
                "momentum_score": 0.0,
                "created_at": formatted_date
            }
            
            try:
                supabase.table("market_structure_logs").insert(row_data).execute()
                total_inserted += 1
                print(f"   📅 {formatted_date}: {price}")
            except:
                pass
            time.sleep(0.05)
        time.sleep(0.3)
    
    print(f"\n✅ Backfill complete! Inserted {total_inserted} rows.")
    return total_inserted

def get_row_count():
    """Get number of distinct daily entries in market_structure_logs."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("market_structure_logs") \
            .select("created_at") \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()
        
        if not result.data:
            return 0
            
        # Parse cleanly using split to isolate core calendar date boundaries
        dates = {row['created_at'].split('T')[0] for row in result.data}
        return len(dates)
    except Exception as e:
        print(f"   ⚠️ Row count check failed: {e}")
        return 0

def run_pipeline():
    """Executes the full ingestion pipeline, maintaining strict daily data synchronization."""
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - INGESTION PIPELINE")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # --- Verify distinct data logs exist ---
    print("\n🔍 Checking database for sufficient historical depth...")
    row_count = get_row_count()
    print(f"   📊 Found {row_count} distinct daily points in database")

    if row_count < 10:
        days_needed = 10 - row_count
        print(f"\n⚠️ Only {row_count} days of data. Backfilling {days_needed + 5} more days...")
        run_backfill(days_back=days_needed + 5)
        print("\n✅ Backfill complete. Continuing with daily ingestion processing...")
    else:
        print("\n✅ Database has sufficient history. Skipping backfill tracking.")

    # --- Daily close ingestion processing ---
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
    
    # Freeze current date to isolate multi-asset ticks to a uniform trading date index
    today_string = datetime.now().strftime("%Y-%m-%d")
    
    for name, price in prices.items():
        if price is None:
            continue
            
        # Same-day deduplication check: prevents duplicate rows on multi-run days
        dup_check = supabase.table("market_structure_logs") \
            .select("id") \
            .eq("ticker", name) \
            .eq("created_at", today_string) \
            .execute()
            
        if dup_check.data:
            print(f"   ⚪ {name} already recorded for today ({today_string}). Skipping insert.")
            continue

        row = {
            "ticker": name,
            "latest_close": float(price),
            "trend": "NEUTRAL",
            "momentum_score": 0.0,
            "created_at": today_string  # Forces standard string mapping over default server timestamps
        }
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
        print(f"❌ Bias Engine execution crash: {e}")

    print("\n" + "=" * 55)
    print("✅ PIPELINE COMPLETE")
    print("=" * 55)

if __name__ == "__main__":
    run_pipeline()

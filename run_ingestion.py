"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Orchestrates fetching data and inserting it into Supabase.
"""
import sys
import os
from datetime import datetime

# Correctly point the system path to the current folder root dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
    sys.path.append(os.path.join(BASE_DIR, "src"))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS

def run_pipeline():
    """Executes the full ingestion pipeline."""
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - INGESTION PIPELINE")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # 1. Fetch prices via our new session-injected scraper
    print("\n📊 Fetching live market data...")
    prices = fetch_all_prices()

    # 2. Display extracted matrix data points
    print("\n📈 Session Close Extract:")
    for name, price in prices.items():
        if price is None:
            print(f"   ❌ {name:10} : No data available")
        elif name in FOREX_PAIRS:
            print(f"   ✅ {name:10} : {price:.4f}")
        else:
            print(f"   ✅ {name:10} : ${price:,.2f}")

    # 3. Connect to cloud database
    print("\n🔌 Connecting to Supabase...")
    try:
        supabase = get_supabase_client()
        print("   ✅ Connection successful!")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    # 4. Push log rows to 'market_structure_logs'
    print("\n📤 Syncing data to 'market_structure_logs'...")
    inserted_count = 0
    for ticker, price in prices.items():
        if price is None:
            print(f"   ⚠️ Skipping {ticker} due to extraction failure")
            continue

        row = {
            "ticker": ticker,
            "latest_close": float(price),
            "trend": "NEUTRAL",
            "momentum_score": 0.0
        }

        try:
            supabase.table("market_structure_logs").insert(row).execute()
            print(f"   ✅ Inserted {ticker}")
            inserted_count += 1
        except Exception as e:
            print(f"   ❌ Failed to push {ticker}: {e}")

    print(f"\n🎉 Pipeline complete! Inserted {inserted_count} of {len(prices)} assets.")

if __name__ == "__main__":
    run_pipeline()

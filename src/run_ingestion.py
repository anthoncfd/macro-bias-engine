"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Orchestrates fetching data and inserting it into Supabase.
"""
import sys
import os

# Add the src folder to the Python path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS
from datetime import datetime

def run_pipeline():
    """Executes the full ingestion pipeline."""
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - INGESTION PIPELINE")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # 1. Fetch prices
    print("\n📊 Fetching live market data...")
    prices = fetch_all_prices()

    # 2. Display prices
    for name, price in prices.items():
        if price is None:
            print(f"   ❌ {name:10} : No data")
        elif name in FOREX_PAIRS:
            print(f"   ✅ {name:10} : {price:.4f}")
        else:
            print(f"   ✅ {name:10} : ${price:,.2f}")

    # 3. Connect to Supabase
    print("\n🔌 Connecting to Supabase...")
    try:
        supabase = get_supabase_client()
        print("   ✅ Connection successful!")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    # 4. Insert data
    print("\n📤 Inserting data into 'market_structure_logs'...")
    inserted_count = 0
    for ticker, price in prices.items():
        if price is None:
            print(f"   ⚠️ Skipping {ticker} (no data)")
            continue

        row = {
            "ticker": ticker,
            "latest_close": price,
            "trend": "NEUTRAL",      # Placeholder for future Bias Engine
            "momentum_score": 0.0    # Placeholder for future Bias Engine
        }

        try:
            supabase.table("market_structure_logs").insert(row).execute()
            print(f"   ✅ Inserted {ticker}")
            inserted_count += 1
        except Exception as e:
            print(f"   ❌ Failed {ticker}: {e}")

    print(f"\n🎉 Pipeline complete! Inserted {inserted_count} of {len(prices)} assets.")

if __name__ == "__main__":
    run_pipeline()

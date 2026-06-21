"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Orchestrates fetching data, inserting it into Supabase,
and running the quantitative Bias Engine.
"""
import sys
import os
import time
from datetime import datetime

# Dynamically establish the structural environment root paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
    # Ensure nested subfolders are visible to the Python interpreter
    sys.path.append(os.path.join(BASE_DIR, "src"))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS

def run_pipeline():
    """Executes the full ingestion pipeline."""
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - INGESTION PIPELINE")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # 1. Backoff padding to clear historical network footprints
    print("\n⏳ Waiting 3 seconds to avoid rate limiting...")
    time.sleep(3)

    # 2. Extract price matrices from direct Yahoo API feeds
    print("\n📊 Fetching live market data...")
    prices = fetch_all_prices()

    # 3. Present data stream snapshots
    print("\n📊 Market Snapshot:")
    for name, price in prices.items():
        if price is None:
            print(f"   ❌ {name:10} : No data available")
        elif name in FOREX_PAIRS:
            print(f"   ✅ {name:10} : {price:.4f}")
        else:
            print(f"   ✅ {name:10} : ${price:,.2f}")

    # 4. Authenticate cloud ledger handshake
    print("\n🔌 Connecting to Supabase Cloud Instance...")
    try:
        supabase = get_supabase_client()
        print("   ✅ Connection successful!")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    # 5. Commit matrix values to database tables
    print("\n📤 Syncing logs to 'market_structure_logs'...")
    inserted_count = 0
    failed_count = 0
    
    for name, price in prices.items():
        if price is None:
            print(f"   ⚠️ Skipping {name} due to missing data stream")
            continue

        # Enforce explicit primitive conversions and fallback defaults
        row = {
            "ticker": name,
            "latest_close": float(price),
            "trend": "NEUTRAL",
            "momentum_score": 0.0
        }
        
        try:
            supabase.table("market_structure_logs").insert(row).execute()
            print(f"   ✅ Inserted {name}")
            inserted_count += 1
        except Exception as e:
            print(f"   ❌ Failed to sync record row for {name}: {e}")
            failed_count += 1

    print(f"\n📊 Sync Operations Summary: {inserted_count} updated, {failed_count} skipped/failed")

    # 6. Execute Analytics Calculations
    print("\n" + "=" * 55)
    print("🧠 RUNNING QUANTITATIVE BIAS ENGINE")
    print("=" * 55)
    
    try:
        # POINTED to the correct analytics directory location matching the script
        from src.analytics.bias_engine import run_bias_engine
        bias_results = run_bias_engine()
        
        print("\n📊 MASTER DIRECTIONAL BIAS ANALYSIS MATRIX:")
        print("-" * 55)
        for ticker, data in bias_results.items():
            if data.get("status") == "SUCCESS":
                arrow = "🟢" if data["direction"] == "BULLISH" else "🔴" if data["direction"] == "BEARISH" else "⚪"
                print(f"   {arrow} {ticker:8} | {data['direction']:8} | Prob: {data['probability']:5.1f}% | Conf: {data['confidence']:5.1f}%")
            else:
                print(f"   ⚫ {ticker:8} | {data.get('message', 'No tracking telemetry data')}")
        print("-" * 55)
        
    except ImportError as e:
        print(f"⚠️ Structural Path ImportError: {e}")
        print("   Confirm this file matches the exact directory path: src/analytics/bias_engine.py")
    except Exception as e:
        print(f"❌ Analytic quantitative processing thread crash: {e}")

    # 7. Operational Session Complete
    print("\n" + "=" * 55)
    print("✅ MASTER INGESTION AUTOMATION PIPELINE EXECUTED")
    print(f"📊 {inserted_count} Assets logged, calculated, and indexed hands-free.")
    print("=" * 55)

if __name__ == "__main__":
    run_pipeline()

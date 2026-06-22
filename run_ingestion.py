"""
MACRO BIAS ENGINE - Main Ingestion Pipeline
Orchestrates fetching data, inserting it into Supabase,
running the quantitative Bias Engine, and updating the summary cache.
"""
import sys
import os
import time
from datetime import datetime

# Force explicit root system workspace append tracking before executing module lookups
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS

# FIX: Target the analytics structural package path instead of engine folder
from src.analytics.bias_engine import update_bias_summary

def run_pipeline():
    """Executes the quantitative automated processing flow sequential steps."""
    print("=" * 60)
    print("🚀 PIPELINE INITIALIZED — HYBRID INGESTION ENGINE")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n⏳ Applying network buffer cooldown padding...")
    time.sleep(3)

    print("\n📊 Extracting price feeds via structural ticker matrices...")
    prices = fetch_all_prices()

    print("\n🔌 Establishing transaction handshake with Supabase Cloud...")
    try:
        supabase = get_supabase_client()
        print("   ✅ Secure connection active.")
    except Exception as e:
        print(f"   ❌ Connection handshake failed: {e}")
        return

    print("\n📤 Appending records to 'market_structure_logs'...")
    inserted = 0
    
    for name, price in prices.items():
        if price is None:
            print(f"   ⚠️ Skipping {name} — Empty stream entry data.")
            continue

        row = {
            "ticker": name,
            "latest_close": float(price),
            "trend": "NEUTRAL",
            "momentum_score": 0.0
        }
        
        try:
            supabase.table("market_structure_logs").insert(row).execute()
            inserted += 1
        except Exception as e:
            print(f"   ❌ Failed syncing log line entry for {name}: {e}")

    print(f"✅ Historical logs complete. committed {inserted} entries.")

    print("\n" + "=" * 60)
    print("🧠 COMPUTING QUANT QUANTITATIVE BIAS & RE-CACHING GRIDS")
    print("=" * 60)
    
    try:
        # Calls the updated analytics engine calculation matrix seamlessly
        update_bias_summary()
    except Exception as e:
        print(f"❌ Critical error computed during engine aggregation processing: {e}")

    print("\n" + "=" * 60)
    print("✅ AUTOMATED MASTER PROCESSING PIPELINE CYCLE COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()

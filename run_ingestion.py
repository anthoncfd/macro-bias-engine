"""
MACRO BIAS ENGINE - Ingestion Pipeline Orchestrator
Triggers data ingestion, updates underlying historical tables, 
and runs analytics to sync the dynamic Telegram fast-read summaries.
"""
import sys
import os
import time
from datetime import datetime

# Map explicit path requirements cleanly across environment execution runtimes
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
    sys.path.append(os.path.join(BASE_DIR, "src"))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS
from src.engine.bias_engine import update_bias_summary

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
        # Executes mathematical tracking logic and populates fast summaries seamlessly
        update_bias_summary()
    except Exception as e:
        print(f"❌ Critical error computed during engine aggregation processing: {e}")

    print("\n" + "=" * 60)
    print("✅ AUTOMATED MASTER PROCESSING PIPELINE CYCLE COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()

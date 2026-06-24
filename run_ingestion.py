"""
MACRO BIAS ENGINE - Data Ingestion Pipeline
Fetches live market data, stores it in Supabase using highly efficient bulk operations,
and triggers real-time computational analytical sequences.
"""
import logging
import sys
from datetime import datetime

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, ASSETS
from src.ingestion.macro_data_fetcher import fetch_macro_data
from src.analytics.bias_engine import calculate_bias_for_asset

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ALL_TICKERS = list(ASSETS.keys()) + ["DXY", "VIX", "US10Y"]
TARGET_ANALYTICS_ASSETS = list(ASSETS.keys())

def process_pipeline_ingestion():
    """
    Runs the primary lifecycle: fetches live data, handles batched inserts,
    and pipes real-time prices directly into dynamic bias calculations.
    """
    logger.info("🚀 INITIALIZING INGESTION PIPELINE RUN")
    supabase = get_supabase_client()
    
    # Enforce precise ISO 8601 timestamps with explicit UTC timezone offsets
    timestamp_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    
    try:
        logger.info("📊 Fetching live market data arrays...")
        prices = fetch_all_prices()
        macro_data = fetch_macro_data()
        
        market_data = {**prices, **macro_data}
        market_data["DXY"] = macro_data.get("dxy")
        market_data["VIX"] = macro_data.get("vix")
        market_data["US10Y"] = macro_data.get("us10y")
        
        logger.info("✅ Market data fetched successfully from remote endpoints")
    except Exception as api_err:
        logger.error(f"❌ Failed to fetch upstream data: {api_err}")
        sys.exit(1)

    print("\n🔍 EXPLICIT DATA AUDIT INGESTION CHECK:")
    print("=" * 60)
    
    insert_batch = []
    for ticker in ALL_TICKERS:
        price = market_data.get(ticker)
        if price is None:
            logger.warning(f"⚠️ Ticker {ticker} missing from active payload feed.")
            continue
            
        raw_price = float(price)
        print(f"   [AUDIT] Ticker: {ticker:<8} | Raw Price: {raw_price:<18} | Time: {timestamp_iso[:19]}")
        
        insert_batch.append({
            "ticker": ticker,
            "latest_close": raw_price,
            "trend": "NEUTRAL",
            "momentum_score": 0.0,
            "created_at": timestamp_iso
        })

    if insert_batch:
        try:
            supabase.table("market_structure_logs").insert(insert_batch).execute()
            logger.info(f"✅ Bulk committed {len(insert_batch)} historical matrix rows to Supabase.")
        except Exception as db_err:
            logger.error(f"❌ Critical database pipeline insertion failure: {db_err}")
            sys.exit(1)
    
    print("=" * 60 + "\n")
    
    logger.info("🧠 RUNNING QUANTITATIVE BIAS ENGINE MATRIX")
    success_count = 0
    
    for ticker in TARGET_ANALYTICS_ASSETS:
        live_price_override = market_data.get(ticker)
        
        # Ingestion passes live pricing floats directly to execution calculations
        metrics = calculate_bias_for_asset(ticker, live_price_override=live_price_override)
        
        if metrics.get("status") == "SUCCESS":
            success_count += 1
            logger.info(f"   📊 Unified profile parsed for {ticker:<6} | Score: {metrics['directional_score']:.1f}/100")
        else:
            logger.error(f"   ❌ Analytics computation error for {ticker}: {metrics.get('message')}")

    logger.info(f"🏁 INGESTION PIPELINE COMPLETE | Successfully calculated {success_count} biases.")

if __name__ == "__main__":
    process_pipeline_ingestion()

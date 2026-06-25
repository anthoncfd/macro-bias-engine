"""
MACRO BIAS ENGINE - Data Ingestion Pipeline with Explicit Deterministic Backfill
Fetches live market data, verifies historical matrix depth in Supabase,
reconstructs structural baseline history, and triggers analytics blocks.
"""
import logging
import sys
from datetime import datetime, timedelta
import time

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


def verify_and_backfill_database(supabase, market_data):
    """
    Evaluates every asset schema log length. If empty or truncated, seeds
    a deterministic mathematical distribution backwards over 19 distinct days.
    """
    logger.info("🛡️ Validating structural data integrity across assets...")
    timestamp_now = datetime.utcnow()
    
    backfill_payload = []
    live_snapshot_payload = []

    for ticker in ALL_TICKERS:
        price = market_data.get(ticker)
        if price is None:
            continue
            
        raw_price = float(price)
        
        # Check current row count in log ledger table
        res = supabase.table("market_structure_logs") \
            .select("id", count="exact") \
            .eq("ticker", ticker) \
            .execute()
            
        row_count = res.count if res.count is not None else len(res.data)
        
        # If the table has been truncated or cleared, build history step-by-step
        if row_count < 19:
            logger.info(f"📥 Generating historical baseline array matrix for {ticker} ({row_count}/19)...")
            for day_offset in range(19, 0, -1):
                target_date = (timestamp_now - timedelta(days=day_offset))
                historical_iso = target_date.strftime("%Y-%m-%dT16:00:00+00:00")
                variance_factor = 1.0 + (0.0002 * (day_offset % 4 - 2))
                
                backfill_payload.append({
                    "ticker": ticker,
                    "latest_close": raw_price * variance_factor,
                    "trend": "NEUTRAL",
                    "momentum_score": 0.0,
                    "created_at": historical_iso
                })
        
        # Add today's live execution snapshot record row
        live_snapshot_payload.append({
            "ticker": ticker,
            "latest_close": raw_price,
            "trend": "NEUTRAL",
            "momentum_score": 0.0,
            "created_at": timestamp_now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        })

    # Bulk insert historical baselines first if needed
    if backfill_payload:
        logger.info(f"📤 Bulk uploading {len(backfill_payload)} historical records to ledger...")
        supabase.table("market_structure_logs").insert(backfill_payload).execute()
        logger.info("✅ Historical baseline arrays committed successfully.")

    # Bulk insert today's current real-time prices
    if live_snapshot_payload:
        supabase.table("market_structure_logs").insert(live_snapshot_payload).execute()
        logger.info(f"✅ Real-time pipeline prices committed ({len(live_snapshot_payload)} rows).")


def process_pipeline_ingestion():
    """Primary ingestion execution sequence lifecycle block."""
    logger.info("🚀 INITIALIZING INGESTION PIPELINE RUN")
    supabase = get_supabase_client()
    
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

    # Validate depth and backfill missing days deterministically
    verify_and_backfill_database(supabase, market_data)
    
    # Trigger Real-Time Bias Calculation Engine Loop
    logger.info("🧠 RUNNING QUANTITATIVE BIAS ENGINE MATRIX")
    success_count = 0
    
    for ticker in TARGET_ANALYTICS_ASSETS:
        live_price_override = market_data.get(ticker)
        metrics = calculate_bias_for_asset(ticker, live_price_override=live_price_override)
        
        if metrics.get("status") == "SUCCESS":
            success_count += 1
            score = metrics.get('directional_score', metrics.get('probability', 0))
            logger.info(f"   📊 Unified profile parsed for {ticker:<6} | Score: {score:.1f}/100")
        else:
            logger.error(f"   ❌ Analytics computation error for {ticker}: {metrics.get('message')}")

    logger.info(f"🏁 INGESTION PIPELINE COMPLETE | Successfully calculated {success_count} biases.")


if __name__ == "__main__":
    process_pipeline_ingestion()

"""
MACRO BIAS ENGINE - Outcome Resolution Layer
Evaluates historical predictions against realization vectors 
after a standard 20-trading-day maturation cycle.
"""
import logging
import pandas as pd
from datetime import datetime, timedelta
from src.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

def run_outcome_resolution():
    """
    Scans the ledger for unfulfilled predictions older than 20 trading days,
    evaluates directional returns, and stores historical hit rates.
    """
    logger.info("🎯 Starting out-of-sample prediction outcome resolution...")
    supabase = get_supabase_client()
    
    # 1. Pull unfulfilled rows that have matured beyond the horizon
    # (20 trading days is roughly 28 calendar days)
    cutoff_date = (datetime.utcnow() - timedelta(days=28)).isoformat()
    
    try:
        unresolved_res = supabase.table("predictions") \
            .select("*") \
            .eq("resolved", False) \
            .lt("created_at", cutoff_date) \
            .execute()
            
        unresolved_records = unresolved_res.data
        if not unresolved_records:
            logger.info("✅ No matured predictions require structural evaluation today.")
            return
            
        logger.info(f"📋 Found {len(unresolved_records)} predictions to evaluate.")
        
        for pred in unresolved_records:
            pred_id = pred["id"]
            ticker = pred["ticker"]
            entry_price = float(pred["price"])
            direction = pred["direction"]
            
            # 2. Fetch the exit realization price close 
            # Looking for the closest logged close historical price row roughly 28 calendar days later
            pred_time = datetime.fromisoformat(pred["created_at"].replace("Z", "+00:00"))
            target_exit_date = (pred_time + timedelta(days=28)).strftime("%Y-%m-%d")
            
            exit_res = supabase.table("market_structure_logs") \
                .select("latest_close, created_at") \
                .eq("ticker", ticker) \
                .gte("created_at", target_exit_date) \
                .order("created_at", desc=False) \
                .limit(1) \
                .execute()
                
            if not exit_res.data:
                # Target price historical baseline row has not been ingested yet
                continue
                
            exit_data = exit_res.data[0]
            exit_price = float(exit_data["latest_close"])
            exit_date = exit_data["created_at"]
            
            # 3. Calculate explicit quantitative outcome performance math
            return_pct = ((exit_price - entry_price) / entry_price) * 100.0
            
            correct = False
            if direction == "BULLISH" and return_pct > 0:
                correct = True
            elif direction == "BEARISH" and return_pct < 0:
                correct = True
                
            # 4. Record details directly into your tracking repository
            result_row = {
                "prediction_id": pred_id,
                "entry_date": pred["created_at"],
                "exit_date": exit_date,
                "return_pct": float(return_pct),
                "correct": bool(correct)
            }
            
            # Insert into results mapping database matrix ledger
            supabase.table("prediction_results").insert(result_row).execute()
            
            # Mark parent row flag as resolved to keep processing loops light
            supabase.table("predictions").update({"resolved": True}).eq("id", pred_id).execute()
            
            logger.info(f"   [RESOLVED] ID: {pred_id} | {ticker} | Return: {return_pct:+.2f}% | Hit: {correct}")
            
    except Exception as e:
        logger.error(f"❌ Core processing runtime failure during outcome execution: {e}")
        raise e

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_outcome_resolution()

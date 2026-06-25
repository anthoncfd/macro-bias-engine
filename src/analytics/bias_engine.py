"""
MACRO BIAS ENGINE - Core Analytics Engine
Processes trailing asset closes, handles multi-day mathematical lookbacks,
and evaluates quantitative directional momentum profiles.
Logs outputs to the 'predictions' table for trend tracking.
"""
import os
import sys
import math
import logging
import traceback
from datetime import datetime
import pandas as pd

# Ensure system path aligns with repository root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

HISTORY_DAYS = 60
SMA_WINDOW = 20
MIN_DATA_POINTS = 10

def datetime_to_date_key():
    """Generates an integer calendar primary key (YYYYMMDD) matching standard schemas."""
    return int(datetime.utcnow().strftime("%Y%m%d"))

def fetch_asset_history(ticker):
    """Fetch historical log array components safely from Supabase."""
    logger.info(f"📥 Fetching history matrix for {ticker}...")
    try:
        supabase = get_supabase_client()
        response = supabase.table("market_structure_logs") \
            .select("latest_close, created_at") \
            .eq("ticker", ticker) \
            .order("created_at", desc=True) \
            .limit(HISTORY_DAYS) \
            .execute()
        
        if not response or not response.data:
            logger.warning(f"⚠️ No historical rows located for symbol: {ticker}")
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        df['created_at'] = pd.to_datetime(df['created_at'], format='mixed')
        df = df.sort_values('created_at').reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"❌ Database error retrieving log history for {ticker}: {e}")
        return pd.DataFrame()

def calculate_bias_for_asset(ticker, live_price_override=None):
    """
    Computes real-time trend bias metrics using mathematical lookbacks
    and upserts results cleanly into the 'predictions' table layout.
    """
    try:
        supabase = get_supabase_client()
        df = fetch_asset_history(ticker)
        
        # Build raw array lists from data frames
        raw_data = df.to_dict(orient='records')

        # Append real-time override snapshot if passed explicitly by pipeline
        if live_price_override is not None:
            if not raw_data or abs(float(raw_data[-1]["latest_close"]) - float(live_price_override)) > 1e-6:
                raw_data.append({"latest_close": float(live_price_override), "created_at": datetime.utcnow()})

        if len(raw_data) < MIN_DATA_POINTS:
            raise IndexError(f"Insufficient history data points. Matrix count is {len(raw_data)}/{MIN_DATA_POINTS}")

        # Extract closing array primitives cleanly
        closes = [float(row["latest_close"]) for row in raw_data]

        # 1. Quantitative Core Calculations
        current_price = closes[-1]
        window = min(SMA_WINDOW, len(closes))
        
        # Metric A: Simple Moving Average (Baseline Tracking)
        sma_20 = sum(closes[-window:]) / window

        # Metric B: Trailing Volatility Profiles (Standard Deviation)
        variance = sum((x - sma_20) ** 2 for x in closes[-window:]) / window
        std_dev = math.sqrt(variance)

        # Metric C: Momentum Rate-of-Change Factor (Velocity Vector)
        prev_close = closes[-2] if len(closes) > 1 else current_price
        momentum_pct = ((current_price - prev_close) / prev_close) * 100

        # 2. Score Assignment Mechanics (Z-Score & Velocity Weighted Scales)
        z_score = (current_price - sma_20) / std_dev if std_dev > 0 else 0.0
        
        calculated_score = 50.0
        if current_price > sma_20 and z_score > 0.3:
            trend_signal = "BULLISH"
            calculated_score += 20.0
        elif current_price < sma_20 and z_score < -0.3:
            trend_signal = "BEARISH"
            calculated_score -= 20.0
        else:
            trend_signal = "NEUTRAL"

        # Apply volatility shifts to the analytical weight score
        calculated_score += (momentum_pct * 5.0)
        calculated_score = max(5.0, min(95.0, calculated_score))

        # Determine conviction threshold using standard deviations distance
        if std_dev == 0:
            conviction_rating = "LOW"
        else:
            deviation_distance = abs(z_score)
            if deviation_distance > 2.0:
                conviction_rating = "EXTREME"
            elif deviation_distance > 1.2:
                conviction_rating = "HIGH"
            elif deviation_distance > 0.6:
                conviction_rating = "MODERATE"
            else:
                conviction_rating = "LOW"

        # 3. Record Outputs to Central Database Using Fixed Verified Schema Mapping
        created_date_key = datetime_to_date_key()
        prediction_record = {
            "ticker": ticker,
            "created_date_key": created_date_key,
            "trend": trend_signal,
            "momentum_score": round(z_score, 2),
            "latest_close": round(current_price, 5)
        }

        # Safe upsert handling mapping structural parameters directly 
        supabase.table("predictions").upsert(
            prediction_record, 
            on_conflict="ticker,created_date_key"
        ).execute()

        logger.info(f"📝 Prediction successfully logged for {ticker}")

        return {
            "status": "SUCCESS",
            "ticker": ticker,
            "latest_close": current_price,
            "sma_20": sma_20,
            "z_score": round(z_score, 2),
            "momentum_pct": round(momentum_pct, 2),
            "direction": trend_signal,
            "probability": round(calculated_score, 1),
            "confidence": conviction_rating
        }

    except IndexError as idx_err:
        logger.warning(f"⚠️ Index limits hit processing analytics matrix for {ticker}: {idx_err}")
        return {"status": "ERROR", "message": f"Array sizing constraint: {str(idx_err)}"}

    except Exception as general_err:
        logger.error(f"💥 Internal processor calculation exception occurred for {ticker}: {str(general_err)}")
        print("\n=== RAW ENGINE MATHEMATICAL EXCEPTION TRACEBACK ===")
        traceback.print_exc()
        print("===================================================\n")
        return {"status": "ERROR", "message": str(general_err)}

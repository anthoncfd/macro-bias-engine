"""
MACRO BIAS ENGINE - Quantitative Bias Engine (V2.1 + Prediction Logging)
Calculates Z-scores, momentum, and directional biases from historical data.
Accepts live_price_override for real-time price injection.
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import ASSETS, FOREX_PAIRS

HISTORY_DAYS = 60
SMA_WINDOW = 20
MIN_DATA_POINTS = 10


def fetch_asset_history(display_name):
    """Fetch historical closing prices from Supabase for a given asset."""
    try:
        supabase = get_supabase_client()
        response = supabase.table("market_structure_logs") \
            .select("latest_close", "created_at") \
            .eq("ticker", display_name) \
            .order("created_at", desc=True) \
            .limit(HISTORY_DAYS) \
            .execute()
        
        if not response.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        df['created_at'] = pd.to_datetime(df['created_at'], format='mixed')
        df = df.sort_values('created_at').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"   ❌ Error fetching {display_name}: {e}")
        return pd.DataFrame()


def calculate_bias_for_asset(display_name, live_price_override=None):
    """
    Calculates bias metrics for a single asset.
    
    Args:
        display_name (str): Asset ticker (e.g., 'EURUSD')
        live_price_override (float, optional): Current live price (if provided)
    
    Returns:
        dict: Bias metrics with status, direction, probability, confidence, etc.
    """
    df = fetch_asset_history(display_name)
    
    if len(df) < MIN_DATA_POINTS:
        return {
            "ticker": display_name,
            "status": "INSUFFICIENT_DATA",
            "data_points": len(df),
            "message": f"Need {MIN_DATA_POINTS} instances, found {len(df)}"
        }
    
    window = min(SMA_WINDOW, len(df))
    df['sma'] = df['latest_close'].rolling(window=window).mean()
    df['std'] = df['latest_close'].rolling(window=window).std()
    
    # Use live price if provided, otherwise last close
    if live_price_override is not None:
        latest_close = float(live_price_override)
    else:
        latest_close = float(df['latest_close'].iloc[-1])
    
    latest_sma = float(df['sma'].iloc[-1])
    latest_std = float(df['std'].iloc[-1])
    
    z_score = (latest_close - latest_sma) / latest_std if latest_std and latest_std > 0 else 0.0
    prev_close = float(df['latest_close'].iloc[-2]) if len(df) > 1 else latest_close
    momentum_pct = ((latest_close - prev_close) / prev_close) * 100
    
    if latest_close > latest_sma and z_score > 0.3:
        direction = "BULLISH"
    elif latest_close < latest_sma and z_score < -0.3:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    
    raw_prob = 0.5 + (z_score * 0.15)
    probability = max(5.0, min(95.0, raw_prob * 100))
    confidence_base = 0.7 + (0.3 * min(1.0, abs(z_score) / 3.0))
    confidence = min(95.0, confidence_base * 100)
    
    result = {
        "ticker": display_name,
        "status": "SUCCESS",
        "data_points": len(df),
        "latest_close": latest_close,
        "sma_20": latest_sma,
        "z_score": round(z_score, 2),
        "momentum_pct": round(momentum_pct, 2),
        "direction": direction,
        "probability": round(probability, 1),
        "confidence": round(confidence, 1),
        "last_update": df['created_at'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S'),
        "directional_score": round(probability, 1)  # For compatibility
    }
    
    # Log prediction to Supabase (only if we have a real close, not a live override)
    if live_price_override is None:
        try:
            supabase = get_supabase_client()
            today = datetime.now().strftime("%Y-%m-%d")
            prediction_row = {
                "ticker": display_name,
                "created_date_key": today,
                "latest_close": latest_close,
                "trend": direction,
                "momentum_score": round(z_score, 2)
            }
            supabase.table("predictions") \
                .upsert(prediction_row, on_conflict="ticker,created_date_key") \
                .execute()
        except Exception as e:
            print(f"   ⚠️ Prediction insert skipped: {e}")
    
    return result


def run_bias_engine():
    """Runs the bias engine for all assets."""
    print("=" * 60)
    print("🧠 MACRO BIAS ENGINE - QUANTITATIVE ANALYSIS")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = {}
    for display_name in ASSETS.keys():
        result = calculate_bias_for_asset(display_name)
        results[display_name] = result
        
        if result.get("status") == "SUCCESS":
            price_str = f"{result['latest_close']:.4f}" if display_name in FOREX_PAIRS else f"${result['latest_close']:,.2f}"
            print(f"{display_name:8} | Price: {price_str:12} | {result['direction']:8} | Prob: {result['probability']:5.1f}% | Conf: {result['confidence']:5.1f}%")
        else:
            print(f"{display_name:8} | ❌ {result.get('message', 'No data')}")
    
    print("=" * 60)
    return results


if __name__ == "__main__":
    run_bias_engine()

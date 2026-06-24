"""
MACRO BIAS ENGINE - Quantitative Bias Engine (V2.1)
Calculates Z-scores, momentum, and directional biases from historical data.
Employs robust mixed-mode ISO timestamp parsing logic.
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
    """Fetch historical records from Supabase and parse mixed timestamp arrays safely."""
    print(f"   📥 Fetching history for {display_name}...")
    try:
        supabase = get_supabase_client()
        response = supabase.table("market_structure_logs") \
            .select("latest_close", "created_at") \
            .eq("ticker", display_name) \
            .order("created_at", desc=True) \
            .limit(HISTORY_DAYS) \
            .execute()
        
        if not response.data:
            print(f"   ⚠️ No historical data array found for {display_name}")
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        # 🔧 FIX: Hand off string conversion tasks to the flexible mixed ISO parser engine
        df['created_at'] = pd.to_datetime(df['created_at'], format='mixed', utc=True)
        
        # Sort data to build traditional chronological asset dataframes
        df = df.sort_values('created_at').reset_index(drop=True)
        print(f"   ✅ Found {len(df)} rows for {display_name}")
        return df
    except Exception as e:
        print(f"   ❌ Error fetching time series for {display_name}: {e}")
        return pd.DataFrame()

def calculate_bias_for_asset(display_name):
    """Calculates rolling quantitative momentum and directional trading biases."""
    df = fetch_asset_history(display_name)
    
    if len(df) < MIN_DATA_POINTS:
        return {
            "ticker": display_name,
            "status": "INSUFFICIENT_DATA",
            "data_points": len(df),
            "message": f"Need {MIN_DATA_POINTS} instances, found {len(df)}"
        }
    
    # Cap window size to data depth during cold starts or backfill transitions
    window = min(SMA_WINDOW, len(df))
    df['sma'] = df['latest_close'].rolling(window=window).mean()
    df['std'] = df['latest_close'].rolling(window=window).std()
    
    latest_close = float(df['latest_close'].iloc[-1])
    latest_sma = float(df['sma'].iloc[-1])
    latest_std = float(df['std'].iloc[-1])
    
    # Avoid mathematical division errors if market variance drops to absolute zero
    z_score = (latest_close - latest_sma) / latest_std if latest_std and latest_std > 0 else 0.0
    prev_close = float(df['latest_close'].iloc[-2]) if len(df) > 1 else latest_close
    momentum_pct = ((latest_close - prev_close) / prev_close) * 100
    
    # Derive structural tracking directions
    if latest_close > latest_sma and z_score > 0.3:
        direction = "BULLISH"
    elif latest_close < latest_sma and z_score < -0.3:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    
    # Project score metrics into bounded probability representations
    raw_prob = 0.5 + (z_score * 0.15)
    probability = max(5.0, min(95.0, raw_prob * 100))
    confidence_base = 0.7 + (0.3 * min(1.0, abs(z_score) / 3.0))
    confidence = min(95.0, confidence_base * 100)
    
    return {
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
        "last_update": df['created_at'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')
    }

def run_bias_engine():
    """Loops through asset definitions to run evaluation profiles."""
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

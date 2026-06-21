"""
MACRO BIAS ENGINE - Quantitative Bias Engine
Calculates Z-scores, momentum, and directional biases
from historical price data stored in Supabase.
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path dynamically
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import ASSETS, FOREX_PAIRS

# --- Configuration ---
HISTORY_DAYS = 60      # Rolling historical sample window
SMA_WINDOW = 20        # Core baseline moving average structure
MIN_DATA_POINTS = 10   # Threshold floor to eliminate fresh-start outliers

def fetch_asset_history(display_name, tickers):
    """
    Fetch historical close instances by searching for both primary 
    and fallback scraping symbols inside the database table.
    """
    print(f"   📥 Fetching historical matrix for {display_name}...")
    
    try:
        supabase = get_supabase_client()
        
        # FIX: Query using the raw tickers array (.in_) instead of the display name
        response = supabase.table("market_structure_logs") \
            .select("latest_close", "created_at", "ticker") \
            .in_("ticker", tickers) \
            .order("created_at", desc=True) \
            .limit(HISTORY_DAYS) \
            .execute()
        
        if not response.data:
            print(f"   ⚠️ No data found in ledger for {display_name}")
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        # Standardize timelines & enforce chronological sorting order
        df['created_at'] = pd.to_datetime(df['created_at'])
        df = df.sort_values('created_at').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        print(f"   ❌ Database query execution crash for {display_name}: {e}")
        return pd.DataFrame()

def calculate_bias_for_asset(display_name, tickers):
    """Calculates quantitative bias metrics for an explicit asset block."""
    df = fetch_asset_history(display_name, tickers)
    
    if len(df) < MIN_DATA_POINTS:
        return {
            "ticker": display_name,
            "status": "INSUFFICIENT_DATA",
            "data_points": len(df),
            "message": f"Need {MIN_DATA_POINTS} instances, found {len(df)}"
        }
    
    # Calculate rolling trend matrices
    window = min(SMA_WINDOW, len(df))
    df['sma'] = df['latest_close'].rolling(window=window).mean()
    df['std'] = df['latest_close'].rolling(window=window).std()
    
    latest_close = float(df['latest_close'].iloc[-1])
    latest_sma = float(df['sma'].iloc[-1])
    latest_std = float(df['std'].iloc[-1])
    
    # Calculate Z-Score: (Price - SMA) / Volatility
    z_score = (latest_close - latest_sma) / latest_std if latest_std and latest_std > 0 else 0.0
    
    # Calculate Session-to-Session Momentum
    prev_close = float(df['latest_close'].iloc[-2]) if len(df) > 1 else latest_close
    momentum_pct = ((latest_close - prev_close) / prev_close) * 100
    
    # Quant Institutional Bias Rules
    if latest_close > latest_sma and z_score > 0.3:
        direction = "BULLISH"
    elif latest_close < latest_sma and z_score < -0.3:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    
    # Map raw Z-scores gracefully to scale probabilities
    raw_prob = 0.5 + (z_score * 0.15)
    probability = max(5.0, min(95.0, raw_prob * 100))
    
    # Calculate Signal Confidence metrics
    confidence_base = 0.7 + (0.3 * (1 - min(1.0, abs(z_score) / 3.0)))
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
    """Orchestrates computational updates across all tracked portfolio models."""
    print("=" * 65)
    print("🧠 MACRO BIAS ENGINE - QUANTITATIVE ANALYSIS")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print(f"📊 Analyzing {len(ASSETS)} assets using rolling lookbacks...")
    print("-" * 65)
    
    results = {}
    
    for display_name, tickers in ASSETS.items():
        # Pass both the display name label and raw symbols list
        result = calculate_bias_for_asset(display_name, tickers)
        results[display_name] = result
        
        if result.get("status") == "SUCCESS":
            if display_name in FOREX_PAIRS:
                price_str = f"{result['latest_close']:.4f}"
                ticker_type = "FX"
            else:
                price_str = f"${result['latest_close']:,.2f}"
                ticker_type = "MACRO"
            
            print(f"{display_name:8} | {ticker_type:6} | "
                  f"Price: {price_str:10} | "
                  f"{result['direction']:8} | "
                  f"Prob: {result['probability']:5.1f}% | "
                  f"Conf: {result['confidence']:5.1f}% | "
                  f"Z: {result['z_score']:5.2f}")
        else:
            print(f"{display_name:8} | ❌ {result.get('message', 'No data available')}")
    
    print("-" * 65)
    print("✅ Bias Engine analysis loop finalized!")
    return results

if __name__ == "__main__":
    results = run_bias_engine()

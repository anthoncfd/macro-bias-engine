"""
MACRO BIAS ENGINE - Quantitative Bias Engine (V3.0 - Twelve Data Match)
Calculates statistical trend parameters directly from historical cash indexes.
"""
import os
import sys
import requests
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import ASSETS, FOREX_PAIRS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HISTORY_DAYS = 60
SMA_WINDOW = 20
MIN_DATA_POINTS = 10

# Map to pure cash spot indexes for reliable evaluation 
YAHOO_SPOT_MAP = {
    "XAUUSD": "XAUUSD=X",
    "XAGUSD": "XAGUSD=X",
}

def fetch_20_sma_from_spot_feed(display_name):
    """Extracts moving calculation averages directly from cash spot assets."""
    ticker = YAHOO_SPOT_MAP.get(display_name)
    if not ticker:
        return None, None, None
        
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=45) 
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"period1": int(start_date.timestamp()), "period2": int(end_date.timestamp()), "interval": "1d", "events": "history"}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            return None, None, None
        data = r.json()
        result = data.get("chart", {}).get("result", [None])[0]
        if not result:
            return None, None, None
            
        timestamps = result.get("timestamp", [])
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        valid = [(t, c) for t, c in zip(timestamps, closes) if t is not None and c is not None]
        
        if len(valid) < SMA_WINDOW:
            return None, None, None
            
        float_closes = [float(item[1]) for item in valid[-SMA_WINDOW:]]
        sma_20 = sum(float_closes) / len(float_closes)
        latest_close = float_closes[-1]
        latest_date = datetime.fromtimestamp(valid[-1][0], tz=timezone.utc).strftime("%Y-%m-%d")
        
        return latest_close, latest_date, round(sma_20, 2)
    except Exception as e:
        logger.warning(f"Spot metric fallback query engine error for {display_name}: {e}")
        return None, None, None

def fetch_asset_history(display_name):
    """Retrieve verified asset log trends directly from Supabase DB blocks."""
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
        logger.error(f"❌ Error recovering history tables for {display_name}: {e}")
        return pd.DataFrame()

def calculate_bias_for_asset(display_name):
    """Evaluates cross-asset directional bias metrics cleanly."""
    if display_name in ["XAUUSD", "XAGUSD"]:
        latest_close, latest_date, sma_20 = fetch_20_sma_from_spot_feed(display_name)
        if latest_close is not None and sma_20 is not None:
            df = fetch_asset_history(display_name)
            if len(df) < MIN_DATA_POINTS:
                return {"ticker": display_name, "status": "INSUFFICIENT_DATA", "message": f"Need {MIN_DATA_POINTS} database records for processing."}
            
            history_closes = df['latest_close'].tolist()
            last_db_date = df['created_at'].iloc[-1].strftime('%Y-%m-%d') if not df.empty else latest_date
            
            if last_db_date == latest_date:
                prev_close = float(history_closes[-2]) if len(history_closes) > 1 else latest_close
                std_window = history_closes[-SMA_WINDOW:]
            else:
                prev_close = float(history_closes[-1]) if history_closes else latest_close
                std_window = (history_closes + [latest_close])[-SMA_WINDOW:]
                
            latest_std = float(np.std(std_window)) if len(std_window) > 0 else 0.0
            z_score = (latest_close - sma_20) / latest_std if latest_std > 0 else 0.0
            momentum_pct = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0
            
            if latest_close > sma_20 and z_score > 0.3:
                direction = "BULLISH"
            elif latest_close < sma_20 and z_score < -0.3:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
                
            raw_prob = 0.5 + (z_score * 0.15)
            probability = max(5.0, min(95.0, raw_prob * 100))
            confidence = min(95.0, (0.7 + (0.3 * min(1.0, abs(z_score) / 3.0))) * 100)
            
            return {
                "ticker": display_name, "status": "SUCCESS", "latest_close": latest_close,
                "sma_20": sma_20, "z_score": round(z_score, 2), "momentum_pct": round(momentum_pct, 2),
                "direction": direction, "probability": round(probability, 1), "confidence": round(confidence, 1)
            }

    # ─── Standard Database Pipeline Processing Path ──────────────────────────
    df = fetch_asset_history(display_name)
    if len(df) < MIN_DATA_POINTS:
        return {"ticker": display_name, "status": "INSUFFICIENT_DATA", "message": f"Target entries missing. Had {len(df)} points."}
        
    window = min(SMA_WINDOW, len(df))
    df['sma'] = df['latest_close'].rolling(window=window).mean()
    df['std'] = df['latest_close'].rolling(window=window).std()
    
    latest_close = float(df['latest_close'].iloc[-1])
    latest_sma = float(df['sma'].iloc[-1])
    latest_std = float(df['std'].iloc[-1])
    
    z_score = (latest_close - latest_sma) / latest_std if latest_std and latest_std > 0 else 0.0
    prev_close = float(df['latest_close'].iloc[-2]) if len(df) > 1 else latest_close
    momentum_pct = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0
    
    if latest_close > latest_sma and z_score > 0.3:
        direction = "BULLISH"
    elif latest_close < latest_sma and z_score < -0.3:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
        
    raw_prob = 0.5 + (z_score * 0.15)
    probability = max(5.0, min(95.0, raw_prob * 100))
    confidence = min(95.0, (0.7 + (0.3 * min(1.0, abs(z_score) / 3.0))) * 100)
    
    return {
        "ticker": display_name, "status": "SUCCESS", "latest_close": latest_close,
        "sma_20": latest_sma, "z_score": round(z_score, 2), "momentum_pct": round(momentum_pct, 2),
        "direction": direction, "probability": round(probability, 1), "confidence": round(confidence, 1)
    }

def run_bias_engine():
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
            print(f"{display_name:8} | ❌ {result.get('message', 'Processing error')}")
    print("=" * 60)
    return results

if __name__ == "__main__":
    run_bias_engine()

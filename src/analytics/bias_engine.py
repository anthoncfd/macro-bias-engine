"""
MACRO BIAS ENGINE - Quantitative Bias Engine (V2.1)
Primary: Uses TradingView chart API for XAUUSD/XAGUSD close & SMA.
Fallback: Uses Supabase historical data (spot-based after backfill).
Other assets: use Supabase.
"""
import os
import sys
import requests
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone

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

TV_EXCHANGE_MAP = {
    "XAUUSD": "OANDA",
    "XAGUSD": "OANDA",
}

def fetch_20_sma_from_tradingview(symbol="XAUUSD", exchange="OANDA"):
    """Fetch latest close, date, and 20‑SMA from TradingView public chart API."""
    tv_ticker = f"{exchange.upper()}:{symbol.upper()}"
    url = "https://chartapi.tradingview.com/v1/history"
    params = {"symbol": tv_ticker, "resolution": "D", "count": 40}
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tradingview.com/"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return None, None, None
        data = r.json()
        timestamps = data.get("t", [])
        closes = data.get("c", [])
        if len(closes) < 20:
            return None, None, None
        float_closes = [float(p) for p in closes[-20:]]
        sma_20 = sum(float_closes) / len(float_closes)
        latest_close = float_closes[-1]
        latest_date = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc).strftime("%Y-%m-%d")
        return latest_close, latest_date, round(sma_20, 2)
    except Exception as e:
        logger.warning(f"TradingView fetch error: {e}")
        return None, None, None

def fetch_asset_history(display_name):
    """Fetch historical closes from Supabase."""
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
        logger.error(f"❌ Error fetching {display_name}: {e}")
        return pd.DataFrame()

def calculate_bias_for_asset(display_name):
    """Calculate bias using TradingView for metals, fallback to Supabase."""
    # Try TradingView for metals
    if display_name in ["XAUUSD", "XAGUSD"]:
        exchange = TV_EXCHANGE_MAP.get(display_name, "OANDA")
        latest_close, latest_date, sma_20 = fetch_20_sma_from_tradingview(display_name, exchange)
        if latest_close is not None and sma_20 is not None:
            # TradingView succeeded – use it, but still need std from history
            df = fetch_asset_history(display_name)
            if len(df) < MIN_DATA_POINTS:
                return {
                    "ticker": display_name,
                    "status": "INSUFFICIENT_DATA",
                    "data_points": len(df),
                    "message": f"Need {MIN_DATA_POINTS} history points for Z-Score."
                }
            history_closes = df['latest_close'].tolist()
            last_db_date = df['created_at'].iloc[-1].strftime('%Y-%m-%d')
            if last_db_date == latest_date:
                prev_close = float(history_closes[-2]) if len(history_closes) > 1 else latest_close
                std_window = history_closes[-SMA_WINDOW:]
            else:
                prev_close = float(history_closes[-1])
                std_window = (history_closes + [latest_close])[-SMA_WINDOW:]
            latest_std = float(np.std(std_window)) if len(std_window) > 0 else 0.0
            z_score = (latest_close - sma_20) / latest_std if latest_std > 0 else 0.0
            momentum_pct = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0
            
            # Direction logic
            if latest_close > sma_20 and z_score > 0.3:
                direction = "BULLISH"
            elif latest_close < sma_20 and z_score < -0.3:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
            raw_prob = 0.5 + (z_score * 0.15)
            probability = max(5.0, min(95.0, raw_prob * 100))
            confidence_base = 0.7 + (0.3 * min(1.0, abs(z_score) / 3.0))
            confidence = min(95.0, confidence_base * 100)
            return {
                "ticker": display_name,
                "status": "SUCCESS",
                "data_points": len(df),
                "latest_close": latest_close,
                "sma_20": sma_20,
                "z_score": round(z_score, 2),
                "momentum_pct": round(momentum_pct, 2),
                "direction": direction,
                "probability": round(probability, 1),
                "confidence": round(confidence, 1),
                "last_update": latest_date
            }
        else:
            # TradingView failed → fallback to Supabase
            logger.warning(f"TradingView failed for {display_name}, falling back to Supabase.")

    # ─── Common Supabase path (for non‑metals or fallback) ──────────
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

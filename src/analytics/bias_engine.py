"""
MACRO BIAS ENGINE - Core Quant Analytics
Calculates mathematically sound directional probabilities using proper distribution functions
and registers predictions into the Supabase verification ledger.
"""
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import norm
from src.database.supabase_client import get_supabase_client

def calculate_bias_for_asset(ticker):
    """
    Evaluates trend distribution to map exact statistical direction probabilities.
    Replaces synthetic heuristics with standard normal curve mapping.
    """
    try:
        if ticker in ["DXY", "VIX", "US10Y"]:
            return {"status": "SKIP", "message": "Benchmark anchor asset."}

        supabase = get_supabase_client()

        # Gather price snapshots
        res = supabase.table("market_structure_logs") \
            .select("*").eq("ticker", ticker).order("created_at", desc=True).limit(35).execute()
            
        if not res.data or len(res.data) < 20:
            return {"status": "ERROR", "message": f"Insufficient database rows historical tracking sample."}

        df = pd.DataFrame(res.data).iloc[::-1].reset_index(drop=True)
        prices = df["latest_close"].astype(float).values
        
        current_price = prices[-1]
        sma_20 = np.mean(prices[-20:])
        std_20 = np.std(prices[-20:])
        z_score = (current_price - sma_20) / std_20 if std_20 > 0 else 0.0
        momentum_pct = ((prices[-1] - prices[-2]) / prices[-2]) * 100

        # Normal Cumulative Distribution Function (CDF) mapping
        if z_score < 0:
            direction = "BEARISH"
            probability = norm.cdf(-z_score) * 100
        elif z_score > 0:
            direction = "BULLISH"
            probability = norm.cdf(z_score) * 100
        else:
            direction = "NEUTRAL"
            probability = 50.0

        # Signal Strength calculated as standard deviation distance profile
        signal_strength = min((abs(z_score) / 2.5) * 100, 100.0)

        # Log to permanent verification ledger table
        prediction_row = {
            "ticker": ticker,
            "price": float(current_price),
            "sma_20": float(sma_20),
            "z_score": float(z_score),
            "momentum_pct": float(momentum_pct),
            "direction": direction,
            "probability": float(probability),
            "signal_strength": float(signal_strength)
        }
        
        try:
            supabase.table("predictions").insert(prediction_row).execute()
        except Exception as log_error:
            print(f"   ⚠️ Non-blocking logging failure to predictions table for {ticker}: {log_error}")

        return {
            "status": "SUCCESS",
            "ticker": ticker,
            "latest_close": current_price,
            "sma_20": sma_20,
            "z_score": z_score,
            "momentum_pct": momentum_pct,
            "direction": direction,
            "probability": probability,
            "signal_strength": signal_strength,
            "last_update": df["created_at"].iloc[-1]
        }
    except Exception as e:
        return {"status": "CRASH", "message": str(e)}

def run_bias_engine():
    """Loops through tracking targets to map profiles."""
    from src.ingestion.market_prices import ASSETS
    results = {}
    for ticker in ASSETS.keys():
        metrics = calculate_bias_for_asset(ticker)
        if metrics.get("status") == "SUCCESS":
            results[ticker] = metrics
    return results

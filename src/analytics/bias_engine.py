"""
MACRO BIAS ENGINE - Core Quant Analytics
Calculates empirical asset distribution parameters using rolling data windows.
Eliminates synthetic constants by utilizing true historical percentile rankings.
"""
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import norm
from src.database.supabase_client import get_supabase_client

def calculate_bias_for_asset(ticker):
    """
    Evaluates historical trend sequences to derive real-world percentile metrics.
    Replaces uncalibrated 'Probabilities' with empirical Directional Scores.
    """
    try:
        if ticker in ["DXY", "VIX", "US10Y"]:
            return {"status": "SKIP", "message": "Benchmark anchor asset."}

        supabase = get_supabase_client()

        # 1. Fetch historical series data
        res = supabase.table("market_structure_logs") \
            .select("*").eq("ticker", ticker).order("created_at", desc=True).limit(35).execute()
            
        if not res.data or len(res.data) < 20:
            return {"status": "ERROR", "message": "Insufficient historical tracking rows."}

        df = pd.DataFrame(res.data).iloc[::-1].reset_index(drop=True)
        prices = df["latest_close"].astype(float).values
        
        current_price = prices[-1]
        
        # Calculate trailing 20-day baseline metrics
        rolling_sample = prices[-20:]
        sma_20 = np.mean(rolling_sample)
        std_20 = np.std(rolling_sample)
        z_score = (current_price - sma_20) / std_20 if std_20 > 0 else 0.0
        momentum_pct = ((prices[-1] - prices[-2]) / prices[-2]) * 100

        # 2. Historical Contextualization (Eliminating Magic 0.5 and 2.5 Numbers)
        # Compute all rolling 20-day Z-scores in our sample window to find true empirical position
        historical_z_scores = []
        for i in range(20, len(prices) + 1):
            window = prices[i-20:i]
            window_mean = np.mean(window)
            window_std = np.std(window)
            if window_std > 0:
                historical_z_scores.append((window[-1] - window_mean) / window_std)
        
        if not historical_z_scores:
            historical_z_scores = [z_score]

        # Determine exact empirical percentile rank of the current absolute Z-score
        abs_historical = np.abs(historical_z_scores)
        abs_current = abs(z_score)
        signal_strength = (np.sum(abs_historical <= abs_current) / len(abs_historical)) * 100.0

        # Pass through a standard logistic activation layer to form a bounded Directional Score
        # This explicitly tells an end user the magnitude of trend alignment, NOT a win rate.
        directional_score = 100 / (1 + np.exp(-z_score))

        if z_score < 0:
            direction = "BEARISH"
        elif z_score > 0:
            direction = "BULLISH"
        else:
            direction = "NEUTRAL"

        # 3. Structural Conviction Mapping derived entirely from Empirical Percentiles
        if signal_strength < 35.0:
            conviction = "LOW"
        elif 35.0 <= signal_strength < 70.0:
            conviction = "MODERATE"
        elif 70.0 <= signal_strength < 90.0:
            conviction = "HIGH"
        else:
            conviction = "EXTREME (MEAN REVERSION RISK)"

        # 4. Anti-Contamination Logging (Problem #4): Prevent Multiple User Queries from Spamming Records
        today_string = datetime.utcnow().strftime("%Y-%m-%d")
        
        # We enforce uniqueness by targeting combinations of Ticker and Ingestion Date
        prediction_row = {
            "ticker": ticker,
            "price": float(current_price),
            "sma_20": float(sma_20),
            "z_score": float(z_score),
            "momentum_pct": float(momentum_pct),
            "direction": direction,
            "probability": float(directional_score),  # Map to database schema legacy column name safely
            "signal_strength": float(signal_strength),
            "conviction": conviction,
            "created_date_key": today_string  # Unique constraint binding anchor
        }
        
        try:
            # Use an upsert execution using your unique key definition to update rather than duplicate
            supabase.table("predictions").upsert(
                prediction_row, on_conflict="ticker,created_date_key"
            ).execute()
        except Exception as log_error:
            print(f"   ⚠️ Non-blocking database logging failure: {log_error}")

        return {
            "status": "SUCCESS",
            "ticker": ticker,
            "latest_close": current_price,
            "sma_20": sma_20,
            "z_score": z_score,
            "momentum_pct": momentum_pct,
            "direction": direction,
            "directional_score": directional_score,
            "signal_strength": signal_strength,
            "conviction": conviction,
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

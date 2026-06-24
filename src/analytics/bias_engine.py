"""
MACRO BIAS ENGINE - Core Quant Analytics
Calculates mathematically unified, standardized distribution vectors 
utilizing real-time price injections to ensure up-to-the-second analytical precision.
"""
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import norm
from src.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

def calculate_bias_for_asset(ticker, live_price_override=None):
    """
    Unified real-time statistical engine block.
    Appends live OTC prices to trailing historical data frames to guarantee
    mathematical accuracy during high-volatility structural expansion events.
    """
    try:
        if ticker in ["DXY", "VIX", "US10Y"]:
            return {"status": "SKIP", "message": "Benchmark anchor asset."}

        supabase = get_supabase_client()

        # 1. Pull trailing 19 records from history (leaving slot 20 for real-time live data)
        res = supabase.table("market_structure_logs") \
            .select("latest_close, created_at") \
            .eq("ticker", ticker) \
            .order("created_at", desc=True) \
            .limit(19).execute()
            
        if not res.data or len(res.data) < 19:
            return {"status": "ERROR", "message": f"Incomplete baseline historical arrays for {ticker}."}

        # Invert data frame stack to chronologically linear order (oldest to newest)
        df = pd.DataFrame(res.data).iloc[::-1].reset_index(drop=True)
        historical_prices = df["latest_close"].astype(float).tolist()

        # 2. Process real-time price injection parameters
        if live_price_override is not None:
            current_price = float(live_price_override)
            logger_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
        else:
            # Safe runtime fallback if live price feed component drops
            current_price = historical_prices[-1]
            logger_timestamp = df["created_at"].iloc[-1]
            logger.warning(f"⚠️ Live price override missing for {ticker}. Falling back to database snapshot.")

        # 3. Form a mathematically unified 20-day window matrix
        complete_window = np.array(historical_prices + [current_price])

        # Compute rolling parameters against the dynamic real-time dataset
        sma_20 = np.mean(complete_window)
        std_20 = np.std(complete_window)
        z_score = (current_price - sma_20) / std_20 if std_20 > 0 else 0.0
        
        # Calculate true momentum velocity against yesterday's actual settled close price
        momentum_pct = ((current_price - historical_prices[-1]) / historical_prices[-1]) * 100

        # 4. Bounded Directional Score Matrix (Logistic Activation Curve Mapping)
        directional_score = 100 / (1 + np.exp(-z_score))

        if z_score < 0:
            direction = "BEARISH"
        elif z_score > 0:
            direction = "BULLISH"
        else:
            direction = "NEUTRAL"

        # 5. Mathematically Unified Signal Strength (Standard Gaussian Curve Coverage)
        abs_z = abs(z_score)
        signal_strength = (2 * norm.cdf(abs_z) - 1) * 100.0

        # 6. Standard Institutional Sigma Band Conviction Routing
        if abs_z < 1.0:
            conviction = "LOW (TREND NOISE)"
        elif 1.0 <= abs_z < 2.0:
            conviction = "MODERATE (DEVELOPING TREND)"
        elif 2.0 <= abs_z < 3.0:
            conviction = "HIGH (EXTENDED DISTRIBUTION)"
        else:
            conviction = "EXTREME (MEAN REVERSION RISK)"

        # 7. Prevent Duplicate Daily Writes via Unique Idempotent Constraint Keys
        today_string = datetime.utcnow().strftime("%Y-%m-%d")
        prediction_row = {
            "ticker": ticker,
            "price": float(current_price),
            "sma_20": float(sma_20),
            "z_score": float(z_score),
            "momentum_pct": float(momentum_pct),
            "direction": direction,
            "probability": float(directional_score), # Retains compatibility with your legacy schema column naming
            "signal_strength": float(signal_strength),
            "conviction": conviction,
            "created_date_key": today_string
        }
        
        try:
            supabase.table("predictions").upsert(
                prediction_row, on_conflict="ticker,created_date_key"
            ).execute()
        except Exception as log_error:
            logger.error(f"⚠️ Non-blocking database ledger logging failure: {log_error}")

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
            "last_update": logger_timestamp
        }
    except Exception as e:
        logger.error(f"💥 Core calculation crash on asset {ticker}: {e}")
        return {"status": "CRASH", "message": str(e)}

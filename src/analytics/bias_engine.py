"""
MACRO BIAS ENGINE - Core Analytics Engine
Processes trailing asset closes, handles multi-day mathematical lookbacks,
and evaluates quantitative directional momentum profiles with error safety rails.
"""
import logging
import math
import traceback
from src.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

def calculate_bias_for_asset(ticker, live_price_override=None):
    """
    Computes real-time trend bias metrics using a 20-period matrix.
    Safely catches array depth constraints and updates the predictions ledger table.
    """
    try:
        supabase = get_supabase_client()

        # 1. Pull the 20 most recent logs to satisfy the quantitative tracking matrix
        res = supabase.table("market_structure_logs") \
            .select("latest_close, created_at") \
            .eq("ticker", ticker) \
            .order("created_at", desc=True) \
            .limit(20) \
            .execute()

        raw_data = res.data if res and res.data else []

        # 2. Append real-time override snapshot string if passed explicitly by pipeline
        if live_price_override is not None:
            # Avoid inserting duplicate metrics if today's record already loaded
            if not raw_data or abs(float(raw_data[0]["latest_close"]) - float(live_price_override)) > 1e-6:
                raw_data.insert(0, {"latest_close": float(live_price_override)})

        if len(raw_data) < 20:
            raise IndexError(f"Insufficient history data points. Matrix count is {len(raw_data)}/20")

        # 3. CRITICAL: Reverse array back to chronological ascending order (past -> present)
        # This keeps sliding range windows index-accurate for momentum analysis
        raw_data.reverse()

        # 4. Extract and force float primitives cleanly
        closes = [float(row["latest_close"]) for row in raw_data]

        # 5. Core Analytical Sequences
        current_price = closes[-1]
        prior_close = closes[-2]

        # Indicator A: Simple Moving Average (20-Period Baseline Tracking)
        sma_20 = sum(closes[-20:]) / 20

        # Indicator B: Historical Volatility Matrix (Standard Deviation over 14-Periods)
        sma_14 = sum(closes[-14:]) / 14
        variance = sum((x - sma_14) ** 2 for x in closes[-14:]) / 14
        std_dev = math.sqrt(variance)

        # Indicator C: Momentum Rate-of-Change Factor (5-Period Velocity Vector)
        lookback_price_5d = closes[-5]
        momentum_factor = ((current_price - lookback_price_5d) / lookback_price_5d) * 100

        # 6. Unified Directional Bias Scoring Model (0 to 100 Matrix Scales)
        # Base matrix rests at equilibrium midpoint (50)
        directional_score = 50.0

        # Apply trend component shifts
        if current_price > sma_20:
            directional_score += 15.0  # Bullish expansion tier
        else:
            directional_score -= 15.0  # Bearish distribution tier

        # Apply short-term velocity adjustments 
        directional_score += (momentum_factor * 10.0)
        directional_score = max(0.0, min(100.0, directional_score)) # Keep clamped within standard limits

        # 7. Map Classification Bands & Standard Deviation Conviction Thresholds
        if directional_score >= 70:
            trend_signal = "BULLISH"
        elif directional_score <= 30:
            trend_signal = "BEARISH"
        else:
            trend_signal = "NEUTRAL"

        # Determine conviction weight using volatility deviations
        if std_dev == 0:
            conviction_rating = "LOW"
        else:
            deviation_distance = abs(current_price - sma_14) / std_dev
            if deviation_distance > 2.0:
                conviction_rating = "EXTREME"
            elif deviation_distance > 1.2:
                conviction_rating = "HIGH"
            elif deviation_distance > 0.6:
                conviction_rating = "MODERATE"
            else:
                conviction_rating = "LOW"

        # 8. Record Outputs to Central Cloud Analytics Database Table
        created_date_key = datetime_to_date_key()
        prediction_record = {
            "ticker": ticker,
            "created_date_key": created_date_key,
            "directional_score": round(directional_score, 2),
            "trend": trend_signal,
            "conviction": conviction_rating,
            "latest_close": current_price
        }

        # Safe upsert mapping using table primary key constraints
        supabase.table("predictions").upsert(
            prediction_record, 
            on_conflict="ticker,created_date_key"
        ).execute()

        return {
            "status": "SUCCESS",
            "ticker": ticker,
            "directional_score": directional_score,
            "trend": trend_signal,
            "conviction": conviction_rating
        }

    except IndexError as idx_err:
        logger.warning(f"⚠️ Index limits hit processing analytics matrix for {ticker}: {idx_err}")
        return {"status": "ERROR", "message": f"Array sizing index constraint: {str(idx_err)}"}

    except ZeroDivisionError:
        logger.warning(f"⚠️ Flatline division constraint detected on asset calculation sequence: {ticker}")
        return {"status": "ERROR", "message": "Zero division encountered inside velocity formula scale."}

    except Exception as general_err:
        logger.error(f"💥 Internal processor calculation exception occurred for {ticker}: {str(general_err)}")
        print("\n=== RAW ENGINE MATHEMATICAL EXCEPTION TRACEBACK ===")
        traceback.print_exc()
        print("===================================================\n")
        return {"status": "ERROR", "message": str(general_err)}


def datetime_to_date_key():
    """Generates an integer calendar primary key string matching standard database schemas."""
    from datetime import datetime
    return int(datetime.utcnow().strftime("%Y%m%d"))

"""
MACRO BIAS ENGINE - Analytical Processing Core
Refactored to eliminate metric logic flaws and introduce a multi-factor macro framework.
"""
import numpy as np
import pandas as pd
from datetime import datetime
from src.database.supabase_client import get_supabase_client

def calculate_bias_for_asset(ticker):
    """
    Evaluates multi-factor structural directional profiles for a target asset.
    Cross-references localized metrics against global macro regime anchors (DXY, VIX, US10Y).
    """
    try:
        # Macro indicators are input drivers, not assets themselves
        if ticker in ["DXY", "VIX", "US10Y"]:
            return {"status": "SKIP", "message": "Systemic benchmark anchor asset."}

        supabase = get_supabase_client()

        # 1. Gather Historical Target Sequence Arrays
        res = supabase.table("market_structure_logs") \
            .select("*").eq("ticker", ticker).order("created_at", desc=True).limit(35).execute()
            
        if not res.data or len(res.data) < 20:
            return {"status": "ERROR", "message": f"Insufficient historical tracking row sample ({len(res.data) if res.data else 0}/20)."}

        df = pd.DataFrame(res.data).iloc[::-1].reset_index(drop=True)
        prices = df["latest_close"].astype(float).values
        
        current_price = prices[-1]
        sma_20 = np.mean(prices[-20:])
        std_20 = np.std(prices[-20:])
        z_score = (current_price - sma_20) / std_20 if std_20 > 0 else 0.0
        momentum_pct = ((prices[-1] - prices[-2]) / prices[-2]) * 100

        # 2. Extract Cross-Asset Macro Variables
        macro_anchors = ["DXY", "VIX", "US10Y"]
        macro_states = {}
        
        for m_ticker in macro_anchors:
            m_res = supabase.table("market_structure_logs") \
                .select("latest_close").eq("ticker", m_ticker).order("created_at", desc=True).limit(2).execute()
            if m_res.data and len(m_res.data) >= 2:
                macro_states[m_ticker] = "RISING" if float(m_res.data[0]["latest_close"]) > float(m_res.data[1]["latest_close"]) else "FALLING"
            else:
                macro_states[m_ticker] = "NEUTRAL"

        # 3. Intermarket Scoring Architecture Matrix
        # +1 weights Bullish bias, -1 weights Bearish bias
        confluence_votes = []

        # Feature Set A: Local Structural Position
        confluence_votes.append(1 if current_price > sma_20 else -1)
        confluence_votes.append(1 if momentum_pct > 0 else -1)
        
        # Feature Set B: Global DXY Liquid Currency Regime
        if macro_states.get("DXY") == "RISING":
            # Stronger dollar pressures foreign FX pairs and precious metals
            confluence_votes.append(-1 if ticker in ["EURUSD", "GBPUSD", "AUDUSD", "XAUUSD", "XAGUSD", "BTCUSD"] else 1)
        else:
            confluence_votes.append(1 if ticker in ["EURUSD", "GBPUSD", "AUDUSD", "XAUUSD", "XAGUSD", "BTCUSD"] else -1)

        # Feature Set C: Volatility Safe-Haven Regime
        if macro_states.get("VIX") == "RISING":
            # High risk off environment drops high-beta equities and crypto assets
            confluence_votes.append(-1 if ticker in ["US30", "JP225", "BTCUSD"] else 1)
        else:
            confluence_votes.append(1 if ticker in ["US30", "JP225", "BTCUSD"] else -1)

        # Feature Set D: Treasury Rate Divergence Matrix
        if macro_states.get("US10Y") == "RISING":
            # Higher yields increase cost of carry, undermining non-yielding assets
            confluence_votes.append(-1 if ticker in ["XAUUSD", "BTCUSD"] else 0)

        # 4. Calibrate Coherent Math Profiles (Resolves logical contradictions)
        total_votes = len([v for v in confluence_votes if v != 0])
        bullish_count = sum(1 for v in confluence_votes if v == 1)
        bearish_count = sum(1 for v in confluence_votes if v == -1)
        
        if bullish_count > bearish_count:
            direction = "BULLISH"
            probability = (bullish_count / total_votes) * 100
        elif bearish_count > bullish_count:
            direction = "BEARISH"
            probability = (bearish_count / total_votes) * 100
        else:
            direction = "NEUTRAL"
            probability = 50.0

        # Confidence Calculation: Quantifies structural stability vs tail risk extension.
        # Highly extended boundaries lower confidence to flag trend exhaustion risks.
        max_normal_deviation = 2.5
        volatility_extension = min(abs(z_score) / max_normal_deviation, 1.0)
        confidence = (1.0 - (volatility_extension * 0.35)) * 100

        return {
            "status": "SUCCESS",
            "ticker": ticker,
            "latest_close": current_price,
            "sma_20": sma_20,
            "z_score": z_score,
            "momentum_pct": momentum_pct,
            "direction": direction,
            "probability": probability,   # Confluence Factor Agreement %
            "confidence": confidence,     # Trend Structural Stability %
            "last_update": df["created_at"].iloc[-1]
        }
    except Exception as e:
        return {"status": "CRASH", "message": str(e)}

def run_bias_engine():
    """Orchestrates computational engine maps over all valid active assets."""
    from src.ingestion.market_prices import ASSETS
    results = {}
    for ticker in ASSETS.keys():
        metrics = calculate_bias_for_asset(ticker)
        if metrics.get("status") == "SUCCESS":
            results[ticker] = metrics
    return results

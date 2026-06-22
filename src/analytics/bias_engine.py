"""
MACRO BIAS ENGINE - Quantitative & Fundamental Hybrid Engine
Calculates technical Z-scores, rolling SMAs, and intercepts real-time 
macroeconomic news data deviations to produce high-fidelity confluence vectors.
"""
import os
import sys
import requests
import pandas as pd
import numpy as np
from datetime import datetime, date

# Safe absolute path resolution regardless of orchestrator execution root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import ASSETS, FOREX_PAIRS

# --- Configuration ---
HISTORY_DAYS = 60
SMA_WINDOW = 20
MIN_DATA_POINTS = 10
FMP_API_KEY = os.environ.get("FMP_API_KEY")
HIGH_IMPACT_KEYWORDS = ["CPI", "FOMC", "INTEREST RATE", "NON FARM PAYROLL", "UNEMPLOYMENT RATE", "FED RATE", "GDP"]

# --- Macro Ingestion & Normalization Core ---

def parse_clean_float(value):
    """Safely extracts numeric values from string economic metrics (e.g., '3.2%', '250K')."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        clean_str = str(value).replace('%', '').replace('K', '').replace('M', '').replace('B', '').strip()
        return float(clean_str)
    except ValueError:
        return None

def get_today_macro_vectors():
    """
    Fetches daily high-impact fundamental deviations.
    Returns: Dict mapping Currency -> 'BULLISH' | 'BEARISH' | 'PENDING'
    """
    vectors = {}
    if not FMP_API_KEY:
        return vectors
        
    today_str = date.today().strftime("%Y-%m-%d")
    url = f"https://financialmodelingprep.com/api/v3/economic_calendar?from={today_str}&to={today_str}&apikey={FMP_API_KEY}"
    
    try:
        response = requests.get(url, timeout=8).json()
        if not isinstance(response, list):
            return vectors
            
        for event in response:
            event_name = event.get("event", "")
            impact = event.get("impact", "").upper()
            currency = event.get("currency", "").upper()
            
            if not currency:
                continue
                
            is_high_impact = impact == "HIGH" or any(kw in event_name.upper() for kw in HIGH_IMPACT_KEYWORDS)
            if not is_high_impact:
                continue
                
            actual_raw = event.get("actual")
            forecast_raw = event.get("forecast")
            
            if actual_raw is None or str(actual_raw).strip() == "":
                if currency not in vectors:
                    vectors[currency] = "PENDING"
                continue
                
            actual = parse_clean_float(actual_raw)
            forecast = parse_clean_float(forecast_raw)
            
            if actual is None or forecast is None:
                continue
                
            deviation = actual - forecast
            if abs(deviation) < 0.001:
                continue
                
            name = event_name.upper()
            if "UNEMPLOYMENT" in name or "JOBLESS CLAIMS" in name:
                vector = "BEARISH" if deviation > 0 else "BULLISH"
            else:
                vector = "BULLISH" if deviation > 0 else "BEARISH"
                
            vectors[currency] = vector
    except Exception as e:
        print(f"   ⚠️ Fundamental stream lookup bypass: {e}")
        
    return vectors

# --- Main Analytical Processing Block ---

def calculate_bias_for_asset(display_name, tickers, macro_vectors):
    df = fetch_asset_history(display_name, tickers)
    if len(df) < MIN_DATA_POINTS:
        return {
            "ticker": display_name, 
            "status": "INSUFFICIENT_DATA", 
            "data_points": len(df), 
            "message": f"Need {MIN_DATA_POINTS}, found {len(df)}"
        }
        
    window = min(SMA_WINDOW, len(df))
    df['sma'] = df['latest_close'].rolling(window=window).mean()
    df['std'] = df['latest_close'].rolling(window=window).std()
    
    latest_close = float(df['latest_close'].iloc[-1])
    latest_sma = float(df['sma'].iloc[-1])
    latest_std = float(df['std'].iloc[-1])
    
    z_score = (latest_close - latest_sma) / latest_std if latest_std and latest_std > 0 else 0.0
    
    prev_close = float(df['latest_close'].iloc[-2]) if len(df) > 1 else latest_close
    momentum_pct = ((latest_close - prev_close) / prev_close) * 100
    
    # 1. Pure Technical Assignment Rule
    if latest_close > latest_sma and z_score > 0.3:
        tech_direction = "BULLISH"
    elif latest_close < latest_sma and z_score < -0.3:
        tech_direction = "BEARISH"
    else:
        tech_direction = "NEUTRAL"
        
    # 2. Extract Matching Fundamental Context
    applicable_currency = None
    if display_name in ["XAUUSD", "XAGUSD", "BTCUSD", "US30"]:
        applicable_currency = "USD"
    else:
        for curr in ["EUR", "GBP", "AUD", "JPY", "CAD", "CHF"]:
            if display_name.startswith(curr):
                applicable_currency = curr
                break
                
    fund_direction = "NEUTRAL"
    if applicable_currency and applicable_currency in macro_vectors:
        fund_direction = macro_vectors[applicable_currency]
        if applicable_currency == "USD" and display_name in ["XAUUSD", "XAGUSD", "BTCUSD", "US30"]:
            if fund_direction == "BULLISH": fund_direction = "BEARISH"
            elif fund_direction == "BEARISH": fund_direction = "BULLISH"

    # 3. Hybrid Integration Ruleset (Confluence Logic Matrix)
    if fund_direction == "PENDING":
        final_direction = "⚠️ PAUSE"
    elif fund_direction == "NEUTRAL":
        final_direction = tech_direction
    elif tech_direction == fund_direction:
        final_direction = f"💎 STRONG {tech_direction}"
    else:
        final_direction = f"⚡ DIVERGENCE ({tech_direction})"
        
    raw_prob = 0.5 + (z_score * 0.15)
    probability = max(5.0, min(95.0, raw_prob * 100))
    
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
        "direction": final_direction,
        "probability": round(probability, 1),
        "confidence": round(confidence, 1),
        "last_update": df['created_at'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')
    }

def fetch_asset_history(display_name, tickers):
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
        df['created_at'] = pd.to_datetime(df['created_at'], format='ISO8601', utc=True)
        df = df.sort_values('created_at').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"   ❌ Database query crash: {e}")
        return pd.DataFrame()

def run_bias_engine():
    """Orchestrates computational updates across all tracked portfolio models."""
    print("=" * 65)
    print("🧠 HYBRID BIAS ENGINE - INSTITUTIONAL DATA INTERCEPT")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    
    macro_vectors = get_today_macro_vectors()
    print(f"📊 Active Fundamental Deviations Map: {macro_vectors}")
    print(f"📊 Analyzing {len(ASSETS)} assets...")
    print("-" * 65)
    
    results = {}
    for display_name, tickers in ASSETS.items():
        result = calculate_bias_for_asset(display_name, tickers, macro_vectors)
        results[display_name] = result
        
        if result.get("status") == "SUCCESS":
            price_str = f"{result['latest_close']:.4f}" if display_name in FOREX_PAIRS else f"${result['latest_close']:,.2f}"
            print(f"{display_name:8} | Price: {price_str:10} | Matrix Bias: {result['direction']:20} | Prob: {result['probability']}%")
        else:
            print(f"{display_name:8} | ❌ {result.get('message', 'Telemetry Error')}")
            
    print("-" * 65)
    print("✅ System analytics computation complete!")
    return results

def update_bias_summary():
    """Updates the macro_bias_summary fast cache table with the hybrid results."""
    print("\n📤 Syncing calculations directly to database summary blocks...")
    results = run_bias_engine()
    supabase = get_supabase_client()
    
    updated = 0
    for ticker, data in results.items():
        if data.get("status") != "SUCCESS":
            continue
        
        row = {
            "ticker": ticker,
            "latest_close": float(data["latest_close"]),
            "direction": str(data["direction"]),
            "probability": float(data["probability"]),
            "confidence": float(data["confidence"]),
            "z_score": float(data["z_score"]),
            "momentum_pct": float(data["momentum_pct"]),
            "updated_at": datetime.utcnow().isoformat() + "Z"  # Standardized high-fidelity timestamp
        }
        
        try:
            supabase.table("macro_bias_summary") \
                .upsert(row, on_conflict="ticker") \
                .execute()
            updated += 1
        except Exception as e:
            print(f"❌ Failed to push summary array entry for {ticker}: {e}")
    
    print(f"✅ Summary cache updated for {updated} assets")
    return updated

if __name__ == "__main__":
    run_bias_engine()

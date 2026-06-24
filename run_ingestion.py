"""
MACRO BIAS ENGINE - Ingestion Pipeline
Downloads, sanitizes, and logs historical and live market asset prices.
Hardened with an explicit data audit layer to catch pricing anomalies.
"""
import sys
import os
import time
import requests
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS

TARGET_REGISTRY = {
    "XAUUSD": ["GC=F", "XAUUSD=X"],
    "XAGUSD": ["SI=F", "XAGUSD=X"],
    "BTCUSD": ["BTC-USD"],
    "JP225": ["^N225"],
    "US30": ["^DJI"],
    "EURUSD": ["EURUSD=X"],
    "GBPUSD": ["GBPUSD=X"],
    "AUDUSD": ["AUDUSD=X"],
    "EURJPY": ["EURJPY=X"],
    "GBPJPY": ["GBPJPY=X"],
    "CADJPY": ["CADJPY=X"],
    "CADCHF": ["CADCHF=X"],
    "DXY": ["DX-Y.NYB"],
    "VIX": ["^VIX"],
    "US10Y": ["^TNX"]
}

def fetch_historical_prices(ticker, days_back=35):
    """Fetches clean historical close sequences using direct Yahoo endpoints."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": f"{days_back}d", "interval": "1d", "includeTimestamps": "true"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://finance.yahoo.com",
        "Referer": "https://finance.yahoo.com/"
    }
    try:
        session = requests.Session()
        session.get("https://finance.yahoo.com", headers=headers, timeout=5)
        response = session.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        result = data.get("chart", {}).get("result", [None])[0]
        if not result:
            return None
            
        timestamps = result.get("timestamp", [])
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        
        formatted_dates, clean_closes = [], []
        for ts, cls in zip(timestamps, closes):
            if ts is None or cls is None:
                continue
            formatted_dates.append(datetime.fromtimestamp(ts).strftime("%Y-%m-%d"))
            clean_closes.append(float(cls))
            
        return pd.DataFrame({"Date": formatted_dates, "Close": clean_closes})
    except Exception:
        return None

def run_backfill(days_back=35):
    """Backfills history to satisfy technical indicators requiring historical depth."""
    print(f"\n📥 Forcing {days_back}-day structural historical backfill...")
    supabase = get_supabase_client()
    total_inserted = 0
    
    for display_name, tickers in TARGET_REGISTRY.items():
        df = None
        for ticker in tickers:
            df = fetch_historical_prices(ticker, days_back=days_back)
            if df is not None and not df.empty:
                break
            time.sleep(0.5)
            
        if df is None or df.empty:
            continue
            
        for _, row in df.iterrows():
            date_str = row["Date"]
            price = row["Close"]
            if pd.isna(price):
                continue
                
            check = supabase.table("market_structure_logs") \
                .select("id").eq("ticker", display_name).eq("created_at", date_str).execute()
                
            if check.data:
                continue
                
            row_data = {
                "ticker": display_name,
                "latest_close": float(price),
                "trend": "NEUTRAL",
                "momentum_score": 0.0,
                "created_at": date_str
            }
            try:
                supabase.table("market_structure_logs").insert(row_data).execute()
                total_inserted += 1
            except Exception:
                pass
    print(f"✅ Historical matrix synchronizer complete. Rows added: {total_inserted}")

def get_row_count():
    """Validates real historical data points currently inside the database logs."""
    try:
        supabase = get_supabase_client()
        res = supabase.table("market_structure_logs").select("created_at").limit(100).execute()
        return len({r['created_at'].split('T')[0] for r in res.data}) if res.data else 0
    except Exception:
        return 0

def run_pipeline():
    """Main execution pipeline runner."""
    print("🚀 INITIALIZING INTEL INGESTION PIPELINE RUN")
    
    row_count = get_row_count()
    if row_count < 20:
        run_backfill(days_back=35)
        
    prices = fetch_all_prices() or {}
    
    # Fill macro endpoints manually if missing from standard spot price dictionaries
    for display_name, tickers in TARGET_REGISTRY.items():
        if display_name not in prices or prices[display_name] is None:
            for ticker in tickers:
                df = fetch_historical_prices(ticker, days_back=2)
                if df is not None and not df.empty:
                    prices[display_name] = df["Close"].iloc[-1]
                    break

    # 🔍 EXPLICIT DATA AUDIT INGESTION CHECK
    print("\n🔍 EXPLICIT DATA AUDIT INGESTION CHECK:")
    print("=" * 65)
    timestamp_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for name, price in list(prices.items()):
        print(f"   [AUDIT] Ticker: {name:<8} | Raw Price: {str(price):<10} | Time: {timestamp_now}")
        
        # 🪙 HARDENED GOLD SPOT CONTRACT SANITIZATION
        if name == "XAUUSD" and price is not None:
            if price > 3500.0:
                print(f"   ⚠️ WARNING: Abnormal Gold pricing detected ({price}). Normalizing...")
                if price > 200000:
                    price = price / 100.0
                elif price > 20000:
                    price = price / 10.0
                prices[name] = price
                print(f"   ✅ Corrected Gold Price to: {prices[name]}")
    print("=" * 65)

    supabase = get_supabase_client()
    today_string = datetime.now().strftime("%Y-%m-%d")
    
    for name, price in prices.items():
        if price is None or name not in TARGET_REGISTRY:
            continue
            
        dup = supabase.table("market_structure_logs") \
            .select("id").eq("ticker", name).eq("created_at", today_string).execute()
        if dup.data:
            continue
            
        row = {
            "ticker": name,
            "latest_close": float(price),
            "trend": "NEUTRAL",
            "momentum_score": 0.0,
            "created_at": today_string
        }
        try:
            supabase.table("market_structure_logs").insert(row).execute()
        except Exception as e:
            print(f"❌ Ingestion database sync failed for {name}: {e}")

    print("🧠 BOOTING COGNITIVE EVALUATION LAYER")
    try:
        from src.analytics.bias_engine import run_bias_engine
        run_bias_engine()
    except Exception as e:
        print(f"❌ Computation step execution fault: {e}")

if __name__ == "__main__":
    run_pipeline()

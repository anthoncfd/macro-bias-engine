"""
MACRO BIAS ENGINE - Main Ingestion Pipeline (V3.0)
Uses direct, authenticated Twelve Data flows alongside targeted Yahoo Cash-Spot historical endpoints.
Automatically adjusts lookback windows to handle tracking calculations over weekends.
"""
import sys
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_all_prices, FOREX_PAIRS, ASSETS

TARGET_MARKET_HISTORY = 60  
MIN_REQUIRED_SESSIONS = 25  

def calculate_required_calendar_days(target_trading_days):
    """Dynamically scales calendar days to clear weekend market drops."""
    weeks = (target_trading_days // 5) + 1
    weekend_days = weeks * 2
    return target_trading_days + weekend_days + 5

def fetch_historical_yahoo(ticker, start_date, end_date):
    """Fetch daily OHLC from Yahoo direct API using standard tracking nodes."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": int(start_date.timestamp()),
        "period2": int(end_date.timestamp()),
        "interval": "1d",
        "events": "history"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        result = data.get("chart", {}).get("result", [None])[0]
        if not result:
            return None
        timestamps = result.get("timestamp", [])
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        valid = [(t, c) for t, c in zip(timestamps, closes) if t is not None and c is not None]
        if not valid:
            return None
        df = pd.DataFrame(valid, columns=["timestamp", "close"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="s").dt.strftime("%Y-%m-%d")
        return df[["date", "close"]]
    except Exception as e:
        print(f"   ⚠️ Yahoo API error for {ticker}: {e}")
        return None

def fetch_historical_metal_spot(symbol, count=40):
    """Fetches historical cash SPOT metal arrays via Yahoo cash indices."""
    spot_ticker_map = {"XAUUSD": "XAUUSD=X", "XAGUSD": "XAGUSD=X"}
    ticker = spot_ticker_map.get(symbol)
    if not ticker:
        return None
        
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=int(count * 1.6) + 5)
    return fetch_historical_yahoo(ticker, start_date, end_date)

def run_backfill(required_trading_days):
    """Automated database asset layer padding routine."""
    calendar_days_back = calculate_required_calendar_days(required_trading_days)
    print(f"\n📥 AUTOMATED BACKFILL: Syncing {calendar_days_back} calendar days...")
    supabase = get_supabase_client()
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=calendar_days_back)
    total_inserted = 0

    for display_name, tickers in ASSETS.items():
        print(f"\n📊 Processing {display_name}...")

        if display_name in ["XAUUSD", "XAGUSD"]:
            df = fetch_historical_metal_spot(display_name, count=required_trading_days + 10)
        else:
            df = None
            for ticker in tickers if isinstance(tickers, list) else [tickers]:
                df = fetch_historical_yahoo(ticker, start_date, end_date)
                if df is not None and not df.empty:
                    break

        if df is None or df.empty:
            print(f"   ❌ No history recovered for {display_name}")
            continue

        for _, row in df.iterrows():
            date_str = row["date"]
            price = float(row["close"])
            if pd.isna(price):
                continue

            check = supabase.table("market_structure_logs") \
                .select("id") \
                .eq("ticker", display_name) \
                .eq("created_at", date_str) \
                .execute()
            if check.data:
                continue

            row_data = {
                "ticker": display_name,
                "latest_close": price,
                "trend": "NEUTRAL",
                "momentum_score": 0.0,
                "created_at": date_str
            }
            try:
                supabase.table("market_structure_logs").insert(row_data).execute()
                total_inserted += 1
            except Exception as e:
                print(f"   ❌ Insert failed: {e}")
            time.sleep(0.02)

    print(f"\n✅ Backfill complete! Inserted {total_inserted} rows.")
    return total_inserted

def get_database_state():
    """Validates records across all assets."""
    state = {}
    try:
        supabase = get_supabase_client()
        for display_name in ASSETS.keys():
            result = supabase.table("market_structure_logs") \
                .select("created_at", count="exact") \
                .eq("ticker", display_name) \
                .execute()
            count = result.count if hasattr(result, 'count') else len(result.data or [])
            state[display_name] = count
        return state
    except Exception as e:
        print(f"   ⚠️ Database state validation failure: {e}")
        return {name: 0 for name in ASSETS.keys()}

def run_pipeline():
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - AUTOMATED INGESTION PIPELINE")
    print(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 55)

    db_state = get_database_state()
    lowest_session_count = min(db_state.values()) if db_state else 0
    print(f"   📉 Minimum available asset metrics: {lowest_session_count} trading days.")

    if lowest_session_count < MIN_REQUIRED_SESSIONS:
        sessions_needed = TARGET_MARKET_HISTORY - lowest_session_count
        run_backfill(required_trading_days=sessions_needed)
    else:
        print("\n✅ Sufficient database cache verified.")

    print("\n📊 Pulling Live Production Feed via Twelve Data...")
    raw_prices = fetch_all_prices()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    normalized_prices = {}
    for name in ASSETS.keys():
        item = raw_prices.get(name)
        if item is None:
            normalized_prices[name] = None
        elif isinstance(item, dict):
            normalized_prices[name] = {"price": item.get("price"), "date": today_str}
        elif isinstance(item, (int, float)):
            normalized_prices[name] = {"price": float(item), "date": today_str}

    print("\n📊 Market Snapshot:")
    for name, item in normalized_prices.items():
        if item is None or item.get("price") is None:
            print(f"   ❌ {name:10} : Out of Service")
        else:
            price = item["price"]
            print(f"   ✅ {name:10} : {price:.4f}" if name in FOREX_PAIRS else f"   ✅ {name:10} : ${price:,.2f}")

    print("\n🔌 Synchronizing Live Records with Supabase Storage Backend...")
    try:
        supabase = get_supabase_client()
    except Exception as e:
        print(f"   ❌ Database stack authentication mapping fatal exception: {e}")
        return

    inserted_count = 0
    for name, item in normalized_prices.items():
        if item is None or item.get("price") is None:
            continue
        price_val = item["price"]
        
        dup_check = supabase.table("market_structure_logs") \
            .select("id") \
            .eq("ticker", name) \
            .eq("created_at", today_str) \
            .execute()
        if dup_check.data:
            print(f"   ⚪ {name} current for today.")
            continue
            
        row = {
            "ticker": name,
            "latest_close": float(price_val),
            "trend": "NEUTRAL",
            "momentum_score": 0.0,
            "created_at": today_str
        }
        try:
            supabase.table("market_structure_logs").insert(row).execute()
            inserted_count += 1
        except Exception as e:
            print(f"   ❌ Failed to sync {name}: {e}")

    print(f"   📥 Live Pipeline processed [{inserted_count}] records.")
    print("\n" + "=" * 55)
    print("🧠 RUNNING BIAS ENGINE CORE ANALYSIS")
    print("=" * 55)
    try:
        from src.analytics.bias_engine import run_bias_engine
        run_bias_engine()
    except Exception as e:
        print(f"❌ Bias Engine execution error: {e}")

if __name__ == "__main__":
    run_pipeline()

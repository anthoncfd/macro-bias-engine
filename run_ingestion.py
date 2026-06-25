"""
MACRO BIAS ENGINE - Main Ingestion Pipeline (V2.2 - Fully Automated)
Uses direct Yahoo API for historical assets and TradingView for metals backfilling.
Automatically calculates required calendar windows to completely eliminate manual inputs.
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

# Global Target Metrics
TARGET_MARKET_HISTORY = 60  # We want a target buffer of 60 trading sessions
SMA_WINDOW = 20
MIN_REQUIRED_SESSIONS = 25  # Minimum safe count to run a true 20 SMA with Z-Score

def calculate_required_calendar_days(target_trading_days):
    """
    Dynamically scales trading days to calendar days to absorb weekend market closures.
    Formula accounts for 2 weekend days out of every 5 business days, adding a 5-day safety margin.
    """
    weeks = (target_trading_days // 5) + 1
    weekend_days = weeks * 2
    return target_trading_days + weekend_days + 5

# ─── Direct Yahoo API (No yfinance tracking layer) ───────────────────
def fetch_historical_yahoo(ticker, start_date, end_date):
    """Fetch daily OHLC from Yahoo direct API with browser-grade headers."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": int(start_date.timestamp()),
        "period2": int(end_date.timestamp()),
        "interval": "1d",
        "events": "history"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
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

# ─── TradingView Historical Fetcher ──────────────────────────────────
def fetch_historical_metal_spot(symbol="XAUUSD", exchange="OANDA", count=40):
    """Fetches clean historical data arrays using the open TradingView proxy."""
    tv_ticker = f"{exchange.upper()}:{symbol.upper()}"
    url = "https://chartapi.tradingview.com/v1/history"
    params = {"symbol": tv_ticker, "resolution": "D", "count": count}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.tradingview.com/"
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        timestamps = data.get("t", [])
        closes = data.get("c", [])
        
        if not closes or not timestamps:
            return None
            
        valid_records = []
        for ts, close_val in zip(timestamps, closes):
            if ts is not None and close_val is not None:
                date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                valid_records.append({"date": date_str, "close": float(close_val)})
                
        if not valid_records:
            return None
            
        return pd.DataFrame(valid_records)
    except Exception as e:
        print(f"   ⚠️ Metal historical backend calculation error: {e}")
        return None

def run_backfill(required_trading_days):
    """Backfills history by automatically calculating the necessary calendar offset."""
    # Convert required trading sessions into safe physical calendar days
    calendar_days_back = calculate_required_calendar_days(required_trading_days)
    
    print(f"\n📥 AUTOMATED BACKFILL: Requesting {calendar_days_back} calendar days to capture {required_trading_days} trading sessions...")
    supabase = get_supabase_client()
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=calendar_days_back)
    total_inserted = 0

    for display_name, tickers in ASSETS.items():
        print(f"\n📊 Processing {display_name}...")

        # Metals Path
        if display_name in ["XAUUSD", "XAGUSD"]:
            df = fetch_historical_metal_spot(display_name, exchange="OANDA", count=required_trading_days + 10)
            if df is None or df.empty:
                print(f"   ⚠️ No historical spot data extracted for {display_name}.")
                continue
        # Standard Assets Path
        else:
            df = None
            for ticker in tickers:
                df = fetch_historical_yahoo(ticker, start_date, end_date)
                if df is not None and not df.empty:
                    print(f"   ✅ Using ticker: {ticker}")
                    break
            if df is None or df.empty:
                print(f"   ❌ No data for {display_name}")
                continue

        # Ingestion Sync Loop
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
                print(f"   📅 {date_str}: {price}")
            except Exception as e:
                print(f"   ❌ Insert failed: {e}")
            time.sleep(0.05)
        time.sleep(0.2)

    print(f"\n✅ Backfill complete! Inserted {total_inserted} rows.")
    return total_inserted

def get_database_state():
    """Returns a dictionary containing the active history counts for every tracked asset."""
    state = {}
    try:
        supabase = get_supabase_client()
        for display_name in ASSETS.keys():
            result = supabase.table("market_structure_logs") \
                .select("created_at", count="exact") \
                .eq("ticker", display_name) \
                .execute()
            # Handle standard postgrest count parsing seamlessly
            count = result.count if hasattr(result, 'count') else len(result.data or [])
            state[display_name] = count
        return state
    except Exception as e:
        print(f"   ⚠️ Database capacity validation failure: {e}")
        return {name: 0 for name in ASSETS.keys()}

def run_pipeline():
    print("=" * 55)
    print("🚀 MACRO BIAS ENGINE - AUTOMATED INGESTION PIPELINE")
    print(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 55)

    print("\n🔍 Checking database state for distinct session logs...")
    db_state = get_database_state()
    
    lowest_session_count = min(db_state.values()) if db_state else 0
    print(f"   📊 Current asset history depths: {db_state}")
    print(f"   📉 Minimum available history across assets: {lowest_session_count} trading days.")

    # AUTOMATED TRIGGER: If history falls short of the required window, automatically top it off
    if lowest_session_count < MIN_REQUIRED_SESSIONS:
        sessions_needed = TARGET_MARKET_HISTORY - lowest_session_count
        print(f"\n⚠️ Database needs history. Automatically requesting a {sessions_needed}-session fill...")
        run_backfill(required_trading_days=sessions_needed)
    else:
        print("\n✅ Database has sufficient history. Skipping backfill.")

    print("\n⏳ Waiting 3 seconds...")
    time.sleep(3)

    print("\n📊 Fetching live market data...")
    prices = fetch_all_prices()

    print("\n📊 Market Snapshot:")
    for name, item in prices.items():
        if item is None or item.get("price") is None:
            print(f"   ❌ {name:10} : No data")
        else:
            price = item["price"]
            if name in FOREX_PAIRS:
                print(f"   ✅ {name:10} : {price:.4f}")
            else:
                print(f"   ✅ {name:10} : ${price:,.2f}")

    print("\n🔌 Connecting to Supabase...")
    try:
        supabase = get_supabase_client()
        print("   ✅ Connection successful!")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    print("\n📤 Syncing today's closes...")
    inserted_count = 0
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for name, item in prices.items():
        if item is None or item.get("price") is None:
            continue
        price_val = item["price"]
        dup_check = supabase.table("market_structure_logs") \
            .select("id") \
            .eq("ticker", name) \
            .eq("created_at", today_str) \
            .execute()
        if dup_check.data:
            print(f"   ⚪ {name} already recorded for today.")
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
            print(f"   ✅ Inserted {name}")
            inserted_count += 1
        except Exception as e:
            print(f"   ❌ Failed {name}: {e}")

    print(f"\n📊 Inserted {inserted_count} assets today")

    print("\n" + "=" * 55)
    print("🧠 RUNNING BIAS ENGINE")
    print("=" * 55)
    try:
        from src.analytics.bias_engine import run_bias_engine
        run_bias_engine()
    except Exception as e:
        print(f"❌ Bias Engine error: {e}")

    print("\n✅ PIPELINE COMPLETE")

if __name__ == "__main__":
    run_pipeline()

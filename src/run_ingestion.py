import sys
import os

# 1. System Path Alignment: Tell Python where to find our custom subfolders
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase_client import get_supabase_client
from src.ingestion.market_prices import fetch_asset_data, calculate_market_structure


def execute_pipeline():
    """
    Orchestrates downloading market data, calculating structure metrics,
    and writing the results to the Supabase cloud ledger.
    """
    print("🚀 Initializing Macro Bias Ingestion Engine Pipeline...")

    # 2. Establish cloud database connection
    try:
        supabase = get_supabase_client()
        print("✅ Secure cloud database connection established successfully.")
    except Exception as connection_error:
        print(f"❌ Pipeline aborted. Connection failure: {connection_error}")
        return

    # 3. Map friendly asset names to yfinance symbols
    assets_to_track = {
        "XAUUSD": "GC=F",          # Gold futures
        "BTCUSD": "BTC-USD",       # Bitcoin
        "DXY":    "DX-Y.NYB",      # US Dollar Index
        "EURUSD": "EURUSD=X",      # Euro / US Dollar
        "GBPUSD": "GBPUSD=X",      # British Pound / US Dollar
        "GBPJPY": "GBPJPY=X",      # British Pound / Japanese Yen
        "EURJPY": "EURJPY=X",      # Euro / Japanese Yen
    }

    # 4. Process each asset sequentially
    for friendly_name, ticker_symbol in assets_to_track.items():
        print(f"\n🔄 Processing asset: {friendly_name} ({ticker_symbol})")

        # --- Step A: fetch raw price data ---
        raw_data = fetch_asset_data(ticker_symbol, lookback_days=30)

        # --- Step B: skip assets with no usable data ---
        if raw_data.empty or len(raw_data) < 2:
            print(f"⚠️ Skipping {friendly_name} – not enough data (got {len(raw_data)} rows).")
            continue

        # --- Step C: calculate market structure ---
        metrics = calculate_market_structure(raw_data)

        # --- Step D: build the database payload ---
        data_packet = {
            "ticker":         friendly_name,
            "latest_close":   metrics["latest_close"],
            "trend":          metrics["trend"],
            "momentum_score": metrics["momentum_score"],
        }

        # --- Step E: push to Supabase ---
        try:
            print(f"📤 Pushing {friendly_name} structure metrics to the cloud...")
            response = supabase.table("market_structure_logs").insert(data_packet).execute()
            print(f"🎉 Success! Recorded row for {friendly_name} (Trend: {metrics['trend']})")
        except Exception as upload_error:
            print(f"❌ Failed to upload data packet for {friendly_name}. Details: {upload_error}")

    print("\n🏁 Pipeline complete. All market regimes logged successfully.")


if __name__ == "__main__":
    execute_pipeline()
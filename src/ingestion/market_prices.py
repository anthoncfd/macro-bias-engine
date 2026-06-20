import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Union


def fetch_asset_data(ticker_symbol: str, lookback_days: int = 30) -> pd.DataFrame:
    """
    Downloads daily closing prices and volume for a given ticker symbol.
    Returns an empty DataFrame on failure or no data.
    """
    # 1. Calculate date range – format as strings for reliable yfinance usage
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"⏳ Downloading market feeds for ticker: {ticker_symbol}...")

    try:
        df = yf.download(
            ticker_symbol,
            start=start_str,
            end=end_str,
            interval="1d",
            progress=False,
            auto_adjust=True,       # ensures we get the adjusted close
        )
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return pd.DataFrame()

    if df.empty:
        print(f"⚠️ Warning: No data returned for ticker {ticker_symbol}")
        return pd.DataFrame()

    # Drop multi-level columns if present (can happen with some yfinance versions)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df


def calculate_market_structure(df: pd.DataFrame) -> Dict[str, Union[str, float]]:
    """
    Computes trend direction, momentum, and moving average from price data.
    Always returns the keys 'latest_close', 'trend', 'momentum_score'.
    """
    # Edge case: not enough data – always include 'latest_close'
    if df.empty or len(df) < 2:
        return {"latest_close": 0.0, "trend": "NEUTRAL", "momentum_score": 0.0}

    # Safe extraction
    latest_close = float(df["Close"].iloc[-1])
    previous_close = float(df["Close"].iloc[-2])

    # Calculate 20-day SMA (or the maximum window if less data)
    window = min(20, len(df))
    df["SMA_20"] = df["Close"].rolling(window=window).mean()
    current_sma = float(df["SMA_20"].iloc[-1])

    # Trend determination
    if latest_close > current_sma:
        trend_direction = "BULLISH"
    elif latest_close < current_sma:
        trend_direction = "BEARISH"
    else:
        trend_direction = "NEUTRAL"

    # Momentum as percentage change
    momentum = ((latest_close - previous_close) / previous_close) * 100

    return {
        "latest_close": latest_close,
        "trend": trend_direction,
        "momentum_score": round(momentum, 2),
    }
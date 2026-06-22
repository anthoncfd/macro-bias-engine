"""
MACRO BIAS ENGINE - Market Data Ingestion Fetcher
Safely extracts price streams for 12 core global macroeconomic assets from Yahoo Finance.
"""
import yfinance as yf

# Institutional Asset Configuration Matrix: "Display_Name": ["Primary_Ticker", "Fallback_Ticker"]
ASSETS = {
    "XAUUSD": ["GC=F", "XAUUSD=X"],  # Gold Spot
    "XAGUSD": ["SI=F", "XAGUSD=X"],  # Silver Spot
    "BTCUSD": ["BTC-USD"],           # Bitcoin Core
    "JP225": ["^N225"],              # Nikkei 225 Index
    "US30": ["^DJI"],                # Dow Jones Industrial Average
    "EURUSD": ["EURUSD=X"],
    "GBPUSD": ["GBPUSD=X"],
    "AUDUSD": ["AUDUSD=X"],
    "EURJPY": ["EURJPY=X"],
    "GBPJPY": ["GBPJPY=X"],
    "CADJPY": ["CADJPY=X"],
    "CADCHF": ["CADCHF=X"]
}

# Standard 4-decimal place truncation targets for Forex pairs
FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

def safe_fetch(ticker):
    """
    Safely extracts the latest daily session close price.
    Uses an isolated 5-day history window to protect against weekend data gaps.
    """
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception:
        return None

def fetch_all_prices():
    """
    Iterates through structural assets using primary and fallback tickers.
    Returns a unified real-time price dictionary.
    """
    prices = {}
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
        prices[name] = price
    return prices

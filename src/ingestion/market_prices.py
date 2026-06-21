"""
MACRO BIAS ENGINE - Market Data Fetcher
Fetches 12 assets (Forex, Commodities, Indices, Crypto) from Yahoo Finance.
"""
import yfinance as yf

# Asset configuration: "Display_Name": ["Primary_Ticker", "Fallback_Ticker"]
ASSETS = {
    "XAUUSD": ["GC=F", "XAUUSD=X"],  # Gold
    "XAGUSD": ["SI=F", "XAGUSD=X"],  # Silver
    "BTCUSD": ["BTC-USD"],           # Bitcoin
    "JP225": ["^N225"],              # Nikkei 225
    "US30": ["^DJI"],                # Dow Jones
    "EURUSD": ["EURUSD=X"],
    "GBPUSD": ["GBPUSD=X"],
    "AUDUSD": ["AUDUSD=X"],
    "EURJPY": ["EURJPY=X"],
    "GBPJPY": ["GBPJPY=X"],
    "CADJPY": ["CADJPY=X"],
    "CADCHF": ["CADCHF=X"]
}

# List of Forex pairs (to format with 4 decimal places)
FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

def safe_fetch(ticker):
    """
    Safely fetches the latest closing price.
    Uses a 5-day window to ensure weekend data is captured.
    Returns None if the ticker fails.
    """
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")
        if not hist.empty:
            return hist["Close"].iloc[-1]
        return None
    except:
        return None

def fetch_all_prices():
    """
    Loops through all assets, tries primary/fallback tickers,
    and returns a dictionary of prices.
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

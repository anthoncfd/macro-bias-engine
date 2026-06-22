"""
MACRO BIAS ENGINE - Market Data Ingestion Fetcher
Extracts price streams for 12 core global macroeconomic assets safely.
"""
import yfinance as yf
import requests

# Institutional Asset Configuration Matrix
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

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

def safe_fetch(ticker):
    """
    Safely extracts the latest daily session close price.
    Attaches custom header sessions to bypass GitHub Actions IP scraper limits.
    """
    try:
        # Create a session to mask serverless automated patterns
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Pull 7 days to cover extended holiday/weekend indexing drops cleanly
        data = yf.Ticker(ticker, session=session)
        hist = data.history(period="7d")
        
        if not hist.empty and 'Close' in hist.columns:
            # Drop any trailing NaN or un-settled real-time daily candles
            clean_series = hist['Close'].dropna()
            if not clean_series.empty:
                return float(clean_series.iloc[-1])
        return None
    except Exception as e:
        print(f"   ⚠️ yfinance connection exception for {ticker}: {e}")
        return None

def fetch_all_prices():
    """Iterates through tickers using primary and fallback channels."""
    prices = {}
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
        prices[name] = price
        if price is not None:
            print(f"   💸 Feed connection successful: {name} -> {price}")
        else:
            print(f"   ❌ Feed connection dead for asset row: {name}")
    return prices

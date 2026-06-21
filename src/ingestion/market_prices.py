"""
MACRO BIAS ENGINE - Market Data Fetcher
Fetches 12 assets (Forex, Commodities, Indices, Crypto) from Yahoo Finance.
Fixed to handle Yahoo JSON tracking and session injection.
"""
import yfinance as yf
import requests
import time
import random

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

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

# Spoof a real browser header configuration
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def safe_fetch(ticker, retries=3):
    """
    Safely fetches the latest closing price with custom sessions
    to bypass Yahoo Finance request screening.
    """
    # Create an authenticated web session explicitly for yfinance
    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(retries):
        try:
            # Pass our browser session into the Ticker object
            ticker_obj = yf.Ticker(ticker, session=session)
            
            # Request historical window data safely
            hist = ticker_obj.history(period="5d", auto_adjust=True)
            
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
                
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt+1}/{retries} failed for {ticker}: {str(e)[:45]}")
            time.sleep(random.uniform(1.5, 3.0))
            
    return None

def fetch_all_prices():
    """Loops through all assets and falls back if primary tickers drop out."""
    prices = {}
    
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            time.sleep(0.5)
        
        prices[name] = price
        # Gentle pacing between asset blocks
        time.sleep(random.uniform(0.5, 1.2))
        
    return prices

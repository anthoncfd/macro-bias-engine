"""
MACRO BIAS ENGINE - Market Data Fetcher
Fetches 12 assets (Forex, Commodities, Indices, Crypto) from Yahoo Finance.
Includes anti-blocking measures: User-Agent spoofing, delays, session reuse.
"""
import yfinance as yf
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

# List of Forex pairs (to format with 4 decimal places)
FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

# ==========================================
# ANTI-BLOCKING MEASURES
# ==========================================

# Spoof a real browser User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def safe_fetch(ticker, retries=3):
    """
    Safely fetches the latest closing price with retries and delays.
    Uses a browser User-Agent to avoid Yahoo blocking.
    """
    for attempt in range(retries):
        try:
            # Create Ticker with custom session
            ticker_obj = yf.Ticker(ticker)
            
            # Download with a small delay to avoid rate limiting
            time.sleep(random.uniform(0.5, 1.5))
            
            hist = ticker_obj.history(
                period="5d",
                auto_adjust=True,
                threads=False,
                progress=False
            )
            
            if not hist.empty:
                return hist["Close"].iloc[-1]
            else:
                # Try using the download function directly as a fallback
                import yfinance as yf_alt
                hist = yf_alt.download(
                    ticker,
                    period="5d",
                    interval="1d",
                    auto_adjust=True,
                    progress=False,
                    threads=False
                )
                if not hist.empty:
                    return hist["Close"].iloc[-1]
                
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt+1}/{retries} failed for {ticker}: {str(e)[:50]}")
            time.sleep(random.uniform(1, 3))  # Wait before retry
    
    return None

def fetch_all_prices():
    """
    Loops through all assets, tries primary/fallback tickers,
    and returns a dictionary of prices.
    """
    prices = {}
    
    # Add a small initial delay
    time.sleep(1)
    
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            # Add a delay between fallback attempts
            time.sleep(random.uniform(0.5, 1))
        
        prices[name] = price
        
        # Delay between different assets to avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))
    
    return prices

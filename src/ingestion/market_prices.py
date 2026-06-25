"""
MACRO BIAS ENGINE - Market Data Fetcher
Uses direct Yahoo API with proper adjusted close and 1m live price fallback.
For metals (XAUUSD, XAGUSD, XPTUSD, XPDUSD, XRHUSD), uses dedicated metals spot API.
"""
import os
import requests
import time
import random
import logging

# ─── Import the metals spot fetcher ────────────────────────────────────
from src.ingestion.metals_spot_fetcher import fetch_metal_spots, METAL_SYMBOLS

logger = logging.getLogger(__name__)

# ==========================================
# ASSET CONFIGURATION
# ==========================================

ASSETS = {
    # Metals: spot tickers (will be overridden by metal API for live price)
    "XAUUSD": ["XAUUSD=X", "GC=F"],          # Gold
    "XAGUSD": ["XAGUSD=X", "SI=F"],          # Silver
    "XPTUSD": ["XPTUSD=X", "PL=F"],          # Platinum
    "XPDUSD": ["XPDUSD=X", "PA=F"],          # Palladium
    "XRHUSD": ["XRHUSD=X", "RH=F"],          # Rhodium
    # Crypto & Indices
    "BTCUSD": ["BTC-USD"],
    "JP225": ["^N225"],
    "US30": ["^DJI"],
    # Forex
    "EURUSD": ["EURUSD=X"],
    "GBPUSD": ["GBPUSD=X"],
    "AUDUSD": ["AUDUSD=X"],
    "EURJPY": ["EURJPY=X"],
    "GBPJPY": ["GBPJPY=X"],
    "CADJPY": ["CADJPY=X"],
    "CADCHF": ["CADCHF=X"],
}

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

# ==========================================
# DATA FETCHER FUNCTIONS
# ==========================================

def safe_fetch(ticker, retries=3):
    """
    Fetches the latest CLOSING price (daily adjusted close).
    Uses '5d' range to ensure weekend data is captured.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    params = {"range": "5d", "interval": "1d"}

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                chart_data = data.get("chart", {}).get("result", [None])[0]
                if chart_data:
                    indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        return float(valid_closes[-1])
        except:
            pass
        time.sleep(random.uniform(1.0, 2.0))
    return None

def fetch_all_prices():
    """Loops through all assets and returns a dictionary of closing prices."""
    prices = {}
    for name, tickers in ASSETS.items():
        price = None
        for t in tickers:
            price = safe_fetch(t)
            if price is not None:
                break
            time.sleep(0.5)
        prices[name] = price
        time.sleep(random.uniform(0.5, 1.0))
    return prices

def fetch_live_price(tickers):
    """
    Fetches current intraday price.
    For metals (XAUUSD, XAGUSD, XPTUSD, XPDUSD, XRHUSD), uses dedicated spot API.
    For others, uses Yahoo Finance (1m → 5m fallback).
    """
    # Check if any of the tickers are metals
    metals_to_fetch = [t for t in tickers if t in METAL_SYMBOLS]
    if metals_to_fetch:
        api_key = os.environ.get("METALS_API_KEY")
        all_metal_prices = fetch_metal_spots(api_key)
        # Try to find a price for any of the requested metals
        for metal in metals_to_fetch:
            if metal in all_metal_prices and all_metal_prices[metal] is not None:
                logger.info(f"📡 Live price from Metals-API: {metal} = {all_metal_prices[metal]}")
                return all_metal_prices[metal]
        # If no metal price found, fall through to Yahoo

    # Fallback: Yahoo Finance for all assets (including metals if API failed)
    intervals = ["1m", "5m"]
    for ticker in tickers:
        for interval in intervals:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                params = {"range": "1d", "interval": interval}
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    chart_data = data.get("chart", {}).get("result", [None])[0]
                    if chart_data:
                        indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                        closes = indicators.get("close", [])
                        valid_closes = [c for c in closes if c is not None]
                        if valid_closes:
                            price = float(valid_closes[-1])
                            logger.info(f"📡 Live price from {ticker} ({interval}): {price}")
                            return price
            except:
                pass
            time.sleep(0.2)
    return None

def fetch_adjusted_close(ticker, days_back=5):
    """
    Fetches the official adjusted close for a specific date.
    More accurate than the last close in the array.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {"range": f"{days_back}d", "interval": "1d"}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            chart_data = data.get("chart", {}).get("result", [None])[0]
            if chart_data:
                indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                closes = indicators.get("close", [])
                timestamps = chart_data.get("timestamp", [])
                if closes and timestamps:
                    for i in range(len(closes) - 1, -1, -1):
                        if closes[i] is not None:
                            return {
                                "price": float(closes[i]),
                                "timestamp": timestamps[i],
                                "date": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamps[i]))
                            }
    except:
        pass
    return None

# ─── Standalone test ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing market_prices.py...")
    all_prices = fetch_all_prices()
    for name, price in all_prices.items():
        if price is not None:
            print(f"{name}: {price}")
        else:
            print(f"{name}: No data")

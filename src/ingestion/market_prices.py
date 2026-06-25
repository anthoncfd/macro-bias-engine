"""
MACRO BIAS ENGINE - Market Data Fetcher
For Gold and Silver: uses dedicated metals API (free, no key) for both live AND daily close.
For all other assets: uses Yahoo Finance.
"""
import os
import requests
import time
import random
import logging
from datetime import datetime

# ─── Import the metals fetcher ──────────────────────────────────────────
from src.ingestion.metals_spot_fetcher import (
    fetch_live_metal_spots, 
    get_historical_data_for_supabase,
    METAL_SYMBOLS
)

logger = logging.getLogger(__name__)

# ==========================================
# ASSET CONFIGURATION
# ==========================================

ASSETS = {
    # Metals: now fetched from dedicated API (not Yahoo)
    "XAUUSD": ["XAUUSD=X", "GC=F"],          # Gold - metal API handles actual data
    "XAGUSD": ["XAGUSD=X", "SI=F"],          # Silver - metal API handles actual data
    "XPTUSD": ["XPTUSD=X", "PL=F"],          # Platinum - still Yahoo
    "XPDUSD": ["XPDUSD=X", "PA=F"],          # Palladium - still Yahoo
    "XRHUSD": ["XRHUSD=X", "RH=F"],          # Rhodium - still Yahoo
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
    Fetches the latest CLOSING price from Yahoo Finance.
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
    """
    Loops through all assets and returns a dictionary of closing prices.
    Gold and Silver use dedicated metals API; others use Yahoo.
    """
    prices = {}
    
    # ─── Gold and Silver: Use dedicated API ──────────────────────────
    gold_history = get_historical_data_for_supabase("XAUUSD", 5)
    if gold_history and len(gold_history) > 0:
        prices["XAUUSD"] = gold_history[-1]["latest_close"]
    else:
        prices["XAUUSD"] = None
    
    silver_history = get_historical_data_for_supabase("XAGUSD", 5)
    if silver_history and len(silver_history) > 0:
        prices["XAGUSD"] = silver_history[-1]["latest_close"]
    else:
        prices["XAGUSD"] = None
    
    # ─── All other assets: Use Yahoo ────────────────────────────────
    for name, tickers in ASSETS.items():
        if name in ["XAUUSD", "XAGUSD"]:
            continue  # Already handled above
        
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
    For Gold (XAUUSD) and Silver (XAGUSD): uses dedicated metals API.
    For all other assets: uses Yahoo Finance (1m → 5m fallback).
    """
    # ─── Check if metal ────────────────────────────────────────────────
    metals_to_fetch = [t for t in tickers if t in ["XAUUSD", "XAGUSD"]]
    if metals_to_fetch:
        live_prices = fetch_live_metal_spots()
        for metal in metals_to_fetch:
            if metal in live_prices and live_prices[metal] is not None:
                logger.info(f"📡 Live {metal}: ${live_prices[metal]:.2f}")
                return live_prices[metal]
        # If API failed, fall through to Yahoo

    # ─── Fallback: Yahoo Finance ──────────────────────────────────────
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
    """Fetches adjusted close from Yahoo (for non-metal assets)."""
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
    
    # Test live price for gold
    gold_tickers = ASSETS.get("XAUUSD", [])
    live_gold = fetch_live_price(gold_tickers)
    print(f"Live Gold: {live_gold}")

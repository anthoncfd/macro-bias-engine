"""
MACRO BIAS ENGINE - Market Data Fetcher
Gold & Silver: ONLY use GoldPrice.Today (spot) – NO YAHOO, NO FUTURES.
All other assets: use Yahoo Finance (spot tickers only).
"""
import requests
import time
import random
import logging
from src.ingestion.metals_spot_fetcher import fetch_metal_spots

logger = logging.getLogger(__name__)

# ==========================================
# ASSET CONFIGURATION – NO FUTURES TICKERS
# ==========================================

ASSETS = {
    # Gold & Silver: spot tickers listed for reference, but we never use them
    "XAUUSD": ["XAUUSD=X"],       # Only spot – we actually use the API
    "XAGUSD": ["XAGUSD=X"],       # Only spot – we actually use the API
    # All other assets: only spot tickers (no futures fallback)
    "BTCUSD": ["BTC-USD"],
    "JP225": ["^N225"],
    "US30": ["^DJI"],
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
# YAHOO FETCHER (for non‑metals only)
# ==========================================

def safe_fetch_yahoo(ticker, retries=3):
    """Fetch daily close from Yahoo (for non‑metals)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {"range": "5d", "interval": "1d"}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                result = data.get("chart", {}).get("result", [None])[0]
                if result:
                    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                    valid = [c for c in closes if c is not None]
                    if valid:
                        return float(valid[-1])
        except:
            pass
        time.sleep(random.uniform(1, 2))
    return None

# ==========================================
# MAIN FETCHERS
# ==========================================

def fetch_all_prices():
    """
    Returns dict of latest closing prices for all assets.
    Gold & Silver: spot price from GoldPrice.Today (at ingestion time).
    Others: Yahoo daily close.
    """
    prices = {}

    # ─── Gold & Silver: use dedicated spot API ──────────────────────
    metals = fetch_metal_spots()
    prices["XAUUSD"] = metals.get("XAUUSD")   # may be None if API fails
    prices["XAGUSD"] = metals.get("XAGUSD")

    # ─── All other assets: Yahoo ─────────────────────────────────────
    for name, tickers in ASSETS.items():
        if name in ["XAUUSD", "XAGUSD"]:
            continue
        price = None
        for t in tickers:
            price = safe_fetch_yahoo(t)
            if price is not None:
                break
            time.sleep(0.5)
        prices[name] = price
        time.sleep(random.uniform(0.5, 1))

    return prices

def fetch_live_price(tickers):
    """
    Returns live price for a single asset (used by Telegram bot).
    For Gold & Silver: FORCE use the API – NO YAHOO, NO FUTURES.
    For others: Yahoo intraday (1m → 5m).
    """
    # ─── Metals: ONLY GoldPrice.Today ────────────────────────────────
    if any(t in ["XAUUSD", "XAGUSD"] for t in tickers):
        metals = fetch_metal_spots()
        for metal in ["XAUUSD", "XAGUSD"]:
            if metal in tickers and metal in metals:
                price = metals[metal]
                if price is not None:
                    logger.info(f"📡 Live {metal}: ${price:.2f} (Spot API)")
                    return price
        # If the API fails, return None – do NOT fallback to Yahoo
        logger.warning("⚠️ GoldPrice.Today failed – no live price for metals")
        return None

    # ─── All other assets: Yahoo intraday ──────────────────────────
    intervals = ["1m", "5m"]
    for ticker in tickers:
        for interval in intervals:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                params = {"range": "1d", "interval": interval}
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers, params=params, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    result = data.get("chart", {}).get("result", [None])[0]
                    if result:
                        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                        valid = [c for c in closes if c is not None]
                        if valid:
                            return float(valid[-1])
            except:
                pass
            time.sleep(0.2)
    return None

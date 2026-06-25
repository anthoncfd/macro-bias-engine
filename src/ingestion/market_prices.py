"""
MACRO BIAS ENGINE - Live Market Prices Ingestion (V3.5)
Queries Twelve Data's settled End-of-Day (/eod) endpoint for institutional session closes,
while using Yahoo Live fallback routing for premium-restricted indices and spot metals.
Provides the clean daily close prices required for accurate 20-SMA calculations.
"""
import os
import requests
import logging
import time

logger = logging.getLogger(__name__)

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

ASSETS = {
    "XAUUSD": "XAU/USD",  # Institutional Gold Close via Twelve Data
    "XAGUSD": "YAHOO",    # Premium restricted on Twelve Data Free -> Yahoo Core
    "BTCUSD": "BTC/USD",  # Crypto Settled Close via Twelve Data
    "JP225": "YAHOO",     # Index -> Yahoo Core
    "US30": "YAHOO",      # Index -> Yahoo Core
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "CADJPY": "CAD/JPY",
    "CADCHF": "CAD/CHF"
}

# Explicit unauthenticated API mapping nodes for Yahoo Finance Core
YAHOO_LIVE_MAP = {
    "XAGUSD": "XAGUSD=X",  # Real-time Silver Spot index proxy 
    "JP225": "^N225",      # Nikkei 225 Daily Close
    "US30": "^DJI"        # Dow Jones Industrial Average Daily Close
}

def fetch_yahoo_live_price(display_name):
    """
    Fetches closing/current daily value from Yahoo Finance's unauthenticated engine.
    Used for assets restricted by Twelve Data's free tier subscription.
    """
    ticker = YAHOO_LIVE_MAP.get(display_name)
    if not ticker:
        return None
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, params={"interval": "1m", "range": "1d"}, timeout=8)
        if r.status_code == 200:
            result = r.json().get("chart", {}).get("result", [None])[0]
            if result:
                meta = result.get("meta", {})
                price = meta.get("regularMarketPrice")
                if price is not None:
                    return float(price)
    except Exception as e:
        logger.warning(f"Yahoo Core engine exception for {display_name}: {e}")
    return None

def fetch_all_prices():
    """
    Fetches official settled daily closing prices across all portfolio instruments.
    Uses Twelve Data /eod for allowed assets, and loops safely with a 9-second delay
    to respect free tier rate limit guidelines.
    """
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    if not api_key:
        logger.error("❌ Missing TWELVE_DATA_API_KEY environment variable.")
        return {name: None for name in ASSETS.keys()}

    output_prices = {name: None for name in ASSETS.keys()}
    url = "https://api.twelvedata.com/eod"
    total_assets = len(ASSETS)
    
    for idx, (display_name, provider_ticker) in enumerate(ASSETS.items(), 1):
        print(f"   ⏳ Fetching daily close for {display_name} ({idx}/{total_assets})...")
        
        # Intercept and route explicitly through Yahoo Core Live
        if provider_ticker == "YAHOO":
            yahoo_price = fetch_yahoo_live_price(display_name)
            if yahoo_price is not None:
                output_prices[display_name] = {"price": yahoo_price}
            else:
                logger.error(f"   ❌ Failed to pull {display_name} from Yahoo.")
            if idx < total_assets:
                time.sleep(0.5)  # Quick cycle for non-Twelve Data calls
            continue

        # Twelve Data End-of-Day (EOD) Close Ingestion Flow
        params = {
            "symbol": provider_ticker,
            "apikey": api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 429:
                logger.warning(f"   ⚠️ Hit 429 rate limit. Pacing retry window...")
                time.sleep(12)
                response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                logger.error(f"   ❌ API Error ({response.status_code}) for {display_name}")
                continue
                
            data = response.json()
            if "status" in data and data["status"] == "error":
                logger.error(f"   ❌ Rejected: {data.get('message')}")
                continue

            # The /eod endpoint maps daily candle close results to the "close" key
            if "close" in data:
                output_prices[display_name] = {
                    "price": float(data["close"])
                }
                
        except Exception as e:
            logger.error(f"   ❌ Exception during fetch for {display_name}: {e}")
            
        # Pacing window (9s delay applies strictly to Twelve Data endpoints to respect Free Tier rules)
        if idx < total_assets:
            time.sleep(9)
            
    return output_prices

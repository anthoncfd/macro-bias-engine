"""
MACRO BIAS ENGINE - Live Market Prices Ingestion (V3.1)
Uses Twelve Data REST API with explicit free-tier pacing to stay below 429 rate limits.
"""
import os
import requests
import logging
import time

logger = logging.getLogger(__name__)

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

ASSETS = {
    "XAUUSD": "XAU/USD",  # True Gold Cash Spot
    "XAGUSD": "XAG/USD",  # True Silver Cash Spot
    "BTCUSD": "BTC/USD",  # Bitcoin Cash Spot
    "JP225": "N225",      # Nikkei 225 Spot Index
    "US30": "DJI",        # Dow Jones Industrial Spot Index
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "CADJPY": "CAD/JPY",
    "CADCHF": "CAD/CHF"
}

def fetch_all_prices():
    """
    Fetches live market closes across all assets individually.
    Paces requests with a 9-second delay to safely stay below the 8 calls/minute limit.
    """
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    if not api_key:
        logger.error("❌ Missing TWELVE_DATA_API_KEY environment variable.")
        return {name: None for name in ASSETS.keys()}

    output_prices = {name: None for name in ASSETS.keys()}
    url = "https://api.twelvedata.com/price"
    
    total_assets = len(ASSETS)
    
    for idx, (display_name, provider_ticker) in enumerate(ASSETS.items(), 1):
        print(f"   ⏳ Fetching {display_name} ({idx}/{total_assets})...")
        
        params = {
            "symbol": provider_ticker,
            "apikey": api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 429:
                logger.warning(f"   ⚠️ Hit 429 rate limit on {display_name}. Retrying in 15 seconds...")
                time.sleep(15)
                response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                logger.error(f"   ❌ API Error ({response.status_code}) for {display_name}")
                continue
                
            data = response.json()
            
            if "status" in data and data["status"] == "error":
                logger.error(f"   ❌ Rejected: {data.get('message')}")
                continue

            if "price" in data:
                output_prices[display_name] = {
                    "price": float(data["price"])
                }
                
        except Exception as e:
            logger.error(f"   ❌ Exception during fetch for {display_name}: {e}")
            
        # Pacing window: 9 seconds between assets keeps us at ~6.6 requests per minute.
        # This completely avoids triggering the Twelve Data 429 free tier guardrail.
        if idx < total_assets:
            time.sleep(9)
            
    return output_prices

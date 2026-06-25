"""
MACRO BIAS ENGINE - Live Market Prices Ingestion (V3.0)
Uses Twelve Data Batch REST API to extract true spot assets, forex, and indices cleanly.
Bypasses data-center network firewalls and rate limits natively.
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)

FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "CADCHF"]

# Pure Cash Spot mappings for twelve data processing
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
    Fetches live market closes across all assets using a single Twelve Data batch call.
    Consumes exactly 1 API call credit out of your 8-per-minute rate limit ceiling.
    """
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    if not api_key:
        logger.error("❌ Missing TWELVE_DATA_API_KEY environment variable.")
        return {name: None for name in ASSETS.keys()}

    # Construct the batch payload string (e.g., "XAU/USD,XAG/USD,BTC/USD...")
    symbols_payload = ",".join(ASSETS.values())
    
    url = "https://api.twelvedata.com/price"
    params = {
        "symbol": symbols_payload,
        "apikey": api_key
    }
    
    output_prices = {name: None for name in ASSETS.keys()}
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            logger.error(f"❌ Twelve Data API error status: {response.status_code}")
            return output_prices
            
        data = response.json()
        
        if "status" in data and data["status"] == "error":
            logger.error(f"❌ Twelve Data execution rejected: {data.get('message')}")
            return output_prices

        # Map Twelve Data structures back into our system metrics
        for display_name, provider_ticker in ASSETS.items():
            asset_data = data.get(provider_ticker)
            
            if isinstance(asset_data, dict) and "price" in asset_data:
                output_prices[display_name] = {
                    "price": float(asset_data["price"])
                }
            elif isinstance(asset_data, (int, float)):
                output_prices[display_name] = {
                    "price": float(asset_data)
                }
                
        return output_prices

    except Exception as e:
        logger.error(f"❌ Critical exception during Twelve Data fetch sequence: {e}")
        return output_prices

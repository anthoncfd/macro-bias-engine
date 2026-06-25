"""
METALS SPOT PRICE FETCHER - Completely Free, No API Key Required
Fetches live spot prices AND historical daily closes for Gold and Silver.
Uses GoldPrice.Today (updates every 5 minutes).
"""
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

METAL_SYMBOLS = {
    "XAUUSD": {"display": "Gold"},
    "XAGUSD": {"display": "Silver"},
    "XPTUSD": {"display": "Platinum"},
    "XPDUSD": {"display": "Palladium"},
    "XRHUSD": {"display": "Rhodium"},
}

def fetch_live_metal_spots():
    """
    Fetch live spot prices for Gold and Silver from GoldPrice.Today.
    Returns a dict with keys: 'XAUUSD', 'XAGUSD' (prices in USD).
    """
    result = {}
    try:
        url = "https://GoldPrice.Today/api.php?data=live"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            usd_data = data.get("USD", {})
            
            if "gold_price" in usd_data:
                result["XAUUSD"] = float(usd_data["gold_price"])
                logger.info(f"📡 Gold spot: ${result['XAUUSD']:.2f}")
            if "silver_price" in usd_data:
                result["XAGUSD"] = float(usd_data["silver_price"])
                logger.info(f"📡 Silver spot: ${result['XAGUSD']:.2f}")
        else:
            logger.warning(f"GoldPrice.Today returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"GoldPrice.Today fetch failed: {e}")
    
    return result

def fetch_historical_close(metal, days_back=60):
    """
    Fetch historical daily closes for a metal from GoldPrice.Today.
    Returns a list of dicts: [{"date": "2026-06-25", "close": 3983.44}, ...]
    """
    try:
        url = f"https://GoldPrice.Today/api.php?data=historical&metal={metal}&days={days_back}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            historical = []
            for entry in data.get("data", []):
                historical.append({
                    "date": entry.get("date"),
                    "close": float(entry.get("price", 0))
                })
            return historical
        else:
            logger.warning(f"Historical data fetch failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"Historical fetch error: {e}")
    
    return []

def get_historical_data_for_supabase(metal_symbol, days_back=60):
    """
    Wrapper that returns historical data formatted for Supabase insertion.
    """
    metal_map = {
        "XAUUSD": "gold",
        "XAGUSD": "silver"
    }
    metal = metal_map.get(metal_symbol)
    if not metal:
        return []
    
    history = fetch_historical_close(metal, days_back)
    result = []
    for entry in history:
        if entry.get("date") and entry.get("close"):
            result.append({
                "ticker": metal_symbol,
                "latest_close": entry["close"],
                "created_at": entry["date"]
            })
    return result

"""
METALS SPOT PRICE FETCHER - Completely Free, No API Key Required
Uses GoldPrice.Today for Gold and Silver (updates every 5 minutes).
Other metals fall back to Yahoo Finance.
"""
import requests
import logging

logger = logging.getLogger(__name__)

# Mapping from display symbol (used in bot) to human-readable name
METAL_SYMBOLS = {
    "XAUUSD": {"display": "Gold"},
    "XAGUSD": {"display": "Silver"},
    "XPTUSD": {"display": "Platinum"},
    "XPDUSD": {"display": "Palladium"},
    "XRHUSD": {"display": "Rhodium"},
}

def fetch_metal_spots(api_key=None):
    """
    Fetch live spot prices for Gold and Silver from GoldPrice.Today.
    No API key required. Updates every ~5 minutes.
    Returns a dict with keys: 'XAUUSD', 'XAGUSD' (prices in USD).
    Other metals (Platinum, Palladium, Rhodium) are set to None.
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
                logger.info(f"📡 Gold spot from GoldPrice.Today: ${result['XAUUSD']:.2f}")
            if "silver_price" in usd_data:
                result["XAGUSD"] = float(usd_data["silver_price"])
                logger.info(f"📡 Silver spot from GoldPrice.Today: ${result['XAGUSD']:.2f}")
        else:
            logger.warning(f"GoldPrice.Today returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"GoldPrice.Today fetch failed: {e}")
    
    # For other metals, we don't have a free spot source, so set to None
    # The caller will fall back to Yahoo Finance for these.
    for sym in ["XPTUSD", "XPDUSD", "XRHUSD"]:
        result[sym] = None
    
    return result

def fetch_metal_spot(metal_symbol, api_key=None):
    """
    Convenience function to fetch a single metal price.
    Returns float or None.
    """
    all_prices = fetch_metal_spots(api_key)
    return all_prices.get(metal_symbol)"""
METALS SPOT PRICE FETCHER - Completely Free, No API Key Required
Uses GoldPrice.Today for Gold and Silver (updates every 5 minutes).
Other metals fall back to Yahoo Finance.
"""
import requests
import logging

logger = logging.getLogger(__name__)

# Mapping from display symbol (used in bot) to human-readable name
METAL_SYMBOLS = {
    "XAUUSD": {"display": "Gold"},
    "XAGUSD": {"display": "Silver"},
    "XPTUSD": {"display": "Platinum"},
    "XPDUSD": {"display": "Palladium"},
    "XRHUSD": {"display": "Rhodium"},
}

def fetch_metal_spots(api_key=None):
    """
    Fetch live spot prices for Gold and Silver from GoldPrice.Today.
    No API key required. Updates every ~5 minutes.
    Returns a dict with keys: 'XAUUSD', 'XAGUSD' (prices in USD).
    Other metals (Platinum, Palladium, Rhodium) are set to None.
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
                logger.info(f"📡 Gold spot from GoldPrice.Today: ${result['XAUUSD']:.2f}")
            if "silver_price" in usd_data:
                result["XAGUSD"] = float(usd_data["silver_price"])
                logger.info(f"📡 Silver spot from GoldPrice.Today: ${result['XAGUSD']:.2f}")
        else:
            logger.warning(f"GoldPrice.Today returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"GoldPrice.Today fetch failed: {e}")
    
    # For other metals, we don't have a free spot source, so set to None
    # The caller will fall back to Yahoo Finance for these.
    for sym in ["XPTUSD", "XPDUSD", "XRHUSD"]:
        result[sym] = None
    
    return result

def fetch_metal_spot(metal_symbol, api_key=None):
    """
    Convenience function to fetch a single metal price.
    Returns float or None.
    """
    all_prices = fetch_metal_spots(api_key)
    return all_prices.get(metal_symbol)

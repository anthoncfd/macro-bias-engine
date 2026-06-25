"""
METALS SPOT PRICE FETCHER - Completely Free, No API Key
Uses GoldPrice.Today for live spot prices (updates every 5 minutes).
"""
import requests
import logging

logger = logging.getLogger(__name__)

def fetch_metal_spots():
    """
    Fetch live spot prices for Gold (XAUUSD) and Silver (XAGUSD) from GoldPrice.Today.
    Returns a dict with keys 'XAUUSD' and 'XAGUSD' containing the price in USD,
    or an empty dict if the API call fails.
    """
    result = {}
    try:
        url = "https://GoldPrice.Today/api.php?data=live"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            usd = data.get("USD", {})
            if "gold_price" in usd:
                result["XAUUSD"] = float(usd["gold_price"])
                logger.info(f"📡 Gold spot: ${result['XAUUSD']:.2f}")
            if "silver_price" in usd:
                result["XAGUSD"] = float(usd["silver_price"])
                logger.info(f"📡 Silver spot: ${result['XAGUSD']:.2f}")
        else:
            logger.warning(f"GoldPrice.Today returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"GoldPrice.Today error: {e}")
    return result

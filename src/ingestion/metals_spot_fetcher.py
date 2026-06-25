"""
METALS SPOT PRICE FETCHER
Fetches live spot prices for Gold, Silver, Platinum, Palladium, Rhodium.
Primary source: Metals-API (requires free API key)
Fallback: GoldPrice.Today (no key) for XAU and XAG only.
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────
METALS_API_URL = "https://api.metals-api.com/api/latest"
GOLDPRICE_API_URL = "https://GoldPrice.Today/api.php?data=live"

# Mapping from display symbol (used in bot) to API symbol and human-readable name
METAL_SYMBOLS = {
    "XAUUSD": {"api_symbol": "XAU", "display": "Gold"},
    "XAGUSD": {"api_symbol": "XAG", "display": "Silver"},
    "XPTUSD": {"api_symbol": "XPT", "display": "Platinum"},
    "XPDUSD": {"api_symbol": "XPD", "display": "Palladium"},
    "XRHUSD": {"api_symbol": "XRH", "display": "Rhodium"},
}

# ─── Primary Source: Metals-API ──────────────────────────────────────
def fetch_metals_api(api_key, symbols=None):
    """
    Fetch multiple metal spot prices from Metals-API.
    Handles unit inversion (1 / rate) because API returns unit per USD/EUR.
    Returns a dict {api_symbol: price} or None if fails.
    """
    if symbols is None:
        symbols = [m["api_symbol"] for m in METAL_SYMBOLS.values()]

    try:
        params = {
            "access_key": api_key,
            "base": "USD",  # Note: Free plan ignores this and forces EUR, but rates are still relative
            "symbols": ",".join(symbols)
        }
        response = requests.get(METALS_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # CRITICAL: Metals-API returns success: false inside a 200 OK wrapper on failure
            if not data.get("success", True):
                error_info = data.get("error", {})
                logger.warning(f"Metals-API error code {error_info.get('code')}: {error_info.get('type')}")
                return None
                
            rates = data.get("rates", {})
            prices = {}
            for symbol in symbols:
                if symbol in rates and rates[symbol] is not None:
                    raw_rate = float(rates[symbol])
                    # CRITICAL: Convert "ounces per dollar" to "dollars per ounce"
                    if raw_rate > 0:
                        prices[symbol] = round(1.0 / raw_rate, 2)
                    else:
                        logger.warning(f"Metals-API returned invalid rate (<= 0) for {symbol}")
            
            if prices:
                logger.info(f"📡 Metals-API: fetched {len(prices)} metals")
                return prices
            else:
                logger.warning("Metals-API returned no valid rates")
        else:
            logger.warning(f"Metals-API returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"Metals-API fetch failed: {e}")
    return None

# ─── Fallback: GoldPrice.Today (no API key) ──────────────────────────
def fetch_goldprice_today_fallback():
    """
    Fallback for Gold and Silver from GoldPrice.Today.
    Returns a dict with keys 'XAU' and 'XAG' if available.
    """
    try:
        response = requests.get(GOLDPRICE_API_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            usd_data = data.get("USD", {})
            prices = {}
            if "gold_price" in usd_data:
                prices["XAU"] = float(usd_data["gold_price"])
            if "silver_price" in usd_data:
                prices["XAG"] = float(usd_data["silver_price"])
            if prices:
                logger.info(f"📡 GoldPrice.Today fallback: {prices}")
                return prices
        else:
            logger.warning(f"GoldPrice.Today returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"GoldPrice.Today fallback failed: {e}")
    return None

# ─── Main Fetcher ──────────────────────────────────────────────────────
def fetch_metal_spots(api_key=None):
    """
    Fetch all metal spot prices.
    Returns a dict with keys like 'XAUUSD', 'XAGUSD', etc.
    Missing metals will have value None.
    """
    result = {}

    # Try Metals-API first if key is provided
    if api_key:
        metals_data = fetch_metals_api(api_key)
        if metals_data:
            for display_symbol, meta in METAL_SYMBOLS.items():
                api_sym = meta["api_symbol"]
                if api_sym in metals_data:
                    result[display_symbol] = metals_data[api_sym]
            # If we got all metals, return early
            if len(result) == len(METAL_SYMBOLS):
                return result

    # Fallback to GoldPrice.Today for Gold and Silver if they are missing
    if "XAUUSD" not in result or "XAGUSD" not in result:
        fallback = fetch_goldprice_today_fallback()
        if fallback:
            if "XAUUSD" not in result and "XAU" in fallback:
                result["XAUUSD"] = fallback["XAU"]
            if "XAGUSD" not in result and "XAG" in fallback:
                result["XAGUSD"] = fallback["XAG"]

    # Ensure all metals are present (fill missing with None)
    for sym in METAL_SYMBOLS:
        if sym not in result:
            result[sym] = None

    return result

# ─── Convenience function to get a single metal price ────────────────
def fetch_metal_spot(metal_symbol, api_key=None):
    """
    Fetch a single metal spot price (e.g., 'XAUUSD').
    Returns float or None if unavailable.
    """
    all_prices = fetch_metal_spots(api_key)
    return all_prices.get(metal_symbol)

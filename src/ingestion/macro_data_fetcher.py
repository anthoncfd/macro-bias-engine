"""
MACRO DATA FETCHER - Fetches DXY, VIX, Yields from Yahoo Finance
"""
import requests
import time
import random
import numpy as np

def fetch_macro_data():
    """
    Fetches all macro indicators and calculates Z-scores.
    """
    macro_tickers = {
        "dxy": "DX-Y.NYB",
        "vix": "^VIX",
        "us2y": "^IRX",
        "us10y": "^TNX"
    }
    
    results = {}
    
    for name, ticker in macro_tickers.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {"range": "5d", "interval": "1d"}
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
                        results[name] = float(valid_closes[-1])
                    else:
                        results[name] = None
            else:
                results[name] = None
        except:
            results[name] = None
        
        time.sleep(random.uniform(0.3, 0.5))
    
    # Calculate spread
    if results.get("us10y") and results.get("us2y"):
        results["spread"] = results["us10y"] - results["us2y"]
    else:
        results["spread"] = None
    
    # Generate Z-scores (simplified for now)
    # In production, these would use rolling historical means
    results["dxy_z"] = (results.get("dxy", 100) - 103) / 3
    results["vix_z"] = (results.get("vix", 20) - 18) / 5
    results["spread_z"] = (results.get("spread", 0.5) - 0.3) / 0.2
    
    return results

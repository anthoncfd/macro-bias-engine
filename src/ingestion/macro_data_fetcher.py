"""
MACRO DATA FETCHER - Fetches DXY, VIX, Yields from Yahoo Finance
"""
import requests
import time
import random

def fetch_macro_data():
    """Fetches macro indicators: DXY, VIX, 10Y yield."""
    macro_tickers = {
        "dxy": "DX-Y.NYB",
        "vix": "^VIX",
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
        except Exception as e:
            results[name] = None
        time.sleep(random.uniform(0.3, 0.5))
    
    return results

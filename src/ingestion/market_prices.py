def fetch_live_price(display_name, tickers):
    """
    Fetches the current intraday price for an asset.
    Uses 5-minute bars to get the most recent traded price.
    """
    for ticker in tickers:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {
                "range": "1d",      # Fetch today's data
                "interval": "5m"    # 5-minute bars for current price
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                chart_data = data.get("chart", {}).get("result", [None])[0]
                if chart_data:
                    indicators = chart_data.get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        return float(valid_closes[-1])
            else:
                print(f"   ⚠️ Live price HTTP {response.status_code} for {ticker}")
                
        except Exception as e:
            print(f"   ⚠️ Live price error for {ticker}: {e}")
            continue
    
    return None  # No live price available

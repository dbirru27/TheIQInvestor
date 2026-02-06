import yfinance as yf
import pandas as pd
import json
import sys

def get_chart_data(ticker):
    print(f"Fetching history for {ticker}...")
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty:
            return None
        
        # Flatten MultiIndex columns if present (yfinance v0.2+)
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.get_level_values(0)
            except:
                pass

        # Convert index to strings and select Close prices
        df.index = df.index.strftime('%Y-%m-%d')
        return {
            "dates": df.index.tolist(),
            "prices": [round(float(p), 2) for p in df['Close'].tolist()]
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

if __name__ == "__main__":
    tickers = ["XLB", "FCX"]
    data = {}
    for t in tickers:
        res = get_chart_data(t)
        if res:
            data[t] = res
            
    with open("charts_data.json", "w") as f:
        json.dump(data, f)
    print("\nDone! Saved to charts_data.json")

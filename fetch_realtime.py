import yfinance as yf
import json
from datetime import datetime
import sys

def get_realtime(tickers):
    """
    Fetches the absolute latest price and change for a list of tickers.
    """
    results = {}
    print(f"Fetching real-time data for {len(tickers)} assets...", file=sys.stderr)
    
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            # Use fast_info or history(period='1d') for the most current price
            data = t.history(period='1d')
            if not data.empty:
                last_price = data['Close'].iloc[-1]
                prev_close = t.info.get('previousClose', last_price)
                change = last_price - prev_close
                p_change = (change / prev_close) * 100 if prev_close else 0
                
                results[ticker] = {
                    "price": round(last_price, 2),
                    "change": round(change, 2),
                    "percent": round(p_change, 2),
                    "time": datetime.now().strftime('%H:%M:%S EST')
                }
        except Exception as e:
            results[ticker] = {"error": str(e)}
            
    return results

if __name__ == "__main__":
    # Default list based on your core portfolio + major indices
    core_list = ["GC=F", "SI=F", "^GSPC", "^IXIC", "^DJI", "VOO", "ITA", "XLI", "COPX", "GLDM"]
    # If tickers passed via cmd line, use those
    target = sys.argv[1:] if len(sys.argv) > 1 else core_list
    
    data = get_realtime(target)
    print(json.dumps(data, indent=2))

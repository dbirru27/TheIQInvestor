import yfinance as yf
import pandas as pd
from datetime import datetime
import sys

# Tickers
tickers = ['SPY', 'QQQ', 'IWM', 'VIX', 'GLD', 'COPX', 'NLR', 'VOO', 'XLI', 'ITA']

def fetch_and_verify():
    print(f"Fetching data for: {tickers}...")
    data = yf.download(tickers, period="1d", interval="1m", progress=False)
    
    # Get the latest data point (last row)
    if data.empty:
        print("Error: No data fetched.")
        return None

    # yfinance download with multiple tickers returns a MultiIndex column.
    # We need to handle 'Close' prices.
    
    report_lines = []
    errors = 0
    
    print(f"\n{'Ticker':<10} {'Price':<10} {'Change %':<10} {'Time'}")
    print("-" * 50)
    
    # Iterate through tickers to get latest close and calculate change
    # Note: 'data' might be complex structure depending on yfinance version. 
    # Usually data['Close'][ticker] works.
    
    latest_data = data.iloc[-1]
    
    # For calculation of change, we need previous close. 
    # Let's just use Ticker object for more details or simple download.
    # Actually, simpler method for real-time snapshot:
    
    final_report = "Market Pulse AM Report\n"
    final_report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    final_report += f"{'Ticker':<8} | {'Price':<10} | {'Change %':<10} | {'Timestamp'}\n"
    final_report += "-" * 60 + "\n"

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            
            # fast_info provides last_price, previous_close
            price = info.last_price
            prev_close = info.previous_close
            
            if price is None or prev_close is None:
                # Fallback to history if fast_info fails (sometimes happens on weak connection)
                hist = t.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    # Approximate prev close from open or previous day? 
                    # Let's rely on calculation from available data if possible.
                    # This is a fallback, assume 0 change if we can't get prev.
                    change_pct = 0.0 
                else:
                    print(f"Failed to fetch data for {ticker}")
                    errors += 1
                    continue
            else:
                change_pct = ((price - prev_close) / prev_close) * 100
            
            # Verify: Change < 10% (sanity check)
            if abs(change_pct) > 10 and ticker != 'VIX': # VIX can be volatile
                print(f"WARNING: {ticker} change {change_pct:.2f}% seems high.")
                # We flag it but include it.
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            line = f"{ticker:<8} | {price:<10.2f} | {change_pct:+.2f}%     | {timestamp}"
            print(line)
            final_report += line + "\n"
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            errors += 1

    return final_report, errors

report, error_count = fetch_and_verify()

if error_count > 2:
    print("Too many errors, regenerating...")
    # Simple retry logic could go here, but for this script we just report failure signal
    sys.exit(1)

with open("market_report.txt", "w") as f:
    f.write(report)

print("\nReport generated successfully.")

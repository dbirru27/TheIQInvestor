import yfinance as yf
import pandas as pd
from datetime import datetime
import sys

# Tickers - Note ^VIX for Yahoo Finance
tickers = ['SPY', 'QQQ', 'IWM', '^VIX', 'GLD', 'COPX', 'NLR', 'VOO', 'XLI', 'ITA']

def fetch_and_verify():
    print(f"Fetching data for: {tickers}...")
    
    final_report = "Market Pulse AM Report\n"
    final_report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    final_report += f"{'Ticker':<8} | {'Price':<10} | {'Change %':<10} | {'Timestamp'}\n"
    final_report += "-" * 60 + "\n"
    
    errors = 0
    print(f"\n{'Ticker':<8} | {'Price':<10} | {'Change %':<10} | {'Timestamp'}")
    print("-" * 60)

    for ticker in tickers:
        try:
            # Fetch data
            t = yf.Ticker(ticker)
            
            # Use fast_info for real-time
            try:
                price = t.fast_info.last_price
                prev_close = t.fast_info.previous_close
            except:
                 # Fallback
                 hist = t.history(period="1d")
                 if not hist.empty:
                     price = hist['Close'].iloc[-1]
                     prev_close = hist['Open'].iloc[0] # Approx
                 else:
                     price = None
            
            if price is None:
                print(f"Failed to fetch data for {ticker}")
                errors += 1
                continue
            
            # Calculate change
            if prev_close and prev_close != 0:
                change_pct = ((price - prev_close) / prev_close) * 100
            else:
                change_pct = 0.0

            # Verify: Change < 10% (sanity check, except VIX which is volatile)
            if abs(change_pct) > 10 and 'VIX' not in ticker: 
                print(f"WARNING: {ticker} change {change_pct:.2f}% seems high.")
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # Display name (remove ^ for cleanliness if desired, but keep for accuracy)
            display_ticker = ticker.replace('^', '') 
            
            line = f"{display_ticker:<8} | {price:<10.2f} | {change_pct:+.2f}%     | {timestamp}"
            print(line)
            final_report += line + "\n"
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            errors += 1

    return final_report, errors

report, error_count = fetch_and_verify()

# Threshold check
if error_count > 2:
    print(f"Too many errors ({error_count}), flagging for regeneration...")
    sys.exit(1)

with open("market_report_v2.txt", "w") as f:
    f.write(report)

print("\nReport generated successfully.")

import yfinance as yf
import sys
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Tickers to check
TICKERS = ["SPY", "QQQ", "IWM", "VIX", "GLD", "COPX", "NLR", "VOO", "XLI", "ITA"]

def fetch_and_verify():
    print("Fetching data...")
    data = yf.download(TICKERS, period="5d", progress=False)
    
    report_lines = []
    report_lines.append(f"Market Pulse Verification Report - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("-" * 40)
    
    all_verified = True
    
    # Check each ticker
    # data['Close'] gives the closing prices. We want the latest available price.
    # If market is open, 'Close' for today might be updated live or we use 'Adj Close'.
    # yfinance download usually gives EOD data for history. For real-time, we might need Ticker object.
    
    for ticker_symbol in TICKERS:
        try:
            ticker = yf.Ticker(ticker_symbol)
            # fast_info is often better for real-time
            price = ticker.fast_info.last_price
            prev_close = ticker.fast_info.previous_close
            
            if price is None or prev_close is None:
                print(f"Skipping {ticker_symbol}: No data")
                continue
                
            change_pct = ((price - prev_close) / prev_close) * 100
            
            status = "OK"
            if abs(change_pct) > 2.0 and ticker_symbol != "VIX": # VIX can move > 2% easily
                 status = "CHECK"
                 # We flag it but for now we won't stop unless it's huge > 10% as per prompt "reasonable <10%"
                 if abs(change_pct) > 10.0:
                     status = "ALERT"
                     all_verified = False

            line = f"{ticker_symbol:<5} | Price: {price:>8.2f} | Prev: {prev_close:>8.2f} | Chg: {change_pct:>6.2f}% | {status}"
            report_lines.append(line)
            
        except Exception as e:
            print(f"Error fetching {ticker_symbol}: {e}")
            all_verified = False

    report_text = "\n".join(report_lines)
    print(report_text)
    
    if all_verified:
        return report_text
    else:
        print("Verification FAILED. Large anomalies detected.")
        return None

def send_email(body):
    # This function is a placeholder. The agent will use the 'message' tool or 'email_sender.py' if available.
    # We will print the body to stdout for the agent to capture.
    print("\n--- EMAIL BODY START ---")
    print(body)
    print("--- EMAIL BODY END ---")

if __name__ == "__main__":
    report = fetch_and_verify()
    if report:
        send_email(report)
    else:
        sys.exit(1)

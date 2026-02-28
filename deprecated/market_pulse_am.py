import yfinance as yf
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys

# Configuration
TICKERS = ["SPY", "QQQ", "IWM", "^VIX", "GLD", "COPX", "NLR", "VOO", "XLI", "ITA"]
RECIPIENT = "dbirru@gmail.com"
SUBJECT = "Market Pulse AM (Verified)"

def get_realtime_data(ticker_symbol):
    """Fetches real-time price and previous close."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        # fast_info provides basic real-time data efficiently
        try:
            price = ticker.fast_info.last_price
            prev_close = ticker.fast_info.previous_close
        except:
             # Fallback to history if fast_info fails (sometimes happens)
             hist = ticker.history(period="2d")
             if len(hist) >= 2:
                 prev_close = hist['Close'].iloc[-2]
                 price = hist['Close'].iloc[-1]
             elif len(hist) == 1:
                 price = hist['Close'].iloc[-1]
                 prev_close = price # Can't calculate change
             else:
                 return None, None
        
        return price, prev_close
    except Exception as e:
        print(f"Error fetching {ticker_symbol}: {e}")
        return None, None

def generate_report():
    print(f"Starting Market Pulse AM for: {', '.join(TICKERS)}")
    
    report_lines = []
    report_lines.append(f"Market Pulse AM Report")
    report_lines.append(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("-" * 60)
    report_lines.append(f"{'Ticker':<6} | {'Price':>8} | {'Prev':>8} | {'Chg %':>7} | {'Status':<10}")
    report_lines.append("-" * 60)
    
    all_verified = True
    alerts = []

    for symbol in TICKERS:
        price, prev_close = get_realtime_data(symbol)
        
        if price is None or prev_close is None:
            report_lines.append(f"{symbol:<6} | {'N/A':>8} | {'N/A':>8} | {'N/A':>7} | ERROR")
            all_verified = False # strict verification?
            continue

        if prev_close == 0:
             change_pct = 0.0
        else:
             change_pct = ((price - prev_close) / prev_close) * 100
        
        abs_change = abs(change_pct)
        
        # VERIFICATION LOGIC
        # 1. Is price reasonable (<10% change)?
        status = "OK"
        if abs_change > 10.0:
            status = "CRITICAL"
            alerts.append(f"CRITICAL: {symbol} moved {change_pct:.2f}% (Limit: 10%)")
            all_verified = False
        
        # 2. Is price within 1% of previous close? (Soft check/info)
        elif abs_change > 1.0:
            status = "VOLATILE"
            if symbol != "VIX": # VIX is expected to be volatile
                alerts.append(f"Note: {symbol} moved {change_pct:.2f}% (>1%)")
        
        report_lines.append(f"{symbol:<6} | {price:>8.2f} | {prev_close:>8.2f} | {change_pct:>+7.2f}% | {status}")

    report_content = "\n".join(report_lines)
    
    if alerts:
        report_content += "\n\n--- VERIFICATION ALERTS ---\n"
        report_content += "\n".join(alerts)
    
    return report_content, all_verified

def send_email_via_script(body):
    import subprocess
    try:
        # Create a temporary file for the body to avoid shell escaping issues
        with open("temp_email_body.txt", "w") as f:
            f.write(body)
        
        cmd = ["python3", "email_sender.py", RECIPIENT, SUBJECT, "temp_email_body.txt"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Email sent successfully.")
            return True
        else:
            print(f"Failed to send email: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
    finally:
        if os.path.exists("temp_email_body.txt"):
            os.remove("temp_email_body.txt")

if __name__ == "__main__":
    report, verified = generate_report()
    
    print("\n--- REPORT PREVIEW ---")
    print(report)
    print("----------------------\n")

    if verified:
        print("Verification PASSED. Sending email...")
        if send_email_via_script(report):
            print("Action complete.")
        else:
            print("Action failed at email step.")
            sys.exit(1)
    else:
        print("Verification FAILED (Critical anomalies detected). skipping email.")
        sys.exit(1)

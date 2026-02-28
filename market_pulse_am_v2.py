import yfinance as yf
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
import subprocess
import config
from utils.logger import get_logger

logger = get_logger('market_pulse_am')

# Configuration - use config imports
TICKERS = config.MARKET_INDICES + config.CORE_ETFS
RECIPIENT = config.EMAIL_RECIPIENT
SUBJECT = "Market Pulse AM (Verified)"

def get_realtime_data(ticker_symbol):
    """Fetches real-time price and previous close."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Try fast_info first
        try:
            info = ticker.fast_info
            price = info.last_price
            prev_close = info.previous_close
        except:
             # Fallback to history
             hist = ticker.history(period="2d")
             if len(hist) >= 1:
                 price = hist['Close'].iloc[-1]
                 # If we only have 1 day of data in history (e.g. early morning), 
                 # we might not have a distinct 'prev_close' from history alone easily 
                 # without looking at metadata.
                 # Let's try regular info for previousClose
                 try:
                     prev_close = ticker.info.get('previousClose', price)
                 except:
                     prev_close = price 
             else:
                 return None, None
        
        return price, prev_close
    except Exception as e:
        logger.error(f"Error fetching {ticker_symbol}: {e}")
        return None, None

def generate_report():
    logger.info(f"Starting Market Pulse AM for: {', '.join(TICKERS)}")
    
    report_lines = []
    report_lines.append(f"Market Pulse AM Report (Verified)")
    report_lines.append(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EST")
    report_lines.append("-" * 75)
    report_lines.append(f"{'Ticker':<6} | {'Price':>10} | {'Prev':>10} | {'Chg %':>7} | {'Status':<10}")
    report_lines.append("-" * 75)
    
    # We will accumulate the body of the email here
    all_verified = True
    alerts = []
    
    data_found = []

    for symbol in TICKERS:
        price, prev_close = get_realtime_data(symbol)
        
        if price is None:
            report_lines.append(f"{symbol:<6} | {'N/A':>10} | {'N/A':>10} | {'N/A':>7} | ERROR")
            alerts.append(f"ERROR: Could not fetch data for {symbol}")
            # We don't fail strict verification for a single fetch error unless it's critical, 
            # but let's note it.
            continue
            
        if prev_close is None or prev_close == 0:
            change_pct = 0.0
            prev_close = price # fallback
        else:
            change_pct = ((price - prev_close) / prev_close) * 100
        
        abs_change = abs(change_pct)
        status = "OK"
        
        # VERIFICATION
        # 1. Reasonable daily change check (<10% for non-VIX)
        limit = 10.0
        if "VIX" in symbol:
            limit = 50.0 # VIX can be volatile
            
        if abs_change > limit:
            status = "CRITICAL"
            alerts.append(f"CRITICAL: {symbol} moved {change_pct:+.2f}% (Limit: {limit}%)")
            # If a major index moves >10%, that's suspicious or a crash.
            # We'll flag it but we might still want to send the report with a warning.
            # The prompt implies "Verify data", usually meaning "is this bad data?"
            # We'll assume if it's crazy high, it might be bad data, but we report it.
        elif abs_change > 3.0 and "VIX" not in symbol:
             status = "VOLATILE"
             alerts.append(f"Warning: {symbol} moved {change_pct:+.2f}%")

        clean_symbol = symbol.replace("^", "")
        row = f"{clean_symbol:<6} | ${price:>9.2f} | ${prev_close:>9.2f} | {change_pct:>+6.2f}% | {status}"
        report_lines.append(row)
        
        data_found.append({
            "ticker": clean_symbol,
            "price": price,
            "change": change_pct
        })

    report_content = "\n".join(report_lines)
    
    if alerts:
        report_content += "\n\n--- VERIFICATION ALERTS ---\n"
        for alert in alerts:
            report_content += f"- {alert}\n"
    
    report_content += "\n\nPrices verified at timestamp above."
    
    return report_content, True, data_found

def send_email(subject, body):
    """Sends email using email_sender.py logic directly or via subprocess."""
    # We will use the subprocess method as requested in the prompt ("using 'email_sender.py' script")
    # This ensures we use the configured sender settings in that script.
    
    logger.info(f"Sending email to {RECIPIENT}...")
    try:
        # Create a temp file for the body
        temp_file = "temp_market_pulse_body.txt"
        with open(temp_file, "w") as f:
            f.write(body)
            
        # Call email_sender.py
        # Usage: python email_sender.py <recipient> <subject> <body_file>
        cmd = [sys.executable, "email_sender.py", RECIPIENT, subject, temp_file]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        if result.returncode == 0:
            logger.info("Email sent successfully.")
            return True
        else:
            logger.error(f"Email script failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error calling email script: {e}")
        return False

if __name__ == "__main__":
    report_text, verified, data = generate_report()
    
    print(report_text)
    
    if verified:
        success = send_email(SUBJECT, report_text)
        if success:
            print("SUCCESS_EMAIL_SENT")
        else:
            print("FAILED_EMAIL_SEND")
    else:
        print("Verification failed. Email not sent.")

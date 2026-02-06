#!/usr/bin/env python3
"""
Nightly cache refresh for Russell 1000 + holdings
Runs with rate limiting to avoid Yahoo Finance bans
"""
import os
import sys
import time
from datetime import datetime
import yfinance as yf

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Rate limiting config
DELAY_BETWEEN_TICKERS = 0.5  # seconds
BATCH_SIZE = 50
BATCH_PAUSE = 10  # seconds between batches

def load_tickers():
    """Load all ticker sources"""
    tickers = set()
    
    # Priority sources
    sources = [
        'russell1000_tickers.txt',  # Russell 1000
        'vug_tickers.txt',          # VUG holdings
        'all_holdings.txt',         # User holdings
        'holdings.txt'              # Core holdings
    ]
    
    for f_path in sources:
        if os.path.exists(f_path):
            with open(f_path, 'r') as f:
                for line in f:
                    t = line.strip().upper()
                    if t and len(t) <= 6:
                        tickers.add(t)
    
    return sorted(tickers)

def refresh_ticker(symbol, db):
    """Refresh a single ticker with rate limiting"""
    try:
        ticker_obj = yf.Ticker(symbol)
        
        # Fetch price history
        hist = ticker_obj.history(period="1y")
        if hist is not None and not hist.empty:
            db._save_prices(symbol, hist)
        
        # Fetch fundamentals
        info = ticker_obj.info
        if info:
            db.save_fundamentals(symbol, info)
        
        return True
    except Exception as e:
        return False

def main():
    print(f"🚀 Cache Refresh Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Import DB
    try:
        from market_data import MarketDB
        db = MarketDB()
    except Exception as e:
        print(f"❌ Failed to connect to DB: {e}")
        sys.exit(1)
    
    tickers = load_tickers()
    total = len(tickers)
    print(f"📊 Refreshing {total} tickers...")
    
    success = 0
    failed = 0
    
    for i, ticker in enumerate(tickers, 1):
        result = refresh_ticker(ticker, db)
        
        if result:
            success += 1
        else:
            failed += 1
        
        # Progress update every 50
        if i % 50 == 0:
            print(f"  [{i}/{total}] ✅ {success} | ❌ {failed}")
        
        # Rate limiting
        time.sleep(DELAY_BETWEEN_TICKERS)
        
        # Batch pause
        if i % BATCH_SIZE == 0 and i < total:
            print(f"  ⏸️  Batch pause ({BATCH_PAUSE}s)...")
            time.sleep(BATCH_PAUSE)
    
    db.close()
    
    print(f"\n✅ Cache Refresh Complete!")
    print(f"   Success: {success}/{total}")
    print(f"   Failed:  {failed}/{total}")
    print(f"   Time:    {datetime.now().strftime('%H:%M')}")

if __name__ == "__main__":
    main()

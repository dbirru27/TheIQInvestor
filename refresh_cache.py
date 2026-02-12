#!/usr/bin/env python3
"""
Nightly cache refresh for Russell 1000 + holdings
Runs with rate limiting to avoid Yahoo Finance bans
"""
import os
import sys
import time
import json
from datetime import datetime
import yfinance as yf
import sqlite3

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Rate limiting config
DELAY_BETWEEN_TICKERS = 0.5  # seconds
BATCH_SIZE = 50
BATCH_PAUSE = 10  # seconds between batches

DB_PATH = os.path.join(os.getcwd(), 'market_data.db')

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

def refresh_revenue_history(symbol, conn):
    """Fetch and store annual revenue history"""
    try:
        ticker_obj = yf.Ticker(symbol)
        
        # Get annual financials
        financials = ticker_obj.financials
        if financials is None or financials.empty:
            return False
        
        # Extract Total Revenue row
        if 'Total Revenue' not in financials.index:
            return False
        
        revenue_row = financials.loc['Total Revenue']
        c = conn.cursor()
        
        # Store each year's revenue
        for date_col, revenue in revenue_row.items():
            if pd.notna(revenue) and revenue > 0:
                # Extract year from column date
                fiscal_year = pd.Timestamp(date_col).year
                
                # Calculate YoY growth if we have prior year
                growth_yoy = None
                if fiscal_year > 2020:  # Need at least 2021 for comparison
                    c.execute(
                        "SELECT total_revenue FROM revenue_history WHERE symbol = ? AND fiscal_year = ?",
                        (symbol, fiscal_year - 1)
                    )
                    prior = c.fetchone()
                    if prior and prior[0] and prior[0] > 0:
                        growth_yoy = (revenue - prior[0]) / prior[0]
                
                # Upsert revenue data
                c.execute('''
                    INSERT OR REPLACE INTO revenue_history 
                    (symbol, fiscal_year, total_revenue, revenue_growth_yoy, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (symbol, fiscal_year, float(revenue), growth_yoy))
        
        conn.commit()
        return True
    except Exception as e:
        return False

def main():
    print(f"🚀 Cache Refresh Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Import DB
    try:
        from market_data import MarketDB
        import pandas as pd  # Needed for revenue refresh
        db = MarketDB()
    except Exception as e:
        print(f"❌ Failed to connect to DB: {e}")
        sys.exit(1)
    
    # Also get direct SQLite connection for revenue_history
    conn = sqlite3.connect(DB_PATH)
    
    tickers = load_tickers()
    total = len(tickers)
    print(f"📊 Refreshing {total} tickers...")
    
    success = 0
    failed = 0
    revenue_success = 0
    
    for i, ticker in enumerate(tickers, 1):
        # Refresh prices and fundamentals
        result = refresh_ticker(ticker, db)
        
        # Refresh revenue history (every 5th ticker to reduce API load)
        if i % 5 == 0:
            rev_result = refresh_revenue_history(ticker, conn)
            if rev_result:
                revenue_success += 1
        
        if result:
            success += 1
        else:
            failed += 1
        
        # Progress update every 50
        if i % 50 == 0:
            print(f"  [{i}/{total}] ✅ {success} | ❌ {failed} | 💰 {revenue_success}")
        
        # Rate limiting
        time.sleep(DELAY_BETWEEN_TICKERS)
        
        # Batch pause
        if i % BATCH_SIZE == 0 and i < total:
            print(f"  ⏸️  Batch pause ({BATCH_PAUSE}s)...")
            time.sleep(BATCH_PAUSE)
    
    db.close()
    conn.close()
    
    print(f"\n✅ Cache Refresh Complete!")
    print(f"   Price/Fundamental Success: {success}/{total}")
    print(f"   Revenue History Updated:   {revenue_success}")
    print(f"   Failed:                    {failed}/{total}")
    print(f"   Time:                      {datetime.now().strftime('%H:%M')}")

if __name__ == "__main__":
    main()

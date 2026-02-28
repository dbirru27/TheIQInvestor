#!/usr/bin/env python3
"""
Nightly cache refresh for Russell 1000 + holdings
Runs with rate limiting to avoid Yahoo Finance bans
v2.0: Added retry with exponential backoff, error categorization, logging
"""
import os
import sys
import time
import json
import random
from datetime import datetime
from collections import defaultdict
import yfinance as yf
import sqlite3

# Import centralized logger
sys.path.insert(0, os.path.dirname(__file__))
from utils.logger import get_logger

# Initialize logger
logger = get_logger('investiq_refresh')

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Rate limiting config (REDUCED from 5 to 2 workers)
DELAY_BETWEEN_TICKERS = 0.5  # seconds between submissions
MAX_WORKERS = 2              # Reduced from 5
MAX_RETRIES = 3              # Retry attempts
INITIAL_BACKOFF = 30         # Starting backoff in seconds

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

def categorize_error(error_msg: str) -> str:
    """Categorize error type for better diagnostics"""
    msg_lower = str(error_msg).lower()
    
    if 'rate' in msg_lower or '429' in msg_lower or 'too many' in msg_lower:
        return 'RATE_LIMIT'
    elif 'not found' in msg_lower or '404' in msg_lower or 'no data' in msg_lower:
        return 'BAD_TICKER'
    elif 'timeout' in msg_lower or 'connection' in msg_lower or 'network' in msg_lower:
        return 'NETWORK_ERROR'
    elif 'none' in msg_lower and 'attribute' in msg_lower:
        return 'INVALID_DATA'
    else:
        return 'UNKNOWN_ERROR'

def refresh_ticker(symbol, db, retry_count=0):
    """
    Refresh a single ticker with exponential backoff retry
    
    Args:
        symbol: Ticker symbol
        db: MarketDB instance
        retry_count: Current retry attempt (0-indexed)
    
    Returns:
        tuple: (success: bool, error_category: str or None)
    """
    try:
        ticker_obj = yf.Ticker(symbol)
        
        # Fetch price history
        hist = ticker_obj.history(period="1y")
        if hist is not None and not hist.empty:
            db._save_prices(symbol, hist)
        else:
            return (False, 'INVALID_DATA')
        
        # Fetch fundamentals
        info = ticker_obj.info
        if info:
            db.save_fundamentals(symbol, info)
        else:
            logger.warning(f"{symbol}: No fundamentals available")
        
        return (True, None)
        
    except Exception as e:
        error_category = categorize_error(str(e))
        
        # Rate limit errors should trigger retry with backoff
        if error_category == 'RATE_LIMIT' and retry_count < MAX_RETRIES:
            # Exponential backoff: 30s, 60s, 120s + random jitter
            backoff_time = INITIAL_BACKOFF * (2 ** retry_count) + random.uniform(0, 5)
            logger.warning(f"{symbol}: Rate limited. Retry {retry_count+1}/{MAX_RETRIES} in {backoff_time:.1f}s")
            time.sleep(backoff_time)
            return refresh_ticker(symbol, db, retry_count + 1)
        
        # Network errors get one retry with shorter backoff
        elif error_category == 'NETWORK_ERROR' and retry_count < 1:
            logger.warning(f"{symbol}: Network error. Retrying in 10s...")
            time.sleep(10)
            return refresh_ticker(symbol, db, retry_count + 1)
        
        # Log the error
        logger.error(f"{symbol}: {error_category} - {str(e)[:100]}")
        return (False, error_category)

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

def refresh_quarterly_revenue(symbol, conn):
    """Fetch and store quarterly revenue for TTM calculations"""
    try:
        ticker_obj = yf.Ticker(symbol)
        
        # Get quarterly financials
        q_financials = ticker_obj.quarterly_financials
        if q_financials is None or q_financials.empty:
            return False
        
        # Extract Total Revenue row
        if 'Total Revenue' not in q_financials.index:
            return False
        
        revenue_row = q_financials.loc['Total Revenue']
        c = conn.cursor()
        
        # Store each quarter's revenue (up to last 8 quarters)
        for date_col, revenue in revenue_row.items():
            if pd.notna(revenue) and revenue > 0:
                # Extract year and quarter from date
                dt = pd.Timestamp(date_col)
                year = dt.year
                quarter = (dt.month - 1) // 3 + 1
                
                # Upsert quarterly revenue
                c.execute('''
                    INSERT OR REPLACE INTO quarterly_revenue 
                    (symbol, year, quarter, revenue, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (symbol, year, quarter, float(revenue)))
        
        conn.commit()
        return True
    except Exception as e:
        return False


from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    start_time = datetime.now()
    logger.info(f"🚀 Cache Refresh Started: {start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"🚀 Cache Refresh Started: {start_time.strftime('%Y-%m-%d %H:%M')}")
    
    # Import DB
    try:
        from market_data import MarketDB
        import pandas as pd  # Needed for revenue refresh
        db = MarketDB()
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        print(f"❌ Failed to connect to DB: {e}")
        sys.exit(1)
    
    # Also get direct SQLite connection for revenue_history
    conn = sqlite3.connect(DB_PATH)
    
    tickers = load_tickers()
    total = len(tickers)
    logger.info(f"📊 Refreshing {total} tickers with ThreadPool (max {MAX_WORKERS} workers)...")
    print(f"📊 Refreshing {total} tickers with ThreadPool (max {MAX_WORKERS} workers)...")
    
    success = 0
    revenue_success = 0
    error_counts = defaultdict(int)  # Track error types
    
    # Filter out already updated tickers (today)
    already_updated = set()
    try:
        with sqlite3.connect(DB_PATH) as check_conn:
            cursor = check_conn.cursor()
            cursor.execute("SELECT symbol FROM tickers WHERE last_updated >= date('now', '-1 day')")
            already_updated = {row[0] for row in cursor.fetchall()}
    except Exception as e:
        logger.warning(f"Could not check existing updates: {e}")

    tickers_to_process = [t for t in tickers if t not in already_updated]
    skipped = total - len(tickers_to_process)
    logger.info(f"⏭️  Skipping {skipped} already updated tickers.")
    print(f"⏭️  Skipping {skipped} already updated tickers.")
    
    def process_ticker(ticker):
        # Small delay to reduce rate limiting
        time.sleep(DELAY_BETWEEN_TICKERS)
        
        # Create a new DB instance for this thread
        try:
            local_db = MarketDB()
            # Refresh prices and fundamentals
            result, error_category = refresh_ticker(ticker, local_db)
            
            # Refresh revenue data (every 5th ticker to reduce API load)
            rev_updated = False
            # Use deterministic hash for revenue refresh
            if result and hash(ticker) % 5 == 0:
                with sqlite3.connect(DB_PATH) as thread_conn:
                    rev_result = refresh_revenue_history(ticker, thread_conn)
                    if rev_result:
                        if hash(ticker) % 10 == 0:
                            refresh_quarterly_revenue(ticker, thread_conn)
                        rev_updated = True
            
            local_db.close()
            return (result, error_category, rev_updated)
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            return (False, 'PROCESS_ERROR', False)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(process_ticker, t): t for t in tickers_to_process}
        
        for i, future in enumerate(as_completed(future_to_ticker), 1):
            ticker = future_to_ticker[future]
            try:
                res, error_cat, rev = future.result()
                if res:
                    success += 1
                else:
                    error_counts[error_cat] += 1
                if rev:
                    revenue_success += 1
            except Exception as e:
                logger.error(f"❌ Error {ticker}: {e}")
                error_counts['EXCEPTION'] += 1
            
            # Progress update every 10
            if i % 10 == 0:
                failed = sum(error_counts.values())
                print(f"  [{i+skipped}/{total}] ✅ {success+skipped} | ❌ {failed} | 💰 {revenue_success}")

    db.close()
    conn.close()
    
    # Calculate final stats
    failed_total = sum(error_counts.values())
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60
    
    # Final Summary
    logger.info("\n" + "="*60)
    logger.info("CACHE REFRESH COMPLETE")
    logger.info("="*60)
    logger.info(f"✅ Price/Fundamental Success: {success+skipped}/{total} ({(success+skipped)/total*100:.1f}%)")
    logger.info(f"💰 Revenue History Updated:   {revenue_success}")
    logger.info(f"❌ Failed:                    {failed_total}/{total} ({failed_total/total*100:.1f}%)")
    logger.info(f"⏱️  Duration:                  {duration:.1f} minutes")
    
    if error_counts:
        logger.info("\n--- FAILURE BREAKDOWN ---")
        for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {error_type:>15}: {count:4d} ({count/failed_total*100:.1f}%)")
    
    print(f"\n✅ Cache Refresh Complete!")
    print(f"   Success: {success+skipped}/{total} | Failed: {failed_total}/{total}")
    print(f"   Duration: {duration:.1f} min | See logs/investiq_refresh.log for details")

if __name__ == "__main__":
    main()

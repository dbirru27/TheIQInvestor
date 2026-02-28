import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import time

DB_PATH = 'market_data.db'

def fix_ticker(symbol, conn):
    # Check if already has annual data
    c = conn.cursor()
    c.execute("SELECT symbol FROM revenue_history WHERE symbol = ? LIMIT 1", (symbol,))
    if c.fetchone():
        return "skipped"

    try:
        ticker_obj = yf.Ticker(symbol)
        
        # 1. Annual Revenue
        financials = ticker_obj.financials
        if financials is not None and not financials.empty and 'Total Revenue' in financials.index:
            revenue_row = financials.loc['Total Revenue']
            for date_col, revenue in revenue_row.items():
                if pd.notna(revenue) and revenue > 0:
                    fiscal_year = pd.Timestamp(date_col).year
                    
                    # Calculate growth
                    growth_yoy = None
                    prior_year = fiscal_year - 1
                    prior_rev = None
                    for d2, r2 in revenue_row.items():
                        if pd.Timestamp(d2).year == prior_year:
                            prior_rev = r2
                            break
                    
                    if prior_rev and prior_rev > 0:
                        growth_yoy = (revenue - prior_rev) / prior_rev
                    
                    c.execute('''
                        INSERT OR REPLACE INTO revenue_history 
                        (symbol, fiscal_year, total_revenue, revenue_growth_yoy, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (symbol, fiscal_year, float(revenue), growth_yoy))
        
        # 2. Quarterly Revenue
        q_financials = ticker_obj.quarterly_financials
        if q_financials is not None and not q_financials.empty and 'Total Revenue' in q_financials.index:
            revenue_row = q_financials.loc['Total Revenue']
            for date_col, revenue in revenue_row.items():
                if pd.notna(revenue) and revenue > 0:
                    dt = pd.Timestamp(date_col)
                    year = dt.year
                    quarter = (dt.month - 1) // 3 + 1
                    c.execute('''
                        INSERT OR REPLACE INTO quarterly_revenue 
                        (symbol, year, quarter, revenue, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (symbol, year, quarter, float(revenue)))
        
        # 3. Fundamentals (Always update info)
        info = ticker_obj.info
        if info:
            import json
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            json_str = json.dumps(info)
            c.execute('''
                INSERT INTO fundamentals (symbol, data, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET data = ?, updated_at = ?
            ''', (symbol, json_str, now_str, json_str, now_str))

        conn.commit()
        return "success"
    except Exception as e:
        return f"failed: {e}"

if __name__ == "__main__":
    if not os.path.exists('russell1000_tickers.txt'):
        print("Missing ticker list.")
        exit(1)
        
    tickers = [line.strip() for line in open('russell1000_tickers.txt') if line.strip()]
    conn = sqlite3.connect(DB_PATH)
    
    print(f"🚀 Starting Full Revenue Backfill for {len(tickers)} tickers...")
    
    success_count = 0
    skipped_count = 0
    fail_count = 0
    
    for i, t in enumerate(tickers, 1):
        res = fix_ticker(t, conn)
        if res == "success":
            success_count += 1
        elif res == "skipped":
            skipped_count += 1
        else:
            fail_count += 1
            print(f"  [{i}/{len(tickers)}] {t}: {res}")
            
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(tickers)} (✅ {success_count} | ⏭️ {skipped_count} | ❌ {fail_count})")
            # Small sleep to avoid aggressive Yahoo rate limits
            time.sleep(1)

    conn.close()
    print("\n✅ Backfill Complete.")
    print(f"Final: ✅ {success_count} | ⏭️ {skipped_count} | ❌ {fail_count}")

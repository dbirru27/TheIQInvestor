#!/usr/bin/env python3
"""
Web Scan - Uses BreakoutRater for consistent scoring
Generates top_stocks.json for website
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rater import BreakoutRater

DB_PATH = os.path.join(os.getcwd(), 'market_data.db')

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def main():
    print("🚀 Starting InvestIQ Web Scan...")
    print("Using BreakoutRater for consistent scoring")
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get all tickers with price data
    c.execute('SELECT DISTINCT symbol FROM prices')
    tickers = [row[0] for row in c.fetchall()]
    
    print(f"Found {len(tickers)} tickers in database")
    
    rater = BreakoutRater()
    results = []
    
    for i, ticker in enumerate(tickers, 1):
        try:
            result = rater.rate_stock(ticker)
            if result and 'error' not in result:
                results.append({
                    'ticker': ticker,
                    'name': result.get('name', ticker),
                    'sector': result.get('sector', 'Unknown'),
                    'score': result.get('score', 0),
                    'grade': result.get('grade', 'F'),
                    'total': result.get('total', 0)
                })
            
            if i % 50 == 0:
                print(f"  Processed {i}/{len(tickers)}...")
                
        except Exception as e:
            print(f"  Error on {ticker}: {e}")
            continue
    
    # Sort by total score
    results.sort(key=lambda x: x['total'], reverse=True)
    
    # Save top 50
    output = {
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'stocks': results[:50]
    }
    
    with open('top_stocks.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Saved {len(results[:50])} rated stocks to top_stocks.json")
    print(f"   Top 5: {', '.join([s['ticker'] + ' ' + s['grade'] for s in results[:5]])}")
    
    conn.close()

if __name__ == '__main__':
    main()

import json
import os
import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = os.path.join(os.getcwd(), 'market_data.db')

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def rate_stock_from_db(symbol, conn):
    """Rate a stock using only cached DB data (no API calls)"""
    try:
        # Get price history
        prices = pd.read_sql_query(
            f"SELECT * FROM prices WHERE symbol = '{symbol}' ORDER BY date",
            conn
        )
        if len(prices) < 130:
            return None
        
        # Get fundamentals
        fund_df = pd.read_sql_query(
            f"SELECT data FROM fundamentals WHERE symbol = '{symbol}'",
            conn
        )
        info = json.loads(fund_df.iloc[0]['data']) if not fund_df.empty else {}
        
        close = prices['close'].iloc[-1]
        sma50 = prices['close'].tail(50).mean()
        sma200 = prices['close'].tail(200).mean()
        
        # Simple scoring (matches rater logic)
        score = 0
        
        # Trend (5 pts)
        if close > sma50 and sma50 > sma200:
            score += 5
        
        # Breakout pattern (20 pts) - simplified
        window = prices.iloc[-130:-5]
        high_1 = window.iloc[:65]['high'].max()
        high_2 = window.iloc[65:]['high'].max()
        base_ceiling = max(high_1, high_2)
        dist = (base_ceiling - close) / base_ceiling
        drift = (high_2 - high_1) / high_1 if high_1 > 0 else 1
        if drift < 0.10 and dist < 0.05:
            score += 20
        
        # Consolidation (10 pts)
        depth = (window['high'].max() - window['low'].min()) / window['high'].max()
        if depth < 0.45:
            score += 10
        
        # Volume (5 pts)
        v5 = prices['volume'].tail(5).mean()
        v50 = prices['volume'].tail(50).mean()
        if v5 < v50 * 1.2:
            score += 5
        
        # Growth (10 pts)
        rev_g = info.get('revenueGrowth', 0)
        if rev_g and rev_g > 0.1:
            score += 10
        
        # Earnings (5 pts)
        earn_g = info.get('earningsGrowth', 0)
        if earn_g and earn_g > 0.15:
            score += 5
        
        # Quality (15 pts)
        margin = info.get('operatingMargins', 0)
        if margin and margin > 0.1:
            score += 10
        
        fcf = info.get('freeCashflow', 0)
        if fcf and fcf > 0:
            score += 5
        
        # Grade
        if score >= 85: grade = 'A+'
        elif score >= 80: grade = 'A'
        elif score >= 75: grade = 'A-'
        elif score >= 70: grade = 'B+'
        elif score >= 60: grade = 'B'
        elif score >= 50: grade = 'B-'
        elif score >= 40: grade = 'C+'
        elif score >= 30: grade = 'C'
        else: grade = 'C-'
        
        return {
            'ticker': symbol,
            'name': info.get('shortName', info.get('longName', symbol))[:35],
            'sector': info.get('sector', 'Unknown'),
            'score': score,
            'grade': grade
        }
    except Exception as e:
        return None

def run_universe_scan():
    print("🚀 Starting DB-Only Universe Scan...")
    
    conn = get_db_connection()
    
    # Load tickers from DB that have recent data
    tickers_df = pd.read_sql_query(
        "SELECT DISTINCT symbol FROM prices WHERE date >= '2026-02-05'",
        conn
    )
    tickers = tickers_df['symbol'].tolist()
    print(f"Targeting {len(tickers)} tickers from DB cache.")
    
    results = []
    count = 0
    for t in tickers:
        data = rate_stock_from_db(t, conn)
        if data:
            results.append({
                'ticker': data['ticker'],
                'name': data['name'],
                'sector': data['sector'],
                'total': data['score'],
                'grade': data['grade']
            })
            count += 1
            if count % 100 == 0:
                print(f"Processed {count}...")
    
    conn.close()
    
    # Sort by Score
    results.sort(key=lambda x: x['total'], reverse=True)
    
    # Save to top_stocks.json
    output = {
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'stocks': results[:50]
    }
    
    with open('top_stocks.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Updated top_stocks.json with {len(results)} results.")
    print(f"   Top 5: {', '.join([r['ticker'] + ' ' + r['grade'] for r in results[:5]])}")

if __name__ == "__main__":
    run_universe_scan()

#!/usr/bin/env python3
"""
InvestIQ Website Scan - v4.2 High Potential (100 Point Scale)
Updates top_stocks.json for website display
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rater import CriterionResult

DB_PATH = os.path.join(os.getcwd(), 'market_data.db')

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def rate_stock_v42(symbol, conn):
    """Rate stock using v4.2 100-point scale with DB data"""
    try:
        import pandas as pd
        
        prices = pd.read_sql_query(
            f"SELECT * FROM prices WHERE symbol = '{symbol}' ORDER BY date",
            conn
        )
        if len(prices) < 130:
            return None
        
        fund_df = pd.read_sql_query(
            f"SELECT data FROM fundamentals WHERE symbol = '{symbol}'",
            conn
        )
        info = json.loads(fund_df.iloc[0]['data']) if not fund_df.empty else {}
        
        hist = prices.set_index('date')
        hist.index = pd.to_datetime(hist.index)
        
        close = hist['close']
        current_price = close.iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1]
        
        results = []
        
        # 1. Trend Alignment (8 pts)
        price_above_50 = bool(current_price > sma50)
        if pd.notna(sma200):
            passed_trend = bool(price_above_50 and (sma50 > sma200))
        else:
            sma50_prev = close.rolling(50).mean().iloc[-5]
            passed_trend = bool(price_above_50 and sma50 > sma50_prev)
        results.append(CriterionResult("Trend Alignment", "Momentum", passed_trend, "", "", 8 if passed_trend else 0))
        
        # 2. Breakout Pattern (22 pts)
        window = hist.iloc[-130:-5]
        high_1 = window.iloc[:65]['high'].max()
        high_2 = window.iloc[65:]['high'].max()
        drift = (high_2 - high_1) / high_1
        base_ceiling = max(high_1, high_2)
        dist = (base_ceiling - current_price) / base_ceiling
        passed_bo = bool((drift < 0.10) and (dist < 0.05))
        results.append(CriterionResult("Breakout Pattern", "Breakout", passed_bo, "", "", 22 if passed_bo else 0))
        
        # 3. Consolidation (10 pts)
        depth = (window['high'].max() - window['low'].min()) / window['high'].max()
        passed_con = bool(depth < 0.45)
        results.append(CriterionResult("Consolidation", "Breakout", passed_con, "", "", 10 if passed_con else 0))
        
        # 4. Volume Dry-up (8 pts)
        v5 = hist['volume'].tail(5).mean()
        v50 = hist['volume'].tail(50).mean()
        passed_vol = bool(v5 < (v50 * 1.2))
        results.append(CriterionResult("Volume Dry-up", "Breakout", passed_vol, "", "", 8 if passed_vol else 0))
        
        # 5. 52W Proximity (5 pts)
        high_52w = hist['high'].max()
        proximity = current_price / high_52w
        passed_52w = bool(proximity > 0.90)
        results.append(CriterionResult("52W Proximity", "Timing", passed_52w, "", "", 5 if passed_52w else 0))
        
        # 6. Volatility Compression (5 pts)
        atr_current = (hist['high'].tail(14) - hist['low'].tail(14)).mean()
        atr_20d = (hist['high'].tail(20) - hist['low'].tail(20)).mean()
        passed_atr = bool(atr_current < 0.8 * atr_20d)
        results.append(CriterionResult("Volatility Compression", "Timing", passed_atr, "", "", 5 if passed_atr else 0))
        
        # 7. Sales Growth with 2-Year Consistency (0-30 pts)
        rev_g = info.get('revenueGrowth')
        
        # Fetch prior year growth from revenue_history
        rev_g_prior = None
        try:
            c = conn.cursor()
            c.execute('''
                SELECT revenue_growth_yoy FROM revenue_history 
                WHERE symbol = ? AND revenue_growth_yoy IS NOT NULL
                ORDER BY fiscal_year DESC LIMIT 1
            ''', (symbol,))
            row = c.fetchone()
            if row:
                rev_g_prior = row[0]
        except:
            pass
        
        # STRICT GATE: Both years must be >= 10%
        if rev_g is None or rev_g < 0.10:
            # Current year < 10% → DISQUALIFIED
            sales_points = 0
        elif rev_g_prior is None or rev_g_prior < 0.10:
            # Prior year < 10% → DISQUALIFIED
            sales_points = 0
        else:
            # Both years >= 10%: calculate score with bonus
            avg_growth = (rev_g + rev_g_prior) / 2
            consistency_bonus = 3  # Guaranteed since both >= 10%
            base_score = min(max(0, (avg_growth / 0.30) * 12), 27)
            sales_points = base_score + consistency_bonus
        
        results.append(CriterionResult("Sales Growth (2yr)", "Growth", sales_points > 0, "", "", int(sales_points)))
        
        # 8. Earnings Growth (3 pts)
        earn_g = info.get('earningsGrowth')
        passed_earn = bool(earn_g is not None and earn_g > 0.15)
        results.append(CriterionResult("Earnings Growth", "Growth", passed_earn, "", "", 3 if passed_earn else 0))
        
        # 9. ROE Quality (5 pts)
        roe = info.get('returnOnEquity')
        passed_roe = bool(roe is not None and roe > 0.15)
        results.append(CriterionResult("ROE Quality", "Quality", passed_roe, "", "", 5 if passed_roe else 0))
        
        # 10. Operating Margin (5 pts)
        margin = info.get('operatingMargins')
        passed_margin = bool(margin is not None and margin > 0.10)
        results.append(CriterionResult("Operating Margin", "Quality", passed_margin, "", "", 5 if passed_margin else 0))
        
        # 11. Valuation Sanity (5 pts) - PEG < 2.0
        peg = info.get('pegRatio')
        passed_peg = bool(peg is not None and peg < 2.0 and peg > 0)
        results.append(CriterionResult("Valuation Sanity", "Quality", passed_peg, "", "", 5 if passed_peg else 0))
        
        # 12. FCF Quality (3 pts)
        fcf = info.get('freeCashflow')
        passed_fcf = bool(fcf is not None and fcf > 0)
        results.append(CriterionResult("FCF Quality", "Quality", passed_fcf, "", "", 3 if passed_fcf else 0))
        
        # 13. Industry Strength (5 pts)
        sector = info.get('sector', '')
        strong_sectors = ['Technology', 'Healthcare', 'Communication Services', 'Industrials']
        passed_ind = sector in strong_sectors
        results.append(CriterionResult("Industry Strength", "Context", passed_ind, "", "", 5 if passed_ind else 0))
        
        # 14. Relative Strength (5 pts)
        price_1m = close.iloc[-22] if len(close) >= 22 else close.iloc[0]
        ret_1m = (current_price - price_1m) / price_1m
        passed_rs = bool(ret_1m > 0.05)
        results.append(CriterionResult("Relative Strength", "Context", passed_rs, "", "", 5 if passed_rs else 0))
        
        # 15. Size Penalty
        market_cap = info.get('marketCap', 0)
        size_penalty = 0
        if market_cap > 1_000_000_000_000:
            size_penalty = -10
        elif market_cap > 500_000_000_000:
            size_penalty = -5
        
        if size_penalty < 0:
            results.append(CriterionResult("Size Factor", "Context", False, "", "", size_penalty))
        
        # Calculate total (0-100)
        total = sum(r.points for r in results)
        
        # Tighter grading: A=70+, B=55-69, C=40-54, D=25-39, F=<25
        if total >= 70: grade = 'A'
        elif total >= 55: grade = 'B'
        elif total >= 40: grade = 'C'
        elif total >= 25: grade = 'D'
        else: grade = 'F'
        
        return {
            'ticker': symbol,
            'name': info.get('shortName', symbol)[:40],
            'sector': sector or 'Unknown',
            'industry': info.get('industry', 'Unknown')[:30],
            'score': total,
            'max_score': 100,
            'grade': grade,
            'market_cap': market_cap,
            'technical_score': sum(r.points for r in results if r.category in ["Momentum", "Breakout", "Timing"]),
            'growth_score': sum(r.points for r in results if r.category == "Growth"),
            'quality_score': sum(r.points for r in results if r.category == "Quality"),
        }
        
    except Exception as e:
        return None

def run_scan():
    print("🚀 Starting InvestIQ v4.2 Scan (100 Point Scale)...")
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT DISTINCT symbol FROM prices')
    tickers = [row[0] for row in c.fetchall()]
    
    print(f"Found {len(tickers)} tickers in database")
    
    results = []
    for i, ticker in enumerate(tickers, 1):
        data = rate_stock_v42(ticker, conn)
        if data:
            results.append(data)
        
        if i % 100 == 0:
            print(f"  Processed {i}/{len(tickers)}...")
    
    conn.close()
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    output = {
        'version': '4.2',
        'max_score': 100,
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'stocks': results[:50]
    }
    
    with open('top_stocks.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Saved {len(results[:50])} stocks to top_stocks.json")
    print(f"   Top 5: {', '.join([s['ticker'] + ' ' + str(s['score']) for s in results[:5]])}")

if __name__ == '__main__':
    run_scan()

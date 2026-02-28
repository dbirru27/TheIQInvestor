#!/usr/bin/env python3
"""
InvestIQ Website Scan - v5.0 Enhanced Algorithm (100 Point Scale)
Updates top_stocks.json and all_stocks.json for website display
"""
import json
import os
import sqlite3
import sys
from datetime import datetime
import config
from utils.logger import get_logger
import yfinance as yf
import pandas as pd

logger = get_logger('web_scan')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rater import CriterionResult, get_ttm_growth
from rotation_catcher import RotationCatcher

DB_PATH = config.DB_PATH

# v5.0 Global Caches
_spy_cache = None
_sector_etf_cache = {}

def get_spy_data():
    """Fetch SPY data once per session and cache it"""
    global _spy_cache
    if _spy_cache is None:
        try:
            spy = yf.Ticker("SPY")
            _spy_cache = spy.history(period="1y")
        except:
            _spy_cache = pd.DataFrame()  # Empty fallback
    return _spy_cache

def get_sector_etf_data(sector_etf):
    """Fetch sector ETF data once per ETF per session and cache it"""
    global _sector_etf_cache
    if sector_etf not in _sector_etf_cache:
        try:
            etf = yf.Ticker(sector_etf)
            _sector_etf_cache[sector_etf] = etf.history(period="6mo")
        except:
            _sector_etf_cache[sector_etf] = pd.DataFrame()  # Empty fallback
    return _sector_etf_cache[sector_etf]

# Sector to ETF mapping
SECTOR_ETFS = {
    'Technology': 'XLK',
    'Consumer Cyclical': 'XLY',
    'Energy': 'XLE',
    'Basic Materials': 'XLB',
    'Industrials': 'XLI',
    'Healthcare': 'XLV',
    'Financial Services': 'XLF',
    'Consumer Defensive': 'XLP',
    'Utilities': 'XLU',
    'Real Estate': 'XLRE',
    'Communication Services': 'XLC'
}

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def rate_stock_v43_full(symbol, conn):
    """Rate stock with full details including criteria breakdown"""
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
            trend_val = f"${current_price:.2f} > 50d(${sma50:.2f}) > 200d(${sma200:.2f})"
        else:
            sma50_prev = close.rolling(50).mean().iloc[-5]
            passed_trend = bool(price_above_50 and sma50 > sma50_prev)
            trend_val = f"${current_price:.2f} > 50d(${sma50:.2f})"
        results.append(CriterionResult("Trend Alignment", "Momentum", passed_trend, trend_val, "Price > 50d > 200d", 8 if passed_trend else 0))
        
        # 2. Breakout Pattern (22 pts)
        window = hist.iloc[-130:-5]
        high_1 = window.iloc[:65]['high'].max()
        high_2 = window.iloc[65:]['high'].max()
        drift = (high_2 - high_1) / high_1
        base_ceiling = max(high_1, high_2)
        dist = (base_ceiling - current_price) / base_ceiling
        passed_bo = bool((drift < 0.10) and (dist < 0.05))
        bo_val = f"{(dist*100):.1f}% from base, drift: {(drift*100):.1f}%"
        results.append(CriterionResult("Breakout Pattern", "Breakout", passed_bo, bo_val, "< 5% from ceiling, < 10% drift", 22 if passed_bo else 0))
        
        # 3. Consolidation (10 pts)
        base_high = window['high'].max()
        base_low = window['low'].min()
        depth = (base_high - base_low) / base_high
        passed_con = bool(depth < 0.45)
        con_val = f"{(depth*100):.1f}% depth (${base_low:.2f} - ${base_high:.2f})"
        results.append(CriterionResult("Consolidation", "Breakout", passed_con, con_val, "Base depth < 45%", 10 if passed_con else 0))
        
        # 4. Volume Dry-up (8 pts)
        v5 = hist['volume'].tail(5).mean()
        v50 = hist['volume'].tail(50).mean()
        vol_ratio = v5 / v50 if v50 > 0 else 1
        passed_vol = bool(vol_ratio < 1.2)
        vol_val = f"{(vol_ratio*100):.0f}% of avg ({v5/1e6:.1f}M vs {v50/1e6:.1f}M)"
        results.append(CriterionResult("Volume Dry-up", "Breakout", passed_vol, vol_val, "5d vol < 1.2x 50d vol", 8 if passed_vol else 0))
        
        # 5. 52W Proximity (5 pts)
        high_52w = hist['high'].max()
        low_52w = hist['low'].min()
        proximity = current_price / high_52w
        passed_52w = bool(proximity > 0.90)
        proximity_val = f"{(proximity*100):.1f}% of 52W high (${high_52w:.2f})"
        results.append(CriterionResult("52W Proximity", "Timing", passed_52w, proximity_val, "> 90% of 52W high", 5 if passed_52w else 0))
        
        # 6. Volatility Compression (5 pts) - FIXED v5.0: 10d vs 50d
        atr_10d = (hist['high'].tail(10) - hist['low'].tail(10)).mean()
        atr_50d = (hist['high'].tail(50) - hist['low'].tail(50)).mean()
        atr_ratio = atr_10d / atr_50d if atr_50d > 0 else 1
        passed_atr = bool(atr_ratio < 0.75)  # 25% compression = squeeze
        atr_val = f"{(atr_ratio*100):.1f}% of 50d ATR (${atr_10d:.2f} vs ${atr_50d:.2f})"
        results.append(CriterionResult("Volatility Compression", "Timing", passed_atr, atr_val, "10d ATR < 75% of 50d ATR", 5 if passed_atr else 0))
        
        # 7. Sales Growth with Graduated Scoring (0-30 pts) - ENHANCED v5.0
        rev_g_fallback = info.get('revenueGrowth')
        rev_g, rev_g_prior = get_ttm_growth(symbol, conn)
        
        if rev_g is None:
            rev_g = rev_g_fallback
        
        if rev_g_prior is None:
            try:
                c = conn.cursor()
                c.execute('''
                    SELECT revenue_growth_yoy FROM revenue_history 
                    WHERE symbol = ? AND revenue_growth_yoy IS NOT NULL
                    ORDER BY fiscal_year DESC LIMIT 1 OFFSET 1
                ''', (symbol,))
                row = c.fetchone()
                if row:
                    rev_g_prior = row[0]
            except:
                pass
        
        # GRADUATED SCORING (v5.0): Softer gate, rewards tiers
        if rev_g is None:
            sales_points = 0
            growth_display = "N/A"
        else:
            # Current year points (0-15)
            if rev_g >= 0.20:
                current_pts = 15
            elif rev_g >= 0.10:
                current_pts = 12
            elif rev_g >= 0.05:
                current_pts = 6
            else:
                current_pts = 0
            
            # Prior year points (0-12)
            if rev_g_prior is not None:
                if rev_g_prior >= 0.20:
                    prior_pts = 12
                elif rev_g_prior >= 0.10:
                    prior_pts = 9
                elif rev_g_prior >= 0.05:
                    prior_pts = 4
                else:
                    prior_pts = 0
            else:
                prior_pts = 0
            
            # Consistency bonus: both years >= 10% = +3
            consistency_bonus = 3 if (rev_g >= 0.10 and rev_g_prior is not None and rev_g_prior >= 0.10) else 0
            
            sales_points = current_pts + prior_pts + consistency_bonus  # max 30
            
            if rev_g_prior is not None:
                growth_display = f"Cur: {float(rev_g)*100:.1f}%, Prior: {float(rev_g_prior)*100:.1f}%"
            else:
                growth_display = f"Current: {float(rev_g)*100:.1f}%"
        
        results.append(CriterionResult("Sales Growth (2yr)", "Growth", sales_points > 0, growth_display, "Graduated: 20%/10%/5% tiers", int(sales_points)))
        
        # 8. Earnings Acceleration (8 pts) - NEW v5.0
        # Fetch quarterly EPS and check if growth is ACCELERATING
        earnings_accel_pts = 0
        earnings_accel_val = "N/A"
        try:
            # Fetch from yfinance since we need quarterly income statement
            import yfinance as yf
            stock = yf.Ticker(symbol)
            quarterly_income = stock.quarterly_income_stmt
            
            if quarterly_income is not None and not quarterly_income.empty and 'Net Income' in quarterly_income.index:
                # Get Net Income values (most recent quarters first in columns)
                net_income = quarterly_income.loc['Net Income'].dropna()
                if len(net_income) >= 3:
                    # Reverse to chronological order (oldest first)
                    net_income_values = net_income.values[::-1]
                    
                    # Calculate growth rates between consecutive quarters
                    growth_rates = []
                    for i in range(1, min(len(net_income_values), 4)):
                        if net_income_values[i-1] != 0:
                            gr = (net_income_values[i] - net_income_values[i-1]) / abs(net_income_values[i-1])
                            growth_rates.append(gr)
                    
                    if len(growth_rates) >= 2:
                        # Check if growth rates are increasing (acceleration)
                        accelerating = all(growth_rates[i] > growth_rates[i-1] for i in range(1, len(growth_rates)))
                        positive = all(gr > 0 for gr in growth_rates)
                        
                        if accelerating and positive:
                            earnings_accel_pts = 8
                            earnings_accel_val = "Accelerating"
                        elif positive:
                            earnings_accel_pts = 4
                            earnings_accel_val = "Positive, flat"
                        else:
                            earnings_accel_pts = 0
                            earnings_accel_val = "Decelerating/Negative"
                    else:
                        earnings_accel_val = "Insufficient quarters"
        except Exception as e:
            earnings_accel_val = "Data unavailable"
        
        results.append(CriterionResult("Earnings Acceleration", "Growth", earnings_accel_pts > 0, earnings_accel_val, "QoQ growth accelerating", earnings_accel_pts))
        
        # 9. ROE Quality (5 pts)
        roe = info.get('returnOnEquity')
        passed_roe = bool(roe is not None and roe > 0.15)
        roe_val = f"{float(roe)*100:.1f}%" if roe else "N/A"
        results.append(CriterionResult("ROE Quality", "Quality", passed_roe, roe_val, "> 15%", 5 if passed_roe else 0))
        
        # 10. Operating Margin (5 pts)
        margin = info.get('operatingMargins')
        passed_margin = bool(margin is not None and margin > 0.10)
        margin_val = f"{float(margin)*100:.1f}%" if margin else "N/A"
        results.append(CriterionResult("Operating Margin", "Quality", passed_margin, margin_val, "> 10%", 5 if passed_margin else 0))
        
        # 11. Valuation Sanity (5 pts)
        peg = info.get('pegRatio')
        passed_peg = bool(peg is not None and peg < 2.0 and peg > 0)
        peg_val = f"{float(peg):.2f}" if peg else "N/A"
        results.append(CriterionResult("Valuation Sanity", "Quality", passed_peg, peg_val, "PEG < 2.0", 5 if passed_peg else 0))
        
        # 12. FCF Quality (3 pts)
        fcf = info.get('freeCashflow')
        passed_fcf = bool(fcf is not None and fcf > 0)
        fcf_val = f"${float(fcf)/1e9:.2f}B" if fcf else "N/A"
        results.append(CriterionResult("FCF Quality", "Quality", passed_fcf, fcf_val, "FCF > 0", 3 if passed_fcf else 0))
        
        # 13. Industry Strength (5 pts) - DYNAMIC v5.0
        sector = info.get('sector', '')
        sector_etf = SECTOR_ETFS.get(sector)
        passed_ind = False
        ind_val = sector or "Unknown"
        
        if sector_etf:
            try:
                spy_hist = get_spy_data()
                etf_hist = get_sector_etf_data(sector_etf)
                
                if not spy_hist.empty and not etf_hist.empty and len(spy_hist) >= 63 and len(etf_hist) >= 63:
                    spy_close = spy_hist['Close']
                    etf_close = etf_hist['Close']
                    
                    # 3-month returns
                    etf_3m_return = (etf_close.iloc[-1] - etf_close.iloc[-63]) / etf_close.iloc[-63]
                    spy_3m_return = (spy_close.iloc[-1] - spy_close.iloc[-63]) / spy_close.iloc[-63]
                    
                    sector_outperformance = etf_3m_return - spy_3m_return
                    passed_ind = sector_outperformance > 0
                    
                    ind_val = f"{sector} ({sector_etf}: {float(sector_outperformance)*100:+.1f}% vs SPY)"
            except:
                ind_val = f"{sector} (no data)"
        
        results.append(CriterionResult("Industry Strength", "Context", passed_ind, ind_val, "Sector outperforming SPY (3mo)", 5 if passed_ind else 0))
        
        # 14. Relative Strength (5 pts) - REAL RS v5.0
        rs_points = 0
        rs_val = "N/A"
        
        try:
            spy_hist = get_spy_data()
            
            if not spy_hist.empty and len(close) >= 130 and len(spy_hist) >= 130:
                # 6-month returns (130 trading days ≈ 6 months)
                price_6m_ago = close.iloc[-130]
                stock_6m_return = (current_price - price_6m_ago) / price_6m_ago
                
                spy_close = spy_hist['Close']
                spy_6m_return = (spy_close.iloc[-1] - spy_close.iloc[-130]) / spy_close.iloc[-130]
                
                # RS = relative outperformance
                relative_strength = stock_6m_return - spy_6m_return
                
                # Score: outperforming SPY by >10% = 5pts, >5% = 3pts, >0% = 1pt
                if relative_strength > 0.10:
                    rs_points = 5
                elif relative_strength > 0.05:
                    rs_points = 3
                elif relative_strength > 0:
                    rs_points = 1
                else:
                    rs_points = 0
                
                rs_val = f"{float(relative_strength)*100:+.1f}% vs SPY (6mo)"
            else:
                rs_val = "Insufficient data"
        except:
            rs_val = "Error calculating RS"
        
        passed_rs = rs_points > 0
        results.append(CriterionResult("Relative Strength", "Context", passed_rs, rs_val, ">0% outperformance vs SPY", rs_points))
        
        # 15. Size Penalty
        market_cap = info.get('marketCap', 0)
        size_penalty = 0
        size_val = ""
        if market_cap > 1_000_000_000_000:
            size_penalty = -10
            size_val = f"${market_cap/1e12:.1f}T"
        elif market_cap > 500_000_000_000:
            size_penalty = -5
            size_val = f"${market_cap/1e9:.0f}B"
        
        if size_penalty < 0:
            results.append(CriterionResult("Size Factor", "Context", False, size_val, "Large Cap Penalty", size_penalty))
        
        # --- MOONSHOT SCORE CALCULATION (0-100) ---
        ms_pts = 0
        
        # 1. Acceleration (40 pts)
        if rev_g and rev_g_prior and rev_g_prior > 0:
            accel = rev_g / rev_g_prior
            if accel > 1.5: ms_pts += 40
            elif accel > 1.2: ms_pts += 30
            elif accel > 1.0: ms_pts += 20
            
        # 2. Valuation Efficiency (30 pts)
        # P/S ratio / Growth
        revenue_ttm = info.get('totalRevenue')
        if market_cap and revenue_ttm and revenue_ttm > 0 and rev_g and rev_g > 0:
            ps_ratio = market_cap / revenue_ttm
            efficiency = ps_ratio / (rev_g * 100)
            if efficiency < 0.1: ms_pts += 30
            elif efficiency < 0.2: ms_pts += 20
            elif efficiency < 0.3: ms_pts += 10
            
        # 3. Relative Strength (30 pts)
        # We use the Ret_1m already calculated for RS
        if passed_rs:
            ms_pts += 30 # Simple proxy: if passed 5% outperformance gate
            
        # Calculate total (capped at 100)
        total = min(100, sum(r.points for r in results))
        
        # Grading
        if total >= 70: grade = 'A'
        elif total >= 55: grade = 'B'
        elif total >= 40: grade = 'C'
        elif total >= 25: grade = 'D'
        else: grade = 'F'
        
        # Build criteria list for detail view
        criteria_list = []
        for r in results:
            criteria_list.append({
                'name': r.name,
                'category': r.category,
                'passed': r.passed,
                'points': r.points,
                'value': r.value,
                'threshold': r.threshold
            })
        
        # Get valuation and analyst data from info
        forward_pe = info.get('forwardPE')
        trailing_pe = info.get('trailingPE')
        peg = info.get('pegRatio')
        recommendation = info.get('recommendationKey', 'N/A')
        target_mean = info.get('targetMeanPrice')
        analyst_count = info.get('numberOfAnalystOpinions', 0)
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        
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
            'context_score': sum(r.points for r in results if r.category == "Context"),
            'moonshot_score': ms_pts, # New Moonshot Metric
            'criteria': criteria_list,  # Full breakdown for detail view
            # Valuation data
            'forward_pe': forward_pe,
            'trailing_pe': trailing_pe,
            'peg_ratio': peg,
            # Analyst data
            'recommendation': recommendation,
            'target_mean': target_mean,
            'analyst_count': analyst_count,
            'current_price': current_price
        }
        
    except Exception as e:
        return None

def run_scan():
    logger.info("🚀 Starting InvestIQ v5.0 Full Scan (All Stocks + Details + Rotation)...")
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT DISTINCT symbol FROM prices')
    tickers = [row[0] for row in c.fetchall()]
    
    logger.info(f"Found {len(tickers)} tickers")
    
    # Create one RotationCatcher instance (shares caches across all stocks)
    rc = RotationCatcher()
    logger.info("Initialized RotationCatcher with session-level caching")
    
    results = []
    for i, ticker in enumerate(tickers, 1):
        data = rate_stock_v43_full(ticker, conn)
        if data:
            # Add rotation score
            try:
                rotation_result = rc.score(ticker)
                data['rotation_score'] = rotation_result['composite_score']
                data['rotation_signal'] = rotation_result['signal']
                data['rotation_convergence'] = rotation_result['convergence_bonus']
            except Exception as e:
                logger.warning(f"Rotation scoring failed for {ticker}: {e}")
                data['rotation_score'] = 0
                data['rotation_signal'] = 'NO DATA'
                data['rotation_convergence'] = 0
            
            results.append(data)
        
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(tickers)}...")
    
    conn.close()
    
    # FILTER: Only include stocks that passed BOTH years >= 10% revenue growth
    # Filter: both years >= 10% revenue growth (growth_score >= 24) AND overall score >= 55
    filtered_results = [r for r in results if r.get('growth_score', 0) >= 24 and r['score'] >= 55]
    
    results.sort(key=lambda x: x['score'], reverse=True)
    filtered_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Save filtered top stocks for main display
    top_output = {
        'version': '5.0',
        'max_score': 100,
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'total_stocks': len(filtered_results),
        'stocks': filtered_results[:100]
    }
    
    import numpy as np
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)
    
    with open('top_stocks.json', 'w') as f:
        json.dump(top_output, f, indent=2, cls=NumpyEncoder)
    
    # Save ALL stocks — keep criteria for top stocks, strip for rest to save memory
    import gc
    top_tickers = set(s['ticker'] for s in filtered_results)
    all_stocks_slim = {}
    for s in results:
        if s['ticker'] in top_tickers:
            all_stocks_slim[s['ticker']] = s  # Keep criteria for detail view
        else:
            slim = {k: v for k, v in s.items() if k != 'criteria'}
            all_stocks_slim[s['ticker']] = slim
    
    all_output = {
        'version': '5.0',
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'total_stocks': len(results),
        'stocks': all_stocks_slim
    }
    
    total_count = len(results)
    del results  # Free memory before serialization
    gc.collect()
    
    with open('all_stocks.json', 'w') as f:
        json.dump(all_output, f, indent=2, cls=NumpyEncoder)
    
    logger.info(f"✅ Saved {len(filtered_results)} top stocks (both years >= 10% growth)")
    logger.info(f"   Saved {total_count} total stocks with details to all_stocks.json")
    logger.info(f"   Filtered out: {total_count - len(filtered_results)} stocks failed revenue gate")
    print(f"✅ Scan complete: {len(filtered_results)} top stocks, {len(results)} total")
    print(f"   Top 5: {', '.join([s['ticker'] + ' ' + str(s['score']) for s in filtered_results[:5]])}")

if __name__ == '__main__':
    run_scan()

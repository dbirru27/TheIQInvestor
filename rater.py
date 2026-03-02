import yfinance as yf
import pandas as pd
import numpy as np
import os
import math
import json
import traceback
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

# Optional: DB-backed incremental updates
try:
    from market_data import MarketDB
    db = MarketDB()
except:
    db = None

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

@dataclass
class CriterionResult:
    name: str
    category: str
    passed: bool
    value: str
    threshold: str
    points: int = 0

def get_ttm_growth(symbol, db_conn):
    """Calculate TTM growth from quarterly data"""
    try:
        c = db_conn.cursor()
        c.execute('''
            SELECT year, quarter, revenue FROM quarterly_revenue
            WHERE symbol = ? AND revenue IS NOT NULL
            ORDER BY year DESC, quarter DESC
            LIMIT 12
        ''', (symbol,))
        rows = c.fetchall()

        if len(rows) < 8:
            return None, None

        ttm_current = sum(r[2] for r in rows[0:4])
        ttm_prior = sum(r[2] for r in rows[4:8])

        rev_g = None
        rev_g_prior = None

        if ttm_prior > 0:
            rev_g = (ttm_current - ttm_prior) / ttm_prior

        if len(rows) >= 12:
            ttm_2yr = sum(r[2] for r in rows[8:12])
            if ttm_2yr > 0:
                rev_g_prior = (ttm_prior - ttm_2yr) / ttm_2yr

        return rev_g, rev_g_prior
    except:
        return None, None

def _sigmoid_normalize(value, center=0.10, scale=5.0):
    """Sigmoid normalization: returns 0-1, centered at 'center'"""
    return 1.0 / (1.0 + math.exp(-scale * (value - center)))


class BreakoutRater:
    def __init__(self):
        # v5.0 Enhanced Algorithm - 100 Point Scale
        self.weights = {
            "Breakout Pattern": 22,
            "Consolidation": 10,
            "Volume Dry-up": 8,
            "Trend Alignment": 8,
            "Revenue Score": 30,
            "Earnings Acceleration": 8,
            "ROE Quality": 5,
            "Operating Margin": 5,
            "Valuation Sanity": 5,
            "FCF Quality": 3,
            "52W Proximity": 5,
            "Volatility Compression": 5,
            "Industry Strength": 5,
            "Relative Strength": 5,
            "Size Factor": 0
        }
        
        self.SECTOR_ETFS = {
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

    def _score_from_data(self, ticker, hist, info, db_conn=None, stock_yf=None):
        """
        Core scoring engine. Takes pre-loaded data and returns scored result.
        
        Args:
            ticker: Stock ticker symbol
            hist: DataFrame with columns Close/close, High/high, Low/low, Open/open, Volume/volume
            info: Dict of fundamental data (from yfinance .info or DB fundamentals JSON)
            db_conn: Optional sqlite3 connection for quarterly_revenue table
            stock_yf: Optional yfinance Ticker object (for earnings_history, quarterly_income_stmt)
        
        Returns:
            Dict with full scoring result, or dict with 'error' key
        """
        if hist is None or hist.empty or len(hist) < 130:
            return {"error": "Insufficient history (130 days required)"}

        # Normalize column names (DB uses lowercase, yfinance uses Title case)
        col_map = {}
        for col in hist.columns:
            cl = col.lower()
            if cl == 'close': col_map[col] = 'Close'
            elif cl == 'high': col_map[col] = 'High'
            elif cl == 'low': col_map[col] = 'Low'
            elif cl == 'open': col_map[col] = 'Open'
            elif cl == 'volume': col_map[col] = 'Volume'
        if col_map:
            hist = hist.rename(columns=col_map)

        results = []
        
        close = hist['Close']
        sma50 = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1]
        current_price = close.iloc[-1]
        price_above_50 = bool(current_price > sma50)
        
        # 1. Trend Alignment (8 pts)
        if pd.notna(sma200):
            passed_trend = bool(price_above_50 and (sma50 > sma200))
            trend_desc = f"${float(current_price):.2f} > ${float(sma50):.2f} > ${float(sma200):.2f}"
        else:
            sma50_prev = close.rolling(50).mean().iloc[-5]
            passed_trend = bool(price_above_50 and sma50 > sma50_prev)
            trend_desc = f"${float(current_price):.2f} > ${float(sma50):.2f} (rising)"
        results.append(CriterionResult("Trend Alignment", "Momentum", passed_trend, trend_desc, "Price > SMA50 > SMA200", 8 if passed_trend else 0))

        # 2. Breakout Pattern (22 pts)
        window = hist.iloc[-130:-5]
        high_1 = window.iloc[:65]['High'].max()
        high_2 = window.iloc[65:]['High'].max()
        drift = (high_2 - high_1) / high_1
        base_ceiling = max(high_1, high_2)
        dist = (base_ceiling - close.iloc[-1]) / base_ceiling
        passed_bo = bool((drift < 0.10) and (dist < 0.05))
        results.append(CriterionResult("Breakout Pattern", "Breakout", passed_bo, f"{float(dist)*100:+.1f}% from Base", "Flat Base + Near High", 22 if passed_bo else 0))

        # 3. Consolidation (10 pts)
        depth = (window['High'].max() - window['Low'].min()) / window['High'].max()
        passed_con = bool(depth < 0.45)
        results.append(CriterionResult("Consolidation", "Breakout", passed_con, f"Depth {float(depth)*100:.0f}%", "Depth < 40%", 10 if passed_con else 0))

        # 4. Volume Dry-up (8 pts)
        v5, v50 = hist['Volume'].tail(5).mean(), hist['Volume'].tail(50).mean()
        passed_vol = bool(v5 < (v50 * 1.2))
        results.append(CriterionResult("Volume Dry-up", "Breakout", passed_vol, f"{float(v5/v50):.1f}x avg", "Vol < 1.2x Avg", 8 if passed_vol else 0))

        # 5. 52-Week Proximity (5 pts)
        high_52w = hist['High'].max()
        proximity = current_price / high_52w
        passed_52w = bool(proximity > 0.90)
        results.append(CriterionResult("52W Proximity", "Timing", passed_52w, f"{float(proximity)*100:.1f}%", "> 90% of 52W High", 5 if passed_52w else 0))
        
        # 6. Volatility Compression (5 pts)
        atr_10d = (hist['High'].tail(10) - hist['Low'].tail(10)).mean()
        atr_50d = (hist['High'].tail(50) - hist['Low'].tail(50)).mean()
        passed_atr = bool(atr_10d < 0.75 * atr_50d)
        atr_val = f"{float(atr_10d/atr_50d)*100:.0f}% of 50d ATR" if atr_50d > 0 else "N/A"
        results.append(CriterionResult("Volatility Compression", "Timing", passed_atr, atr_val, "10d ATR < 75% of 50d ATR", 5 if passed_atr else 0))

        # 7. Revenue Score (0-30 pts) - v5.1: 4-component continuous scoring
        revenue_pts = 0
        growth_display = "N/A"
        rev_components = {}
        q_yoy_growths = []
        yoy_growth = None
        
        try:
            quarterly_rev = []
            
            # Source 1: DB quarterly_revenue table
            if db_conn:
                try:
                    c = db_conn.cursor()
                    c.execute('''
                        SELECT year, quarter, revenue FROM quarterly_revenue
                        WHERE symbol = ? AND revenue IS NOT NULL
                        ORDER BY year ASC, quarter ASC
                    ''', (ticker,))
                    quarterly_rev = [{'date': None, 'revenue': float(row[2])} for row in c.fetchall()]
                except:
                    pass
            
            # Source 2: yfinance quarterly income statement
            if not quarterly_rev and stock_yf:
                try:
                    quarterly_income = stock_yf.quarterly_income_stmt
                    if quarterly_income is not None and not quarterly_income.empty and 'Total Revenue' in quarterly_income.index:
                        rev_series = quarterly_income.loc['Total Revenue'].dropna()
                        for dt, val in reversed(list(rev_series.items())):
                            quarterly_rev.append({'date': dt, 'revenue': float(val)})
                except:
                    pass
                
                if not quarterly_rev:
                    try:
                        qf = stock_yf.quarterly_financials
                        if qf is not None and not qf.empty and 'Total Revenue' in qf.index:
                            rev_series = qf.loc['Total Revenue'].dropna()
                            for dt, val in reversed(list(rev_series.items())):
                                quarterly_rev.append({'date': dt, 'revenue': float(val)})
                    except:
                        pass
            
            # Source 3: DB via MarketDB (fallback for live mode)
            if db and stock_yf and len(quarterly_rev) > 0:
                try:
                    c2 = db.conn.cursor()
                    c2.execute('''
                        SELECT year, quarter, revenue FROM quarterly_revenue
                        WHERE symbol = ? AND revenue IS NOT NULL
                        ORDER BY year ASC, quarter ASC
                    ''', (ticker,))
                    db_rows = c2.fetchall()
                    if len(db_rows) > len(quarterly_rev):
                        quarterly_rev = [{'date': None, 'revenue': float(row[2])} for row in db_rows]
                except:
                    pass
            
            revenues = [q['revenue'] for q in quarterly_rev]
            n = len(revenues)
            
            # Component 1: Magnitude (10.5 pts max)
            magnitude = 0
            if n >= 8:
                ttm_current = sum(revenues[n-4:n])
                ttm_prior = sum(revenues[n-8:n-4])
                if ttm_prior > 0:
                    yoy_growth = ttm_current / ttm_prior - 1.0
            elif n >= 5:
                if revenues[0] > 0:
                    yoy_growth = revenues[-1] / revenues[0] - 1.0
            
            # Fallback: DB TTM or info
            if yoy_growth is None and db_conn:
                rev_g, _ = get_ttm_growth(ticker, db_conn)
                if rev_g is not None:
                    yoy_growth = float(rev_g)
            
            if yoy_growth is None:
                # Try annual income statement (yfinance)
                if stock_yf:
                    try:
                        ann_inc = stock_yf.income_stmt
                        if ann_inc is not None and 'Total Revenue' in ann_inc.index:
                            ann_rev = ann_inc.loc['Total Revenue'].dropna()
                            if len(ann_rev) >= 2:
                                yoy_growth = float(ann_rev.iloc[0]) / float(ann_rev.iloc[1]) - 1.0
                    except:
                        pass
            
            if yoy_growth is None:
                rev_g = info.get('revenueGrowth')
                if rev_g is not None:
                    yoy_growth = float(rev_g)
            
            if yoy_growth is not None:
                magnitude = _sigmoid_normalize(yoy_growth, center=0.10, scale=5.0) * 10.5
                rev_components['yoy_growth'] = round(yoy_growth * 100, 1)
            
            # Component 2: Consistency (7.5 pts max)
            consistency = 0
            if n >= 5:
                for i in range(4, n):
                    if revenues[i-4] > 0:
                        g = revenues[i] / revenues[i-4] - 1.0
                        q_yoy_growths.append(g)
            
            if len(q_yoy_growths) >= 2:
                mean_g = np.mean(q_yoy_growths)
                std_g = np.std(q_yoy_growths)
                cv = std_g / abs(mean_g) if abs(mean_g) > 0.001 else 1.0
                consistency = max(0, (1.0 - min(cv, 2.0))) * 7.5
                rev_components['consistency_cv'] = round(cv, 2)
                rev_components['q_yoy_count'] = len(q_yoy_growths)
            
            # Component 3: Acceleration (7.5 pts max)
            accel = 0
            if len(q_yoy_growths) >= 2:
                mid = len(q_yoy_growths) // 2
                recent_avg = np.mean(q_yoy_growths[mid:])
                older_avg = np.mean(q_yoy_growths[:mid])
                accel_diff = recent_avg - older_avg
                accel = _sigmoid_normalize(accel_diff, center=0.0, scale=10.0) * 7.5
                rev_components['acceleration'] = round(accel_diff * 100, 1)
            elif len(q_yoy_growths) == 1 and yoy_growth is not None:
                accel = 3.75  # midpoint
            
            # Component 4: Earnings Beat Rate (4.5 pts max)
            beat_pts = 0
            if stock_yf:
                try:
                    eh = stock_yf.earnings_history
                    if eh is not None and not eh.empty and len(eh) >= 2:
                        recent = eh.tail(4)
                        beats = sum(1 for _, row in recent.iterrows() 
                                   if pd.notna(row.get('epsActual')) and pd.notna(row.get('epsEstimate'))
                                   and row['epsActual'] > row['epsEstimate'])
                        beat_rate = beats / len(recent)
                        
                        surprises = []
                        for _, row in recent.iterrows():
                            if (pd.notna(row.get('epsActual')) and pd.notna(row.get('epsEstimate')) 
                                and row['epsEstimate'] != 0):
                                surprises.append((row['epsActual'] - row['epsEstimate']) / abs(row['epsEstimate']))
                        avg_surprise = np.mean(surprises) if surprises else 0
                        
                        raw_beat = min(100, beat_rate * 50 + avg_surprise * 500)
                        beat_pts = max(0, raw_beat * 0.045)
                        rev_components['beat_rate'] = round(beat_rate * 100, 0)
                        rev_components['avg_surprise'] = round(avg_surprise * 100, 1)
                except:
                    pass
            
            revenue_pts = min(30, magnitude + consistency + accel + beat_pts)
            
            parts = []
            if yoy_growth is not None:
                parts.append(f"YoY: {yoy_growth*100:.1f}%")
            if 'acceleration' in rev_components:
                sign = "+" if rev_components['acceleration'] > 0 else ""
                parts.append(f"Accel: {sign}{rev_components['acceleration']:.0f}pp")
            if 'beat_rate' in rev_components:
                parts.append(f"Beats: {rev_components['beat_rate']:.0f}%")
            growth_display = ", ".join(parts) if parts else "N/A"
            
            if not parts:
                rev_g = info.get('revenueGrowth')
                if rev_g is not None:
                    magnitude = _sigmoid_normalize(float(rev_g), center=0.10, scale=5.0) * 10.5
                    revenue_pts = magnitude
                    growth_display = f"TTM: {float(rev_g)*100:.1f}% (fallback)"
                    
        except Exception as e:
            growth_display = f"Error: {str(e)[:30]}"
        
        results.append(CriterionResult("Revenue Score", "Growth", revenue_pts >= 15, growth_display, "Magnitude+Consistency+Accel+Beats", int(revenue_pts)))

        # 8. Earnings Acceleration (8 pts)
        earnings_accel_pts = 0
        earnings_accel_val = "N/A"
        if stock_yf:
            try:
                quarterly_income = stock_yf.quarterly_income_stmt
                if quarterly_income is not None and not quarterly_income.empty and 'Net Income' in quarterly_income.index:
                    net_income = quarterly_income.loc['Net Income'].dropna()
                    if len(net_income) >= 3:
                        net_income_values = net_income.values[::-1]
                        growth_rates = []
                        for i in range(1, min(len(net_income_values), 4)):
                            if net_income_values[i-1] != 0:
                                gr = (net_income_values[i] - net_income_values[i-1]) / abs(net_income_values[i-1])
                                growth_rates.append(gr)
                        
                        if len(growth_rates) >= 2:
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
            except:
                earnings_accel_val = "Data unavailable"
        else:
            earnings_accel_val = "No yfinance data"
        
        results.append(CriterionResult("Earnings Acceleration", "Growth", earnings_accel_pts > 0, earnings_accel_val, "QoQ growth accelerating", earnings_accel_pts))

        # 9. ROE Quality (5 pts)
        roe = info.get('returnOnEquity')
        passed_roe = bool(roe is not None and roe > 0.15)
        results.append(CriterionResult("ROE Quality", "Quality", passed_roe, f"{float(roe)*100:.1f}%" if roe else "N/A", "> 15%", 5 if passed_roe else 0))

        # 10. Operating Margin (5 pts)
        marg = info.get('operatingMargins')
        passed_marg = bool(marg is not None and marg > 0.10)
        results.append(CriterionResult("Operating Margin", "Quality", passed_marg, f"{float(marg)*100:.1f}%" if marg else "N/A", "> 10%", 5 if passed_marg else 0))

        # 11. Valuation Sanity (5 pts)
        peg = info.get('pegRatio')
        passed_peg = bool(peg is not None and peg < 2.0 and peg > 0)
        results.append(CriterionResult("Valuation Sanity", "Quality", passed_peg, f"{float(peg):.2f}" if peg else "N/A", "PEG < 2.0", 5 if passed_peg else 0))

        # 12. FCF Quality (3 pts)
        fcf = info.get('freeCashflow')
        passed_fcf = bool(fcf and fcf > 0)
        results.append(CriterionResult("FCF Quality", "Quality", passed_fcf, "Positive" if passed_fcf else "Negative/NA", "FCF > 0", 3 if passed_fcf else 0))

        # 13. Industry Strength (5 pts)
        sector = info.get('sector', '')
        sector_etf = self.SECTOR_ETFS.get(sector)
        passed_ind = False
        ind_val = sector or "Unknown"
        
        if sector_etf:
            try:
                spy_hist = get_spy_data()
                etf_hist = get_sector_etf_data(sector_etf)
                
                if not spy_hist.empty and not etf_hist.empty and len(spy_hist) >= 63 and len(etf_hist) >= 63:
                    spy_close = spy_hist['Close']
                    etf_close = etf_hist['Close']
                    etf_3m_return = (etf_close.iloc[-1] - etf_close.iloc[-63]) / etf_close.iloc[-63]
                    spy_3m_return = (spy_close.iloc[-1] - spy_close.iloc[-63]) / spy_close.iloc[-63]
                    sector_outperformance = etf_3m_return - spy_3m_return
                    passed_ind = sector_outperformance > 0
                    ind_val = f"{sector} ({sector_etf}: {float(sector_outperformance)*100:+.1f}% vs SPY)"
            except:
                ind_val = f"{sector} (no data)"
        
        results.append(CriterionResult("Industry Strength", "Context", passed_ind, ind_val, "Sector outperforming SPY (3mo)", 5 if passed_ind else 0))
        
        # 14. Relative Strength (5 pts)
        rs_points = 0
        rs_val = "N/A"
        
        try:
            spy_hist = get_spy_data()
            if not spy_hist.empty and len(close) >= 130 and len(spy_hist) >= 130:
                price_6m_ago = close.iloc[-130]
                stock_6m_return = (current_price - price_6m_ago) / price_6m_ago
                spy_close = spy_hist['Close']
                spy_6m_return = (spy_close.iloc[-1] - spy_close.iloc[-130]) / spy_close.iloc[-130]
                relative_strength = stock_6m_return - spy_6m_return
                if relative_strength > 0.10:
                    rs_points = 5
                elif relative_strength > 0.05:
                    rs_points = 3
                elif relative_strength > 0:
                    rs_points = 1
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
        if market_cap > 1_000_000_000_000:
            size_penalty = -10
        elif market_cap > 500_000_000_000:
            size_penalty = -5
        
        if size_penalty < 0:
            results.append(CriterionResult("Size Factor", "Context", False, f"${market_cap/1e12:.1f}T" if market_cap > 1e12 else f"${market_cap/1e9:.0f}B", "Large Cap Penalty", size_penalty))

        # --- Score & Grade ---
        score = min(100, int(sum(r.points for r in results)))
        grade = 'A' if score >= 70 else 'B' if score >= 55 else 'C' if score >= 40 else 'D' if score >= 25 else 'F'

        technical_score = int(sum(r.points for r in results if r.category in ["Momentum", "Breakout", "Timing"]))
        growth_score = int(sum(r.points for r in results if r.category == "Growth"))
        quality_score = int(sum(r.points for r in results if r.category == "Quality"))
        context_score = int(sum(r.points for r in results if r.category == "Context"))

        # --- Moonshot Score ---
        ms_pts = 0
        rev_g = yoy_growth
        rev_g_prior = q_yoy_growths[-2] if len(q_yoy_growths) >= 2 else None
        
        if rev_g and rev_g_prior and rev_g_prior > 0:
            accel_ratio = rev_g / rev_g_prior
            if accel_ratio > 1.5: ms_pts += 40
            elif accel_ratio > 1.2: ms_pts += 30
            elif accel_ratio > 1.0: ms_pts += 20
            
        revenue_ttm = info.get('totalRevenue')
        if market_cap and revenue_ttm and revenue_ttm > 0 and rev_g and rev_g > 0:
            ps_ratio = market_cap / revenue_ttm
            efficiency = ps_ratio / (rev_g * 100)
            if efficiency < 0.1: ms_pts += 30
            elif efficiency < 0.2: ms_pts += 20
            elif efficiency < 0.3: ms_pts += 10
            
        if passed_rs:
            ms_pts += 30

        # --- Build criteria list ---
        criteria_list = [asdict(r) for r in results]

        return {
            "ticker": ticker,
            "name": str(info.get('shortName', ticker))[:40],
            "sector": str(info.get('sector', 'N/A')),
            "industry": str(info.get('industry', 'N/A'))[:30],
            "score": score,
            "grade": grade,
            "max_score": 100,
            "technical_score": technical_score,
            "growth_score": growth_score,
            "quality_score": quality_score,
            "context_score": context_score,
            "moonshot_score": ms_pts,
            "criteria": criteria_list,
            "market_cap": market_cap,
            "forward_pe": info.get('forwardPE'),
            "trailing_pe": info.get('trailingPE'),
            "peg_ratio": info.get('pegRatio'),
            "recommendation": str(info.get('recommendationKey', 'N/A')),
            "target_mean": float(info['targetMeanPrice']) if info.get('targetMeanPrice') else None,
            "analyst_count": info.get('numberOfAnalystOpinions', 0),
            "current_price": float(current_price),
        }

    def rate_stock(self, ticker):
        """Rate a single stock using yfinance (live). Original API."""
        ticker = ticker.upper()
        try:
            stock = yf.Ticker(ticker)
            if db:
                hist = db.get_history_smart(ticker)
            else:
                hist = stock.history(period="1y")
            
            info = stock.info
            result = self._score_from_data(ticker, hist, info, db_conn=db.conn if db else None, stock_yf=stock)
            
            if "error" in result:
                return result
            
            # Add news (only available in live mode)
            news_items = []
            try:
                raw_news = stock.news or []
                for n in raw_news[:5]:
                    content = n.get('content', {})
                    title = content.get('title')
                    publisher = content.get('provider', {}).get('displayName')
                    link = content.get('canonicalUrl', {}).get('url')
                    pub_date = content.get('pubDate')
                    
                    if title:
                        time_str = "Recently"
                        if pub_date:
                            try:
                                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                                time_str = dt.strftime('%b %d, %H:%M')
                            except:
                                time_str = pub_date[:16] if pub_date else "Recently"
                        
                        news_items.append({
                            "title": title,
                            "publisher": publisher or "Yahoo Finance",
                            "link": link,
                            "time": time_str
                        })
            except:
                pass
            
            result["news"] = news_items
            
            # Add valuation/opinions dicts for backward compat with CLI output
            result["results"] = result["criteria"]  # alias
            result["valuation"] = {
                "forward_pe": result.get("forward_pe"),
                "trailing_pe": result.get("trailing_pe"),
                "peg_ratio": result.get("peg_ratio"),
                "book_value": info.get('bookValue'),
                "price_to_book": info.get('priceToBook'),
                "roe": info.get('returnOnEquity')
            }
            result["opinions"] = {
                "recommendation": result.get("recommendation", "N/A").replace('_', ' ').title(),
                "target_mean": result.get("target_mean"),
                "analysts": result.get("analyst_count")
            }
            
            return result
        except Exception as e:
            return {"error": str(e), "trace": traceback.format_exc()}

    def rate_stock_from_db(self, ticker, conn):
        """
        Rate a stock using only data from the sqlite DB (no yfinance for prices/fundamentals).
        Uses yfinance only for earnings_history and quarterly_income_stmt (earnings acceleration).
        
        Args:
            ticker: Stock ticker symbol
            conn: sqlite3 connection to market_data.db
        
        Returns:
            Dict with full scoring result, or None on error
        """
        try:
            # Load price history from DB
            prices = pd.read_sql_query(
                f"SELECT * FROM prices WHERE symbol = ? ORDER BY date",
                conn, params=(ticker,)
            )
            if len(prices) < 130:
                return None
            
            hist = prices.set_index('date')
            hist.index = pd.to_datetime(hist.index)
            
            # Load fundamentals from DB
            fund_df = pd.read_sql_query(
                "SELECT data FROM fundamentals WHERE symbol = ?",
                conn, params=(ticker,)
            )
            info = json.loads(fund_df.iloc[0]['data']) if not fund_df.empty else {}
            
            # Get yfinance Ticker for earnings data (lightweight - no price fetch)
            try:
                stock_yf = yf.Ticker(ticker)
            except:
                stock_yf = None
            
            result = self._score_from_data(ticker, hist, info, db_conn=conn, stock_yf=stock_yf)
            
            if "error" in result:
                return None
            
            return result
            
        except Exception as e:
            return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ticker = sys.argv[1]
        rater = BreakoutRater()
        result = rater.rate_stock(ticker)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python rater.py TICKER")

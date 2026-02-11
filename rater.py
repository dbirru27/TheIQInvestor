import yfinance as yf
import pandas as pd
import numpy as np
import os
import traceback
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

# Optional: DB-backed incremental updates
try:
    from market_data import MarketDB
    db = MarketDB()
except:
    db = None

@dataclass
class CriterionResult:
    name: str
    category: str
    passed: bool
    value: str
    threshold: str
    points: int = 0

class BreakoutRater:
    def __init__(self):
        # v4.2 High Potential - 100 Point Scale
        self.weights = {
            # Technical (48 pts)
            "Breakout Pattern": 22,      # Core timing
            "Consolidation": 10,         # Base quality  
            "Volume Dry-up": 8,          # Institutional quiet
            "Trend Alignment": 8,        # Direction
            
            # Growth (17 pts)
            "Sales Growth": 12,          # Revenue engine
            "Earnings Growth": 3,        # Profit growth
            "ROE Quality": 5,            # Capital efficiency
            
            # Quality/Value (13 pts)
            "Operating Margin": 5,       # Profitability
            "Valuation Sanity": 5,       # PEG < 2.0
            "FCF Quality": 3,            # Cash generation
            
            # Timing (10 pts)
            "52W Proximity": 5,          # Near highs
            "Volatility Compression": 5, # ATR squeeze
            
            # Context (7 pts)
            "Industry Strength": 5,      # Sector tailwind
            "Relative Strength": 5,      # vs Sector ETF
            
            # Size Penalty
            "Size Factor": 0             # -5 to -10 penalty
        }

    def rate_stock(self, ticker):
        ticker = ticker.upper()
        try:
            stock = yf.Ticker(ticker)
            # 1. Get Price History (Database-first optimized)
            if db:
                hist = db.get_history_smart(ticker)
            else:
                hist = stock.history(period="1y")  # Need 1y for 52w high
            
            if hist is None or hist.empty or len(hist) < 130:
                return {"error": "Insufficient history (130 days required)"}
            
            info = stock.info
            results = []
            
            # --- 1. MOMENTUM & BREAKOUT ---
            close = hist['Close']
            sma50 = close.rolling(50).mean().iloc[-1]
            sma200 = close.rolling(200).mean().iloc[-1]
            current_price = close.iloc[-1]
            price_above_50 = bool(current_price > sma50)
            
            # Trend Alignment (8 pts)
            if pd.notna(sma200):
                passed_trend = bool(price_above_50 and (sma50 > sma200))
                trend_desc = f"${float(current_price):.2f} > ${float(sma50):.2f} > ${float(sma200):.2f}"
            else:
                sma50_prev = close.rolling(50).mean().iloc[-5]
                passed_trend = bool(price_above_50 and sma50 > sma50_prev)
                trend_desc = f"${float(current_price):.2f} > ${float(sma50):.2f} (rising)"
            results.append(CriterionResult("Trend Alignment", "Momentum", passed_trend, trend_desc, "Price > SMA50 > SMA200", 8))

            # Breakout Pattern (22 pts)
            window = hist.iloc[-130:-5]
            high_1 = window.iloc[:65]['High'].max()
            high_2 = window.iloc[65:]['High'].max()
            drift = (high_2 - high_1) / high_1
            base_ceiling = max(high_1, high_2)
            dist = (base_ceiling - close.iloc[-1]) / base_ceiling
            passed_bo = bool((drift < 0.10) and (dist < 0.05))
            results.append(CriterionResult("Breakout Pattern", "Breakout", passed_bo, f"{float(dist)*100:+.1f}% from Base", "Flat Base + Near High", 22))

            # Consolidation (10 pts)
            depth = (window['High'].max() - window['Low'].min()) / window['High'].max()
            passed_con = bool(depth < 0.45)
            results.append(CriterionResult("Consolidation", "Breakout", passed_con, f"Depth {float(depth)*100:.0f}%", "Depth < 40%", 10))

            # Volume Dry-up (8 pts)
            v5, v50 = hist['Volume'].tail(5).mean(), hist['Volume'].tail(50).mean()
            passed_vol = bool(v5 < (v50 * 1.2))
            results.append(CriterionResult("Volume Dry-up", "Breakout", passed_vol, f"{float(v5/v50):.1f}x avg", "Vol < 1.2x Avg", 8))

            # --- 2. TIMING SIGNALS ---
            # 52-Week Proximity (5 pts)
            high_52w = hist['High'].max()
            proximity = current_price / high_52w
            passed_52w = bool(proximity > 0.90)
            results.append(CriterionResult("52W Proximity", "Timing", passed_52w, f"{float(proximity)*100:.1f}%", "> 90% of 52W High", 5))
            
            # Volatility Compression (5 pts)
            atr_current = (hist['High'].tail(14) - hist['Low'].tail(14)).mean()
            atr_20d = (hist['High'].tail(20) - hist['Low'].tail(20)).mean()
            passed_atr = bool(atr_current < 0.8 * atr_20d)
            results.append(CriterionResult("Volatility Compression", "Timing", passed_atr, "ATR Squeezing", "ATR < 80% of 20D ATR", 5))

            # --- 3. GROWTH & QUALITY ---
            # Sales Growth (0-30 pts) - PROPORTIONAL: min(max(0, growth/0.3*12), 30)
            rev_g = info.get('revenueGrowth')
            if rev_g is not None and rev_g > 0:
                sales_points = min(max(0, (rev_g / 0.30) * 12), 30)
            else:
                sales_points = 0
            results.append(CriterionResult("Sales Growth", "Growth", sales_points > 0, f"{float(rev_g)*100:.1f}%" if rev_g else "N/A", "Proportional 0-30", int(sales_points)))

            # Earnings Growth (3 pts)
            eps_g = info.get('earningsGrowth')
            passed_eps = bool(eps_g is not None and eps_g > 0.15)
            results.append(CriterionResult("Earnings Growth", "Growth", passed_eps, f"{float(eps_g)*100:.1f}%" if eps_g else "N/A", "> 15%", 3))

            # ROE Quality (5 pts)
            roe = info.get('returnOnEquity')
            passed_roe = bool(roe is not None and roe > 0.15)
            results.append(CriterionResult("ROE Quality", "Quality", passed_roe, f"{float(roe)*100:.1f}%" if roe else "N/A", "> 15%", 5))

            # Operating Margin (5 pts)
            marg = info.get('operatingMargins')
            passed_marg = bool(marg is not None and marg > 0.10)
            results.append(CriterionResult("Operating Margin", "Quality", passed_marg, f"{float(marg)*100:.1f}%" if marg else "N/A", "> 10%", 5))

            # Valuation Sanity (5 pts) - PEG < 2.0
            peg = info.get('pegRatio')
            passed_peg = bool(peg is not None and peg < 2.0 and peg > 0)
            results.append(CriterionResult("Valuation Sanity", "Quality", passed_peg, f"{float(peg):.2f}" if peg else "N/A", "PEG < 2.0", 5))

            # FCF Quality (3 pts)
            fcf = info.get('freeCashflow')
            passed_fcf = bool(fcf and fcf > 0)
            results.append(CriterionResult("FCF Quality", "Quality", passed_fcf, "Positive" if passed_fcf else "Negative/NA", "FCF > 0", 3))

            # --- 4. CONTEXT ---
            # Industry Strength (5 pts)
            sector = info.get('sector', '')
            strong_sectors = ['Technology', 'Healthcare', 'Communication Services', 'Industrials']
            passed_ind = sector in strong_sectors
            results.append(CriterionResult("Industry Strength", "Context", passed_ind, sector, "High-Conviction Sector", 5))
            
            # Relative Strength vs Sector (5 pts) - simplified proxy
            # Compare 1M return to SPY
            price_1m = close.iloc[-22] if len(close) >= 22 else close.iloc[0]
            ret_1m = (current_price - price_1m) / price_1m
            passed_rs = bool(ret_1m > 0.05)  # Outperforming by 5%
            results.append(CriterionResult("Relative Strength", "Context", passed_rs, f"{float(ret_1m)*100:+.1f}%", "> 5% vs Market", 5))

            # --- 5. SIZE PENALTY ---
            market_cap = info.get('marketCap', 0)
            size_penalty = 0
            if market_cap > 1_000_000_000_000:  # $1T+
                size_penalty = -10
            elif market_cap > 500_000_000_000:  # $500B+
                size_penalty = -5
            
            if size_penalty < 0:
                results.append(CriterionResult("Size Factor", "Context", False, f"${market_cap/1e12:.1f}T" if market_cap > 1e12 else f"${market_cap/1e9:.0f}B", "Large Cap Penalty", size_penalty))

            # Final Score Calculation (0-100)
            score = int(sum(r.points for r in results))
            
            # Tighter grading: A=70+ (70% of max), B=55-69, C=40-54, D=25-39, F=<25
            grade = 'A' if score >= 70 else 'B' if score >= 55 else 'C' if score >= 40 else 'D' if score >= 25 else 'F'

            m_score = int(sum(r.points for r in results if r.category in ["Momentum", "Breakout", "Timing"]))
            q_score = int(sum(r.points for r in results if r.category in ["Growth", "Quality"]))

            # News Relay
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
            except Exception:
                pass

            target_mean = info.get('targetMeanPrice')
            if target_mean: target_mean = float(target_mean)

            return {
                "ticker": ticker,
                "name": str(info.get('shortName', ticker)),
                "sector": str(info.get('sector', 'N/A')),
                "industry": str(info.get('industry', 'N/A')),
                "score": score,
                "grade": grade,
                "max_score": 100,
                "technical_score": m_score,
                "quality_score": q_score,
                "results": [asdict(r) for r in results],
                "news": news_items,
                "market_cap": market_cap,
                "valuation": {
                    "forward_pe": info.get('forwardPE'),
                    "trailing_pe": info.get('trailingPE'),
                    "peg_ratio": info.get('pegRatio'),
                    "book_value": info.get('bookValue'),
                    "price_to_book": info.get('priceToBook'),
                    "roe": info.get('returnOnEquity')
                },
                "opinions": {
                    "recommendation": str(info.get('recommendationKey', 'N/A')).replace('_', ' ').title(),
                    "target_mean": target_mean,
                    "analysts": info.get('numberOfAnalystOpinions')
                }
            }
        except Exception as e:
            return {"error": str(e), "trace": traceback.format_exc()}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ticker = sys.argv[1]
        rater = BreakoutRater()
        result = rater.rate_stock(ticker)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python rater.py TICKER")

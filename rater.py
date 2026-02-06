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
        self.weights = {
            "Trend Alignment": 5, 
            "Breakout Pattern": 20,
            "Consolidation": 10,
            "Volume Dry-up": 5,
            "Industry Strength": 10,
            "Sales Growth": 5,
            "Earnings Growth": 5, 
            "Operating Margin": 10,
            "FCF Quality": 5, 
            "Debt Safety": 5
        }

    def rate_stock(self, ticker):
        ticker = ticker.upper()
        try:
            stock = yf.Ticker(ticker)
            # 1. Get Price History (Database-first optimized)
            if db:
                hist = db.get_history_smart(ticker)
            else:
                hist = stock.history(period="9mo")
            
            if hist is None or hist.empty or len(hist) < 130:
                return {"error": "Insufficient history (130 days required)"}
            
            info = stock.info
            results = []
            
            # --- 1. MOMENTUM & BREAKOUT ---
            close = hist['Close']
            sma50 = close.rolling(50).mean().iloc[-1]
            sma200 = close.rolling(200).mean().iloc[-1]
            
            # Fix: Handle NaN in SMA200 when data is insufficient
            current_price = close.iloc[-1]
            price_above_50 = bool(current_price > sma50)
            
            # Only check SMA200 if we have valid data, otherwise use SMA50 trend only
            if pd.notna(sma200):
                passed_trend = bool(price_above_50 and (sma50 > sma200))
                trend_desc = f"${float(current_price):.2f} > ${float(sma50):.2f} > ${float(sma200):.2f}"
            else:
                # Fallback: Just check price above 50 SMA and rising
                sma50_prev = close.rolling(50).mean().iloc[-5]  # 5 days ago
                passed_trend = bool(price_above_50 and sma50 > sma50_prev)
                trend_desc = f"${float(current_price):.2f} > ${float(sma50):.2f} (rising)"
            
            results.append(CriterionResult("Trend Alignment", "Momentum", passed_trend, trend_desc, "Price > SMA50 > SMA200", 5))

            # Breakout Pattern (v3.5)
            # Check for consolidation (drift < 10% in the last 6 months of base)
            # and current price within 3% of that base ceiling
            window = hist.iloc[-130:-5]
            high_1 = window.iloc[:65]['High'].max()
            high_2 = window.iloc[65:]['High'].max()
            drift = (high_2 - high_1) / high_1
            base_ceiling = max(high_1, high_2)
            dist = (base_ceiling - close.iloc[-1]) / base_ceiling
            passed_bo = bool((drift < 0.10) and (dist < 0.05))
            results.append(CriterionResult("Breakout Pattern", "Breakout", passed_bo, f"{float(dist)*100:+.1f}% from Base", "Flat Base + Near High", 20))

            depth = (window['High'].max() - window['Low'].min()) / window['High'].max()
            passed_con = bool(depth < 0.45)
            results.append(CriterionResult("Consolidation", "Breakout", passed_con, f"Depth {float(depth)*100:.0f}%", "Depth < 40%", 10))

            v5, v50 = hist['Volume'].tail(5).mean(), hist['Volume'].tail(50).mean()
            passed_vol = bool(v5 < (v50 * 1.2))
            results.append(CriterionResult("Volume Dry-up", "Breakout", passed_vol, f"{float(v5/v50):.1f}x avg", "Vol < 1.2x Avg", 5))

            # --- 2. QUALITY & GROWTH ---
            rev_g = info.get('revenueGrowth')
            results.append(CriterionResult("Sales Growth", "Growth", bool(rev_g is not None and rev_g > 0.1), f"{float(rev_g)*100:.1f}%" if rev_g else "N/A", "> 10%", 10))

            eps_g = info.get('earningsGrowth')
            results.append(CriterionResult("Earnings Growth", "Growth", bool(eps_g is not None and eps_g > 0.15), f"{float(eps_g)*100:.1f}%" if eps_g else "N/A", "> 15%", 10))

            marg = info.get('operatingMargins')
            results.append(CriterionResult("Operating Margin", "Quality", bool(marg is not None and marg > 0.1), f"{float(marg)*100:.1f}%" if marg else "N/A", "> 10%", 10))

            fcf = info.get('freeCashflow')
            passed_fcf = bool(fcf and fcf > 0)
            results.append(CriterionResult("FCF Quality", "Quality", passed_fcf, "Positive" if passed_fcf else "Negative/NA", "FCF > 0", 5))

            # Final Score Calculation
            score = int(sum(r.points for r in results if r.passed))
            grade = 'A' if score >= 50 else 'B' if score >= 35 else 'C' if score >= 20 else 'D' if score >= 10 else 'F'

            m_score = int(sum(r.points for r in results if r.passed and r.category in ["Momentum", "Breakout"]))
            q_score = int(sum(r.points for r in results if r.passed and r.category in ["Growth", "Quality"]))

            # News Relay (yfinance 2024+ structure: nested under 'content')
            news_items = []
            try:
                raw_news = stock.news or []
                for n in raw_news[:5]:
                    content = n.get('content', {})
                    
                    title = content.get('title')
                    publisher = content.get('provider', {}).get('displayName')
                    link = content.get('canonicalUrl', {}).get('url')
                    pub_date = content.get('pubDate')  # ISO string like '2026-02-03T16:01:09Z'
                    
                    if title:
                        time_str = "Recently"
                        if pub_date:
                            try:
                                # Parse ISO date string
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
                "score": score,
                "grade": grade,
                "momentum_score": float(m_score * (100/40)), # Scale to 100
                "quality_score": float(q_score * (100/35)),   # Scale to 100
                "results": [asdict(r) for r in results],
                "news": news_items,
                "valuation": {
                    "forward_pe": info.get('forwardPE'),
                    "trailing_pe": info.get('trailingPE'),
                    "peg_ratio": info.get('pegRatio'),
                    "book_value": info.get('bookValue'),
                    "price_to_book": info.get('priceToBook')
                },
                "opinions": {
                    "recommendation": str(info.get('recommendationKey', 'N/A')).replace('_', ' ').title(),
                    "target_mean": target_mean,
                    "analysts": info.get('numberOfAnalystOpinions')
                }
            }
        except Exception as e:
            return {"error": str(e), "trace": traceback.format_exc()}

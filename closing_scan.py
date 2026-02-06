import json
import os
from datetime import datetime
import sys
import yfinance as yf
import pandas as pd
import traceback
from dataclasses import dataclass, asdict

# Ensure we're in the workspace root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

@dataclass
class CriterionResult:
    name: str
    category: str
    passed: bool
    value: str
    threshold: str
    points: int = 0

class ScanEngine:
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

    def rate(self, ticker):
        ticker = ticker.upper()
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 130: return None
            
            def get_col(df, name):
                if isinstance(df.columns, pd.MultiIndex): return df[name].iloc[:, 0]
                return df[name]

            close = get_col(hist, 'Close')
            highs = get_col(hist, 'High')
            lows = get_col(hist, 'Low')
            info = stock.info
            
            results = []
            
            # Trend
            sma50 = close.rolling(50).mean().iloc[-1]
            sma200 = close.rolling(200).mean().iloc[-1]
            passed_trend = bool((close.iloc[-1] > sma50) and (sma50 > sma200))
            results.append(CriterionResult("Trend Alignment", "Momentum", passed_trend, f"${close.iloc[-1]:.2f}", "Price > SMA50", 5))

            # Breakout
            window = hist.iloc[-130:-5]
            w_highs = get_col(window, 'High')
            high_1, high_2 = w_highs.iloc[:65].max(), w_highs.iloc[65:].max()
            drift = (high_2 - high_1) / high_1
            base_ceiling = max(high_1, high_2)
            dist = (base_ceiling - close.iloc[-1]) / base_ceiling
            passed_bo = bool((drift < 0.10) and (dist < 0.05))
            results.append(CriterionResult("Breakout Pattern", "Breakout", passed_bo, f"{drift*100:+.1f}% drift", "Flat Base", 20))

            # Consolidation
            depth = (w_highs.max() - get_col(window, 'Low').min()) / w_highs.max()
            passed_con = bool(depth < 0.45)
            results.append(CriterionResult("Consolidation", "Breakout", passed_con, f"Depth {depth*100:.0f}%", "Depth < 45%", 10))

            # Quality
            rev_g = info.get('revenueGrowth', 0)
            results.append(CriterionResult("Sales Growth", "Growth", bool(rev_g and rev_g > 0.1), f"{float(rev_g)*100:.1f}%" if rev_g else "N/A", "> 10%", 10))

            score = int(sum(r.points for r in results if r.passed))
            grade = 'A' if score >= 40 else 'B' if score >= 25 else 'C' if score >= 15 else 'F'
            
            return {
                "ticker": ticker,
                "name": info.get('shortName', ticker),
                "total": score,
                "grade": grade,
                "sector": info.get('sector', 'N/A')
            }
        except: return None

def run_closing_protocol():
    print(f"--- 6:00 PM PST CLOSING RUN ---")
    tickers = []
    if os.path.exists('vug_tickers.txt'):
        with open('vug_tickers.txt', 'r') as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    
    # Core focus names
    core_names = ["VRT", "GE", "MU", "LLY", "NVDA", "MLM", "O", "PWR", "MSCI", "ROL", "TPL", "ECL", "MPWR"]
    tickers = list(set(tickers + core_names))
    
    engine = ScanEngine()
    
    final_list = []
    for t in tickers:
        print(f"Rating {t}...")
        res = engine.rate(t)
        if res: final_list.append(res)
    
    final_list.sort(key=lambda x: x['total'], reverse=True)
    
    output = {
        "last_scan": datetime.now().strftime("%A, %B %d, %Y @ %I:%M %p PST"),
        "stocks": final_list[:50]
    }
    
    with open('top_stocks.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print("✅ Scan complete.")

if __name__ == "__main__":
    run_closing_protocol()

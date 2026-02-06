import sys
import os
import json

# Add path for existing logic
sys.path.append(os.path.join(os.getcwd(), "skills", "market-analyst"))
from rater import StockRater

def rank_stocks(tickers):
    results = []
    
    weights = {
        "Trend Alignment": 20, 
        "Relative Strength": 30, 
        "Volume Footprint": 10, 
        "Industry Strength": 20, 
        "Upcoming Catalyst": 0,
        "Sales Growth": 5, 
        "Earnings Growth": 5, 
        "Operating Margin": 2, 
        "FCF Quality": 2, 
        "Debt Safety": 2, 
        "Short Interest": 4 
    }
    
    for ticker in tickers:
        try:
            print(f"Rating {ticker}...")
            rater = StockRater(ticker)
            if not rater.is_valid:
                continue
                
            methods = {
                "Trend Alignment": rater.c1_trend, "Relative Strength": rater.c2_rs, "Volume Footprint": rater.c3_vol,
                "Industry Strength": rater.c9_industry, "Upcoming Catalyst": rater.c13_catalyst,
                "Sales Growth": rater.c4_sales, "Earnings Growth": rater.c5_eps,
                "Operating Margin": rater.c6_margin, "FCF Quality": rater.c7_fcf, "Debt Safety": rater.c8_debt,
                "Short Interest": rater.c12_short
            }
            
            total_score = 0
            for name, method in methods.items():
                try:
                    res = method()
                    if res.passed:
                        total_score += weights.get(name, 0)
                except:
                    pass
            
            results.append({
                "ticker": ticker,
                "name": rater.info.get("longName", ticker),
                "score": total_score
            })
        except:
            print(f"Error rating {ticker}")
            
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

if __name__ == "__main__":
    tickers = ["MRVL", "ANET", "WDC", "AMD", "MU", "AVGO", "TSM", "STX", "ASML"]
    ranked = rank_stocks(tickers)
    
    print("\nRANKING RESULTS:")
    print(f"{'RANK':<5} {'TICKER':<8} {'NAME':<30} {'SCORE':<5}")
    print("-" * 50)
    for i, res in enumerate(ranked, 1):
        print(f"{i:<5} {res['ticker']:<8} {res['name'][:30]:<30} {res['score']:<5}")

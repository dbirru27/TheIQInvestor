import sys
import os
import json

# Add path for existing logic
sys.path.append(os.getcwd())
from invest_iq.app import InvestIQEngine

def master_rank(tickers):
    results = []
    print(f"Ranking {len(tickers)} tickers...")
    
    for ticker in tickers:
        try:
            # Using the new Dual-Engine logic from app.py
            data = InvestIQEngine.get_rating(ticker)
            if data['grade'] == 'F' and data['momentum_score'] == 0:
                continue
                
            results.append({
                "ticker": ticker,
                "name": data['name'],
                "momentum": data['momentum_score'],
                "quality": data['quality_score'],
                "total": data['total_score'],
                "grade": data['grade']
            })
        except Exception as e:
            print(f"Error rating {ticker}: {e}")
            
    # Sort by total score
    results.sort(key=lambda x: x['total'], reverse=True)
    return results

if __name__ == "__main__":
    tickers = [
        "MU", "META", "ANET", "LRCX", "AMAT", "AMD", "NVDA", "CAT", "GOOGL", "LLY", "AVGO", "V",
        "AMZN", "TSLA", "GE", "CRWD", "MSFT", "TMUS", "JPM", "NFLX", "UNH", "UBER", "BRK-B", "HD",
        "MRVL", "WDC", "TSM", "STX", "ASML"
    ]
    ranked = master_rank(tickers)
    
    print("\nINVEST IQ MASTER LEADERBOARD:")
    print(f"{'RANK':<5} {'TICKER':<8} {'NAME':<25} {'MOM.':<5} {'QUAL.':<5} {'TOTAL':<5} {'GRADE'}")
    print("-" * 75)
    for i, res in enumerate(ranked, 1):
        print(f"{i:<5} {res['ticker']:<8} {res['name'][:25]:<25} {res['momentum']:<5} {res['quality']:<5} {res['total']:<5} {res['grade']}")

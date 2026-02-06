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
            print(f"Processing {ticker}...")
            data = InvestIQEngine.get_rating(ticker)
            if data['grade'] == 'F' and data['momentum_score'] == 0:
                continue
                
            res = {
                "ticker": ticker,
                "name": data['name'],
                "momentum": data['momentum_score'],
                "quality": data['quality_score'],
                "total": data['total_score'],
                "grade": data['grade']
            }
            results.append(res)
            # Save partial results
            with open("ranking_partial.json", "w") as f:
                json.dump(results, f)
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
    
    with open("ranking_final.json", "w") as f:
        json.dump(ranked, f)
    print("\nMaster Rank Complete.")

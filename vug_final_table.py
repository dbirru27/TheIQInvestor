import sys
import os
import json

# Add path for existing logic
sys.path.append(os.getcwd())
from invest_iq.app import InvestIQEngine

def vug_master_rank(ticker_file):
    with open(ticker_file, 'r') as f:
        tickers = [line.strip().upper() for line in f if line.strip()]
    
    results = []
    print(f"Ranking {len(tickers)} VUG tickers...")
    
    for i, ticker in enumerate(tickers):
        try:
            data = InvestIQEngine.get_rating(ticker)
            if data['grade'] == 'F' and data['momentum_score'] == 0:
                continue
                
            results.append({
                "rank": 0, # Placeholder
                "ticker": ticker,
                "mom": data['momentum_score'] * 2,
                "qual": data['quality_score'] * 2,
                "total": data['total_score'],
                "grade": data['grade']
            })
        except:
            continue
            
    # Sort by total score
    results.sort(key=lambda x: x['total'], reverse=True)
    
    # Header
    table = "RANK  TICKER    MOM   QUAL  SCORE  GRADE\n"
    table += "────────────────────────────────────────\n"
    
    for i, r in enumerate(results[:50], 1):
        table += f"{i:02d}    {r['ticker']:<8}  {r['mom']:<4}  {r['qual']:<4}  {r['total']:<5}  {r['grade']}\n"
    
    table += "────────────────────────────────────────"
    print(table)

if __name__ == "__main__":
    vug_master_rank("vug_tickers.txt")

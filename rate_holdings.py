import sys
import os
import json
from market_data import MarketDB

# Add path for existing logic
sys.path.append(os.getcwd())
try:
    from invest_iq.app import InvestIQEngine
except ImportError:
    # Fallback if running from a different dir
    sys.path.append(os.path.join(os.getcwd(), "invest_iq"))
    from app import InvestIQEngine

def rate_holdings(holdings_file):
    if not os.path.exists(holdings_file):
        print(f"Error: {holdings_file} not found.")
        return
        
    with open(holdings_file, 'r') as f:
        # Handle BRK-B vs BRK.B vs BRKB
        tickers = []
        for line in f:
            t = line.strip().upper()
            if not t: continue
            if t == "BRKB": t = "BRK-B" # Yahoo format
            tickers.append(t)
    
    # Remove duplicates
    tickers = list(set(tickers))
    
    # 1. Ensure DB has data for these specific tickers
    print(f"Updating DB for {len(tickers)} holdings...")
    db = MarketDB()
    for t in tickers:
        try:
            db.update_ticker(t)
        except:
            print(f"Failed to update {t}")

    # 2. Rate them
    results = []
    print(f"\nRating {len(tickers)} holdings...")
    
    for i, ticker in enumerate(tickers):
        try:
            print(f"Rating {ticker}...")
            data = InvestIQEngine.get_rating(ticker)
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
            continue
            
    # Sort by Score
    results.sort(key=lambda x: x['total'], reverse=True)
    
    # Print Table
    print("\n[ YOUR HOLDINGS: BREAKOUT ANALYSIS ]")
    print(f"{'RANK':<4} {'TICKER':<6} {'SCORE':<5} {'GRADE':<5} {'NOTE'}")
    print("─" * 40)
    
    for i, r in enumerate(results):
        note = "Top Pick" if r['grade'] in ['A', 'A+'] else \
               "Valid Base" if r['grade'] in ['B+', 'B', 'B-'] else \
               "Watch/Hold" if r['grade'] == 'C' else \
               "Avoid/Sell"
        print(f"{i+1:<4} {r['ticker']:<6} {r['total']:<5} {r['grade']:<5} {note}")

if __name__ == "__main__":
    rate_holdings("holdings.txt")

import sys
import os
import json
from market_data import MarketDB
import config
from utils.logger import get_logger

logger = get_logger('rate_holdings')

# Add path for existing logic
sys.path.append(os.getcwd())
from rater import BreakoutRater

_rater = BreakoutRater()

def rate_holdings(holdings_file):
    if not os.path.exists(holdings_file):
        logger.error(f"Error: {holdings_file} not found.")
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
    logger.info(f"Updating DB for {len(tickers)} holdings...")
    db = MarketDB()
    for t in tickers:
        try:
            db.update_ticker(t)
        except:
            logger.warning(f"Failed to update {t}")

    # 2. Rate them
    results = []
    logger.info(f"Rating {len(tickers)} holdings...")
    
    for i, ticker in enumerate(tickers):
        try:
            logger.debug(f"Rating {ticker}...")
            data = _rater.rate_stock(ticker)
            if "error" in data:
                logger.warning(f"Skipping {ticker}: {data['error']}")
                continue
            results.append({
                "ticker": ticker,
                "name": data.get('name', ticker),
                "momentum": data.get('technical_score', 0),
                "quality": data.get('quality_score', 0),
                "total": data.get('score', 0),
                "grade": data.get('grade', 'F')
            })
        except Exception as e:
            logger.error(f"Error rating {ticker}: {e}")
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

import sys
import os
from market_data import MarketDB
import config
from utils.logger import get_logger

logger = get_logger('scan_all_top10')

# Add path for existing logic
sys.path.append(os.getcwd())
from rater import BreakoutRater

_rater = BreakoutRater()

def scan_all():
    # 1. Aggregate all known tickers
    tickers = set()
    
    # Add config tickers
    tickers.update(config.PORTFOLIO_TICKERS)
    tickers.update(config.CORE_ETFS)
    
    # Load VUG Universe
    if os.path.exists('vug_tickers.txt'):
        with open('vug_tickers.txt', 'r') as f:
            for line in f:
                t = line.strip().upper()
                if t: tickers.add(t)
    
    # Load User Holdings
    if os.path.exists('all_holdings.txt'):
        with open('all_holdings.txt', 'r') as f:
            for line in f:
                t = line.strip().upper()
                if t: tickers.add(t)

    target_list = list(tickers)
    logger.info(f"Scanning universe of {len(target_list)} unique tickers...")
    
    results = []
    for t in target_list:
        try:
            # We assume DB is populated enough from previous runs
            data = _rater.rate_stock(t)
            if "error" in data:
                continue
            results.append({
                "ticker": t,
                "score": data.get('score', 0),
                "grade": data.get('grade', 'F'),
                "momentum": data.get('technical_score', 0),
                "quality": data.get('quality_score', 0)
            })
        except:
            continue
            
    # Sort
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # Print Top 10
    print("\n🏆 TOP 10 BREAKOUT CANDIDATES (Combined Universe)")
    print(f"{'RANK':<4} {'TICKER':<6} {'SCORE':<5} {'GRADE':<5} {'MOM/QUAL'}")
    print("──────────────────────────────────────")
    
    for i, r in enumerate(results[:10]):
        print(f"{i+1:<4} {r['ticker']:<6} {r['score']:<5} {r['grade']:<5} {r['momentum']}/{r['quality']}")

if __name__ == "__main__":
    scan_all()

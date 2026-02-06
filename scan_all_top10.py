import sys
import os
from market_data import MarketDB

# Add path for existing logic
sys.path.append(os.getcwd())
try:
    from invest_iq.app import InvestIQEngine
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), "invest_iq"))
    from app import InvestIQEngine

def scan_all():
    # 1. Aggregate all known tickers
    tickers = set()
    
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
    print(f"Scanning universe of {len(target_list)} unique tickers...")
    
    results = []
    for t in target_list:
        try:
            # We assume DB is populated enough from previous runs
            data = InvestIQEngine.get_rating(t)
            results.append({
                "ticker": t,
                "score": data['total_score'],
                "grade": data['grade'],
                "momentum": data['momentum_score'],
                "quality": data['quality_score']
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

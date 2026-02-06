import sys
import os
import yfinance as yf
from market_data import MarketDB

def scan_value_growth():
    # Load VUG Universe
    tickers = []
    if os.path.exists('vug_tickers.txt'):
        with open('vug_tickers.txt', 'r') as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    
    tickers = list(set(tickers))
    print(f"Scanning {len(tickers)} VUG stocks for PE < 30 and PEG < 5...")
    
    results = []
    db = MarketDB()
    
    for t in tickers:
        try:
            # Try DB first
            info = db.get_fundamentals(t)
            if not info:
                # Fetch fresh if missing
                stock = yf.Ticker(t)
                info = stock.info
                db.save_fundamentals(t, info)
            
            # Get Metrics
            fwd_pe = info.get('forwardPE')
            peg = info.get('pegRatio')
            rev_growth = info.get('revenueGrowth', 0) # 0.20 = 20%
            
            # Filter
            # Ensure values are not None before comparing
            if fwd_pe is not None and peg is not None:
                # Widened: PE < 35, PEG < 5.0
                if fwd_pe < 35 and peg < 5.0:
                    results.append({
                        "ticker": t,
                        "name": info.get('shortName', t),
                        "pe": fwd_pe,
                        "peg": peg,
                        "growth": (rev_growth * 100) if rev_growth else 0,
                        "sector": info.get('sector', 'N/A')
                    })
        except Exception as e:
            continue

    # Sort by Growth (Highest Growth first)
    results.sort(key=lambda x: x['growth'], reverse=True)
    
    print("\n[ TOP 10 VUG: VALUE GROWTH (PE<35, PEG<5, Sorted by Growth) ]")
    print(f"{'RANK':<4} {'TICKER':<6} {'FWD PE':<8} {'PEG':<6} {'GROWTH':<8} {'SECTOR'}")
    print("──────────────────────────────────────────────────────────")
    
    for i, r in enumerate(results[:15]):
        print(f"{i+1:<4} {r['ticker']:<6} {r['pe']:<8.1f} {r['peg']:<6.2f} {r['growth']:<8.1f} {r['sector']}")

if __name__ == "__main__":
    scan_value_growth()

import json
import os
from datetime import datetime
from rater import BreakoutRater

def run_universe_scan():
    print("🚀 Starting Universe Scan for Website Update...")
    rater = BreakoutRater()
    tickers = set()
    
    # 1. Load Universes (including Russell 1000)
    for f_path in ['russell1000_tickers.txt', 'vug_tickers.txt', 'all_holdings.txt', 'holdings.txt']:
        if os.path.exists(f_path):
            with open(f_path, 'r') as f:
                for line in f:
                    t = line.strip().upper()
                    if t and len(t) <= 6: tickers.add(t)
    
    print(f"Targeting {len(tickers)} tickers.")
    
    results = []
    count = 0
    for t in tickers:
        try:
            data = rater.rate_stock(t)
            if data and "error" not in data:
                # Format for the dashboard template
                results.append({
                    "ticker": data['ticker'],
                    "name": data['name'],
                    "sector": data['sector'],
                    "total": data['score'], # Template uses .total
                    "grade": data['grade']
                })
                count += 1
                if count % 10 == 0:
                    print(f"Processed {count}...")
        except Exception as e:
            continue

    # 2. Sort by Score
    results.sort(key=lambda x: x['total'], reverse=True)
    
    # 3. Save to top_stocks.json
    output = {
        "last_scan": datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        "stocks": results[:50] # Top 50 for the table
    }
    
    with open('top_stocks.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Successfully updated top_stocks.json with {len(results)} results.")

if __name__ == "__main__":
    run_universe_scan()

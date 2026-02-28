import sys
import os
from market_data import MarketDB

def populate():
    db = MarketDB()
    
    # Load tickers
    with open('vug_tickers.txt', 'r') as f:
        tickers = [t.strip().upper() for t in f.readlines() if t.strip()]
        
    print(f"Populating DB for {len(tickers)} tickers...")
    
    count = 0
    for t in tickers:
        print(f"[{count+1}/{len(tickers)}] Updating {t}...")
        try:
            db.update_ticker(t)
            count += 1
        except Exception as e:
            print(f"Failed {t}: {e}")
            
    print("DB Population Complete.")

if __name__ == "__main__":
    populate()

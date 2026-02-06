import sys
import os
import json
import time

# Add path for existing logic
sys.path.append(os.getcwd())
from invest_iq.app import InvestIQEngine

def vug_rank(ticker_file):
    if not os.path.exists(ticker_file):
        print(f"Error: {ticker_file} not found.")
        return
        
    with open(ticker_file, 'r') as f:
        tickers = [line.strip().upper() for line in f if line.strip()]
    
    total_count = len(tickers)
    results = []
    print(f"InvestIQ VUG Scan starting for {total_count} tickers...")
    
    for i, ticker in enumerate(tickers):
        try:
            # Update progress for the watchdog
            percent = int((i + 1) / total_count * 100)
            if percent % 5 == 0:
                print(f"PROGRESS: [{('#' * (percent // 5)).ljust(20)}] {percent}% - Rating {ticker}...")
            
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
        except:
            continue
            
    # Sort and take top 50
    results.sort(key=lambda x: x['total'], reverse=True)
    top_50 = results[:50]
    
    with open("vug_top_50.json", "w") as f:
        json.dump(top_50, f)
        
    print("\nSCAN COMPLETE.")

if __name__ == "__main__":
    vug_rank("vug_tickers.txt")

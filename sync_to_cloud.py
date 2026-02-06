import sqlite3
import requests
import json
from datetime import datetime

VERCEL_URL = "https://www.qortexai.com/api/sync"

def sync_to_cloud():
    print(f"Connecting to local database...")
    conn = sqlite3.connect('market_data.db')
    conn.row_factory = sqlite3.Row
    
    # The actual table name/schema on Mac might differ from the app logic
    # Looking at logs, it seems the table info shows 'symbol' instead of 'ticker'
    try:
        stocks = conn.execute('SELECT * FROM tickers').fetchall()
    except Exception as e:
        print(f"Database error: {e}")
        return

    data_to_send = []
    for s in stocks:
        # Map DB columns to what Vercel app expects
        # DB has: symbol, name, sector, industry, last_updated
        # App expects: ticker, name, score, grade, trend, setup, vol_dryup, rs_rating, sector, last_updated
        
        # We need to fill in some defaults since the current local DB is just fundamentals
        ticker = s['symbol'] if 'symbol' in s.keys() else s[0]
        
        data_to_send.append({
            "ticker": ticker,
            "name": s['name'] or ticker,
            "score": 0, # Placeholders for now
            "grade": "N/A",
            "trend": "N/A",
            "setup": "N/A",
            "vol_dryup": "N/A",
            "rs_rating": "N/A",
            "sector": s['sector'] or "N/A",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    print(f"Sending {len(data_to_send)} stocks to {VERCEL_URL}...")
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(VERCEL_URL, json=data_to_send, headers=headers, timeout=30)
        
        if response.status_code == 200:
            print("✅ Sync Successful!")
            print(response.json())
        else:
            print(f"❌ Sync Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error during sync: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    sync_to_cloud()

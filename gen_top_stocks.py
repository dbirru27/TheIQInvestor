import sqlite3
import json
import os

def generate_top_stocks_json():
    print("Generating top_stocks.json for Vercel...")
    conn = sqlite3.connect('market_data.db')
    conn.row_factory = sqlite3.Row
    # Get top 50 stocks by score
    stocks = conn.execute('SELECT * FROM tickers ORDER BY score DESC LIMIT 50').fetchall()
    
    data = []
    for s in stocks:
        data.append(dict(s))
    
    with open('top_stocks.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    conn.close()
    print(f"✅ Generated top_stocks.json with {len(data)} stocks.")

if __name__ == "__main__":
    generate_top_stocks_json()

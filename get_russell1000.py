#!/usr/bin/env python3
"""
Fetch Russell 1000 tickers from Wikipedia
"""
import pandas as pd
import requests
from io import StringIO

def get_russell_1000():
    """Scrape Russell 1000 constituents from Wikipedia"""
    url = "https://en.wikipedia.org/wiki/Russell_1000_Index"
    
    try:
        # Add headers to avoid 403
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        tables = pd.read_html(StringIO(response.text))
        # Find the table with Company/Symbol columns
        for df in tables:
            cols = [str(c).lower() for c in df.columns]
            if 'symbol' in cols or 'ticker' in cols:
                # Find the symbol column
                sym_col = None
                for c in df.columns:
                    if 'symbol' in str(c).lower() or 'ticker' in str(c).lower():
                        sym_col = c
                        break
                if sym_col:
                    tickers = df[sym_col].dropna().astype(str).str.strip().tolist()
                    # Clean up tickers - allow dots for BRK.B etc
                    clean = []
                    for t in tickers:
                        t = t.replace('.', '-')  # BRK.B -> BRK-B for yfinance
                        if t and len(t) <= 6 and t[0].isalpha():
                            clean.append(t)
                    return clean
    except Exception as e:
        print(f"Wikipedia scrape failed: {e}")
    
    return []

if __name__ == "__main__":
    print("Fetching Russell 1000 tickers...")
    tickers = get_russell_1000()
    
    if len(tickers) > 500:
        print(f"✅ Found {len(tickers)} tickers")
        with open('russell1000_tickers.txt', 'w') as f:
            for t in sorted(set(tickers)):
                f.write(t + '\n')
        print(f"Saved to russell1000_tickers.txt")
    else:
        print(f"⚠️  Only found {len(tickers)} tickers, may be incomplete")
        if tickers:
            with open('russell1000_tickers.txt', 'w') as f:
                for t in sorted(set(tickers)):
                    f.write(t + '\n')
            print(f"Saved partial list to russell1000_tickers.txt")

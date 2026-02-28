import requests
from bs4 import BeautifulSoup
import sys

def get_vug_tickers():
    url = "https://stockanalysis.com/etf/vug/holdings/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print("Fetching VUG holdings from StockAnalysis...")
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        # Tickers are usually in a table with links like /stocks/aapl/
        tickers = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/symbol/s/'):
                # Some sites use /symbol/s/ticker
                ticker = href.split('/')[-2].upper()
                if ticker not in tickers:
                    tickers.append(ticker)
            elif href.startswith('/stocks/'):
                ticker = href.split('/')[-2].upper()
                if ticker and ticker != 'STOCKS' and ticker not in tickers:
                    tickers.append(ticker)
        
        # Filter for likely tickers (all caps, short)
        valid_tickers = [t for t in tickers if t.isalpha() and 1 <= len(t) <= 5]
        return sorted(list(set(valid_tickers)))
    except Exception as e:
        print(f"Scraping error: {e}")
        return []

if __name__ == "__main__":
    tickers = get_vug_tickers()
    if tickers:
        print(f"Found {len(tickers)} tickers. Saving to vug_tickers.txt...")
        with open("vug_tickers.txt", "w") as f:
            for t in tickers:
                f.write(t + "\n")
        print("Done.")
    else:
        print("Failed to find tickers.")

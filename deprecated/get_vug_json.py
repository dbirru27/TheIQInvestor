import requests
import re
import json

def get_vug_full():
    url = "https://stockanalysis.com/etf/vug/holdings/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print("Fetching VUG full list from StockAnalysis...")
    try:
        response = requests.get(url, headers=headers)
        # Look for the JSON data in the script tag (common in Next.js/React apps)
        # Typically under window.__NEXT_DATA__ or similar
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if match:
            data = json.loads(match.group(1))
            # Drill down into the holdings
            # Structure varies, but usually under props.pageProps.data.holdings
            try:
                holdings = data['props']['pageProps']['data']['holdings']
                tickers = [h['s'] for h in holdings] # 's' is usually symbol
                return tickers
            except:
                pass
                
        # Fallback: simple regex for all uppercase 1-5 char words in a likely area
        # This is a bit risky but can work if the above fails
        tickers = re.findall(r'\"s\":\"([A-Z]{1,5})\"', response.text)
        return sorted(list(set(tickers)))
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    list_vug = get_vug_full()
    if list_vug:
        print(f"Success! Found {len(list_vug)} tickers.")
        with open("vug_tickers.txt", "w") as f:
            for t in list_vug:
                f.write(t + "\n")
    else:
        print("Failed to find tickers.")

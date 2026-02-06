import json
from rater import BreakoutRater
from datetime import datetime

PORTFOLIO = {
    "Defense": ["LHX", "LMT", "NOC", "GE"],
    "Grid-to-Chip": ["PWR", "VRT", "GEV"],
    "TopVOO": ["MSFT", "AMZN", "GOOGL", "META", "NVDA", "AMD", "AVGO", "TSLA", "LLY"],
    "Core ETFs": ["COPX", "GLD", "GLDM", "ITA", "IWM", "NLR", "VOO", "XLI"]
}

def main():
    rater = BreakoutRater()
    report = []
    
    # Only rate individual stocks, not ETFs for now as rater expects stock info
    tickers_to_rate = []
    for basket, tickers in PORTFOLIO.items():
        if basket != "Core ETFs":
            tickers_to_rate.extend(tickers)
            
    print(f"Rating {len(tickers_to_rate)} holdings...")
    
    results = []
    for ticker in tickers_to_rate:
        try:
            print(f"Processing {ticker}...")
            data = rater.rate_stock(ticker)
            if data and "error" not in data:
                results.append(data)
        except Exception as e:
            print(f"Error rating {ticker}: {e}")
            
    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    
    with open('portfolio_ratings.json', 'w') as f:
        json.dump({
            "updated": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    
    print("✅ Portfolio ratings saved to portfolio_ratings.json")

if __name__ == "__main__":
    main()

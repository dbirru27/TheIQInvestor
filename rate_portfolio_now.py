import json
from rater import BreakoutRater
from datetime import datetime
import config
from utils.logger import get_logger

logger = get_logger('rate_portfolio')

# Use config for portfolio tickers
PORTFOLIO = {
    "Defense": ["LHX", "LMT", "NOC", "GE"],
    "Grid-to-Chip": ["PWR", "VRT", "GEV"],
    "TopVOO": [t for t in config.PORTFOLIO_TICKERS if t in ["MSFT", "AMZN", "GOOGL", "META", "NVDA", "AMD", "PLTR", "LLY"]],
    "Core ETFs": config.CORE_ETFS + ["GLDM", "IWM"]
}

def main():
    rater = BreakoutRater()
    report = []
    
    # Only rate individual stocks, not ETFs for now as rater expects stock info
    tickers_to_rate = []
    for basket, tickers in PORTFOLIO.items():
        if basket != "Core ETFs":
            tickers_to_rate.extend(tickers)
            
    logger.info(f"Rating {len(tickers_to_rate)} holdings...")
    
    results = []
    for ticker in tickers_to_rate:
        try:
            logger.debug(f"Processing {ticker}...")
            data = rater.rate_stock(ticker)
            if data and "error" not in data:
                results.append(data)
        except Exception as e:
            logger.error(f"Error rating {ticker}: {e}")
            
    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    
    with open('portfolio_ratings.json', 'w') as f:
        json.dump({
            "updated": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    
    logger.info("✅ Portfolio ratings saved to portfolio_ratings.json")
    print("✅ Portfolio ratings saved to portfolio_ratings.json")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate watchlist.json for InvestIQ portfolio holdings
Fetches live data from yfinance + rating scores from all_stocks.json
"""
import json
import yfinance as yf
from datetime import datetime
from config import (
    TRADING_ACCOUNT, CORE_ETFS, 
    GRID_TO_CHIP, DEFENSE_AEROSPACE, AI_SEMIS, BIOTECH
)
from utils.logger import get_logger

logger = get_logger('watchlist')

# Portfolio baskets
BASKETS = {
    "Trading Account": TRADING_ACCOUNT,
    "IRA Core ETFs": CORE_ETFS,
    "Grid-to-Chip": GRID_TO_CHIP,
    "Defense & Aerospace": DEFENSE_AEROSPACE,
    "AI Semis": AI_SEMIS,
    "Biotech": BIOTECH
}

def load_ratings():
    """Load rating scores from all_stocks.json"""
    try:
        with open('all_stocks.json', 'r') as f:
            data = json.load(f)
            ratings = {}
            for stock in data.get('stocks', []):
                ticker = stock.get('ticker')
                if ticker:
                    ratings[ticker] = {
                        'score': stock.get('score', 0),
                        'grade': stock.get('grade', 'N/A')
                    }
            logger.info(f"Loaded ratings for {len(ratings)} stocks")
            return ratings
    except Exception as e:
        logger.warning(f"Could not load all_stocks.json: {e}")
        return {}

def fetch_stock_data(ticker, ratings):
    """Fetch fundamental data for a single ticker"""
    try:
        logger.info(f"Fetching data for {ticker}...")
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get rating from all_stocks.json
        rating = ratings.get(ticker, {'score': 0, 'grade': 'N/A'})
        
        # Calculate daily price change
        current_price = info.get('regularMarketPrice') or info.get('currentPrice')
        previous_close = info.get('previousClose')
        daily_change = None
        if current_price and previous_close and previous_close > 0:
            daily_change = ((current_price - previous_close) / previous_close) * 100
        
        # Get PE ratios (may be None for ETFs)
        trailing_pe = info.get('trailingPE')
        forward_pe = info.get('forwardPE')
        
        # Growth rates (convert from decimal to percentage)
        revenue_growth = info.get('revenueGrowth')
        if revenue_growth is not None:
            revenue_growth = revenue_growth * 100
        
        earnings_growth = info.get('earningsGrowth')
        if earnings_growth is not None:
            earnings_growth = earnings_growth * 100
        
        # PEG ratio
        peg_ratio = info.get('pegRatio') or info.get('trailingPegRatio')
        
        return {
            "ticker": ticker,
            "name": info.get('longName') or info.get('shortName') or ticker,
            "trailing_pe": round(trailing_pe, 2) if trailing_pe else None,
            "forward_pe": round(forward_pe, 2) if forward_pe else None,
            "revenue_growth": round(revenue_growth, 2) if revenue_growth else None,
            "earnings_growth": round(earnings_growth, 2) if earnings_growth else None,
            "peg_ratio": round(peg_ratio, 2) if peg_ratio else None,
            "score": rating['score'],
            "grade": rating['grade'],
            "daily_change": round(daily_change, 2) if daily_change else None
        }
    except Exception as e:
        logger.error(f"Failed to fetch {ticker}: {e}")
        return {
            "ticker": ticker,
            "name": ticker,
            "trailing_pe": None,
            "forward_pe": None,
            "revenue_growth": None,
            "earnings_growth": None,
            "peg_ratio": None,
            "score": 0,
            "grade": "N/A",
            "daily_change": None
        }

def generate_watchlist():
    """Generate complete watchlist.json"""
    logger.info("Starting watchlist generation...")
    
    # Load existing ratings
    ratings = load_ratings()
    
    # Process each basket
    watchlist_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M EST"),
        "baskets": {},
        "all": []
    }
    
    for basket_name, tickers in BASKETS.items():
        logger.info(f"Processing basket: {basket_name} ({len(tickers)} holdings)")
        basket_stocks = []
        
        for ticker in tickers:
            stock_data = fetch_stock_data(ticker, ratings)
            stock_data['basket'] = basket_name
            basket_stocks.append(stock_data)
            watchlist_data['all'].append(stock_data)
        
        watchlist_data['baskets'][basket_name] = basket_stocks
    
    # Write to file
    output_path = 'watchlist.json'
    with open(output_path, 'w') as f:
        json.dump(watchlist_data, f, indent=2)
    
    logger.info(f"✓ Watchlist generated: {output_path}")
    logger.info(f"  Total holdings: {len(watchlist_data['all'])}")
    logger.info(f"  Baskets: {len(watchlist_data['baskets'])}")
    
    return watchlist_data

if __name__ == "__main__":
    result = generate_watchlist()
    print(f"\n✓ Generated watchlist with {len(result['all'])} holdings")
    print(f"Last updated: {result['last_updated']}")

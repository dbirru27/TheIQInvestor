#!/usr/bin/env python3
"""
Generate watchlist.json for InvestIQ portfolio holdings.
Reads all scores and fundamentals from all_stocks.json (database).
Only fetches live price for daily % change via yfinance bulk download.
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

BASKETS = {
    "Trading Account": TRADING_ACCOUNT,
    "IRA Core ETFs": CORE_ETFS,
    "Grid-to-Chip": GRID_TO_CHIP,
    "Defense & Aerospace": DEFENSE_AEROSPACE,
    "AI Semis": AI_SEMIS,
    "Biotech": BIOTECH
}

# Position sizes: account_weight * position_weight = portfolio_weight
# Account weights as % of total portfolio
ACCOUNT_WEIGHTS = {
    "Trading Account": 0.26,
    "IRA Core ETFs": 0.66,      # Part of Traditional IRA
    "Grid-to-Chip": 0.66,       # Part of Traditional IRA
    "Defense & Aerospace": 0.035 + 0.66,  # Roth (3.5%) + some IRA
    "AI Semis": 0.66,           # Part of Traditional IRA
    "Biotech": 0.66,            # Part of Traditional IRA
}

# Position size within each account/basket (% of that basket)
POSITION_SIZES = {
    # Trading Account (26% of portfolio)
    "VGT": 40.13, "VUG": 17.22, "GOOGL": 19.88, "GOOG": 19.87,
    # Roth Account (3.5% of portfolio) — Defense & Aerospace Roth portion
    "LMT": 35.16, "NOC": 33.33, "LHX": 31.51,
    # IRA positions — to be filled in later by Dan
}


def load_stock_db():
    """Load all stock data from all_stocks.json"""
    try:
        with open('all_stocks.json', 'r') as f:
            data = json.load(f)
            stocks = data.get('stocks', {})
            if isinstance(stocks, dict):
                logger.info(f"Loaded {len(stocks)} stocks from database")
                return stocks
            # Handle list format (convert to dict)
            return {s['ticker']: s for s in stocks if 'ticker' in s}
    except Exception as e:
        logger.warning(f"Could not load all_stocks.json: {e}")
        return {}


def fetch_live_prices(tickers):
    """Fetch live prices + names using yfinance Tickers"""
    live = {}
    names = {}
    try:
        tickers_obj = yf.Tickers(' '.join(tickers))
        for t in tickers:
            try:
                info = tickers_obj.tickers[t].info
                curr = info.get('regularMarketPrice') or info.get('currentPrice')
                prev = info.get('previousClose')
                names[t] = info.get('longName') or info.get('shortName') or t
                # Capture growth data too
                rev_g = info.get('revenueGrowth')
                earn_g = info.get('earningsGrowth')
                live[t] = live.get(t, {})
                if rev_g is not None:
                    live[t]['revenue_growth'] = round(rev_g * 100, 1)
                if earn_g is not None:
                    live[t]['earnings_growth'] = round(earn_g * 100, 1)
                if curr and prev and prev > 0:
                    live[t]['price'] = round(curr, 2)
                    live[t]['previous_close'] = round(prev, 2)
                    live[t]['daily_change'] = round((curr - prev) / prev * 100, 2)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Price fetch failed: {e}")
    return live, names


def build_stock_entry(ticker, basket_name, db, live_prices, names_cache):
    """Build a watchlist entry from DB + live price data"""
    stock = db.get(ticker, {})
    live = live_prices.get(ticker, {})
    
    # Get name: DB first, then names_cache (from yf.Tickers)
    name = stock.get('name') or names_cache.get(ticker, ticker)

    # Growth data from bulk fetch
    revenue_growth = live.get('revenue_growth')
    earnings_growth = live.get('earnings_growth')

    return {
        "ticker": ticker,
        "name": name,
        "sector": stock.get('sector', ''),
        "industry": stock.get('industry', ''),
        "price": live.get('price') or stock.get('current_price'),
        "previous_close": live.get('previous_close'),
        "daily_change": live.get('daily_change'),
        "trailing_pe": round(stock['trailing_pe'], 2) if stock.get('trailing_pe') else None,
        "forward_pe": round(stock['forward_pe'], 2) if stock.get('forward_pe') else None,
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
        "peg_ratio": round(stock['peg_ratio'], 2) if stock.get('peg_ratio') else None,
        "market_cap": stock.get('market_cap'),
        # Rater v5.0 scores (from DB)
        "score": stock.get('score', 0),
        "grade": stock.get('grade', 'N/A'),
        "technical_score": stock.get('technical_score', 0),
        "growth_score": stock.get('growth_score', 0),
        "quality_score": stock.get('quality_score', 0),
        "context_score": stock.get('context_score', 0),
        "moonshot_score": stock.get('moonshot_score', 0),
        # Rotation Catcher scores (from DB)
        "rotation_score": stock.get('rotation_score', 0),
        "rotation_signal": stock.get('rotation_signal', 'N/A'),
        # Analyst data
        "recommendation": stock.get('recommendation'),
        "target_mean": round(stock['target_mean'], 2) if stock.get('target_mean') else None,
        "analyst_count": stock.get('analyst_count', 0),
        # Basket & Position Size
        "basket": basket_name,
        "position_size": POSITION_SIZES.get(ticker),
    }


def generate_watchlist():
    """Generate watchlist.json from database + live prices"""
    logger.info("Starting watchlist generation...")

    # Load DB
    db = load_stock_db()

    # Collect all tickers
    all_tickers = []
    for tickers in BASKETS.values():
        all_tickers.extend(tickers)
    all_tickers = list(set(all_tickers))

    # Bulk fetch live prices (single API call)
    logger.info(f"Fetching live prices for {len(all_tickers)} tickers...")
    live_prices, names_cache = fetch_live_prices(all_tickers)
    logger.info(f"Got live prices for {len(live_prices)} tickers, {len(names_cache)} names")

    # Build watchlist
    watchlist_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M EST"),
        "baskets": {},
        "all": []
    }

    for basket_name, tickers in BASKETS.items():
        logger.info(f"Processing basket: {basket_name} ({len(tickers)} holdings)")
        basket_stocks = []

        for ticker in tickers:
            entry = build_stock_entry(ticker, basket_name, db, live_prices, names_cache)
            basket_stocks.append(entry)
            watchlist_data['all'].append(entry)

        watchlist_data['baskets'][basket_name] = basket_stocks

    # Write
    with open('watchlist.json', 'w') as f:
        json.dump(watchlist_data, f, indent=2)

    logger.info(f"✓ Watchlist generated: watchlist.json")
    logger.info(f"  Total holdings: {len(watchlist_data['all'])}")
    logger.info(f"  Baskets: {len(watchlist_data['baskets'])}")

    return watchlist_data


if __name__ == "__main__":
    result = generate_watchlist()
    print(f"\n✓ Generated watchlist with {len(result['all'])} holdings")
    print(f"Last updated: {result['last_updated']}")

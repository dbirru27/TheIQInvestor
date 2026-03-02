#!/usr/bin/env python3
"""
Shared Configuration for InvestIQ Workspace
Centralizes paths, emails, tickers, and logging setup
"""
import os
import json

# Email Configuration
EMAIL_RECIPIENT = os.getenv("REPORT_EMAIL", "dbirru@gmail.com")
WORK_EMAIL = "***REMOVED***"
EMAIL_CONFIG_PATH = os.getenv("EMAIL_CONFIG_PATH", os.path.expanduser("~/.openclaw/workspace/.email_config.ini"))

# Directory Structure
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(WORKSPACE_DIR, 'data', 'market_data.db')
LOG_DIR = os.path.join(WORKSPACE_DIR, 'logs')

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# --- Portfolio (now loads from portfolio.json) ---

def load_portfolio():
    """Load portfolio from portfolio.json - single source of truth"""
    portfolio_path = os.path.join(WORKSPACE_DIR, 'data', 'portfolio.json')
    try:
        with open(portfolio_path, 'r') as f:
            data = json.load(f)
            baskets = data.get('baskets', {})
            
            # Build basket lists from JSON
            result = {}
            for basket_name, basket_data in baskets.items():
                result[basket_name] = list(basket_data.get('tickers', {}).keys())
            
            return result
    except FileNotFoundError:
        # Fallback to hardcoded values if portfolio.json doesn't exist yet
        return {
            'Trading Account': ['VGT', 'VUG', 'GOOGL'],
            'Defense & Aerospace': ['LMT', 'NOC', 'LHX', 'HWM', 'HEI', 'RTX', 'HII', 'UFO', 'EUAD', 'SHLD'],
            'Biotech': ['XBI', 'LLY', 'ALNY', 'HALO'],
            'IRA Core ETFs': ['COPX', 'GLD', 'XLI', 'VOO', 'DXJ', 'INDA', 'SIL'],
            'Grid-to-Chip': ['NLR', 'VRT', 'CEG', 'PWR', 'GEV', 'ETN', 'GRID', 'NVT', 'FIX', 'CCJ', 'APH', 'HUBB'],
            'AI Semis': ['MU', 'AVGO', 'TSM', 'ANET', 'WDC', 'MRVL', 'ASML', 'AMD', 'ALAB', 'STX']
        }

# Load baskets from portfolio.json
_BASKETS = load_portfolio()

# Trading Account (~26%)
TRADING_ACCOUNT = _BASKETS.get('Trading Account', [])

# Defense & Aerospace (IRA + Roth)
DEFENSE_AEROSPACE = _BASKETS.get('Defense & Aerospace', [])

# Biotech (IRA)
BIOTECH = _BASKETS.get('Biotech', [])

# IRA (~66%) - Core ETFs
CORE_ETFS = _BASKETS.get('IRA Core ETFs', [])

# IRA - Grid-to-Chip
GRID_TO_CHIP = _BASKETS.get('Grid-to-Chip', [])

# IRA - AI Semis
AI_SEMIS = _BASKETS.get('AI Semis', [])

# All individual stocks (non-ETF) - compute from baskets
PORTFOLIO_TICKERS = DEFENSE_AEROSPACE + GRID_TO_CHIP + AI_SEMIS + BIOTECH + [t for t in TRADING_ACCOUNT if t not in ['VGT', 'VUG']]

# All holdings (everything)
ALL_HOLDINGS = TRADING_ACCOUNT + CORE_ETFS + GRID_TO_CHIP + DEFENSE_AEROSPACE + AI_SEMIS + BIOTECH

# Sector ETFs Mapping
SECTOR_ETFS = {
    'Technology': 'XLK',
    'Communication Services': 'XLC',
    'Consumer Cyclical': 'XLY',
    'Healthcare': 'XLV',
    'Financial Services': 'XLF',
    'Industrials': 'XLI',
    'Basic Materials': 'XLB',
    'Energy': 'XLE',
    'Utilities': 'XLU',
    'Real Estate': 'XLRE',
    'Semiconductors': 'SMH',
    'Biotech': 'XBI',
    'Software': 'IGV'
}

# Strong Sectors (updated manually based on market conditions)
STRONG_SECTORS = ['Technology', 'Industrials', 'Healthcare']

# Market Indices
MARKET_INDICES = ['SPY', 'QQQ', 'IWM', 'DIA']

# Volatility & Commodities
VOLATILITY_TICKERS = ['VIXY', 'VIX']
COMMODITY_TICKERS = ['GLD', 'SLV', 'DXY', 'BTC-USD', 'CL=F']  # Gold, Silver, Dollar, Bitcoin, Oil

if __name__ == "__main__":
    print("InvestIQ Configuration")
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"Database: {DB_PATH}")
    print(f"Logs: {LOG_DIR}")
    print(f"Email: {EMAIL_RECIPIENT}")
    print(f"Core ETFs: {len(CORE_ETFS)}")
    print(f"Portfolio: {len(PORTFOLIO_TICKERS)}")
    print(f"Sectors: {len(SECTOR_ETFS)}")

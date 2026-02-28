#!/usr/bin/env python3
"""
Shared Configuration for InvestIQ Workspace
Centralizes paths, emails, tickers, and logging setup
"""
import os

# Email Configuration
EMAIL_RECIPIENT = os.getenv("REPORT_EMAIL", "dbirru@gmail.com")
WORK_EMAIL = "***REMOVED***"
EMAIL_CONFIG_PATH = os.getenv("EMAIL_CONFIG_PATH", os.path.expanduser("~/.openclaw/workspace/.email_config.ini"))

# Directory Structure
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(WORKSPACE_DIR, 'market_data.db')
LOG_DIR = os.path.join(WORKSPACE_DIR, 'logs')

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Core ETF Holdings
CORE_ETFS = ['COPX', 'GLD', 'GLDM', 'NLR', 'VOO', 'XLI', 'ITA']

# Portfolio Tickers
PORTFOLIO_TICKERS = [
    'LMT', 'NOC', 'GE', 'PWR',           # Defense & Grid-to-Chip
    'MSFT', 'AMZN', 'GOOGL', 'META',     # Mag 7
    'NVDA', 'AMD', 'PLTR',               # AI/Semis
    'LLY'                                 # Pharma
]

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

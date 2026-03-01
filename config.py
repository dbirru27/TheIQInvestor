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

# --- Portfolio (source: MY_PORTFOLIO.md, updated 2026-02-28) ---

# Trading Account (~26%)
TRADING_ACCOUNT = ['VGT', 'VUG', 'GOOGL']

# Defense & Aerospace (IRA + Roth)
DEFENSE_AEROSPACE = ['LMT', 'NOC', 'LHX', 'HWM', 'HEI', 'RTX', 'HII', 'UFO', 'EUAD', 'SHLD']

# Biotech (IRA)
BIOTECH = ['XBI', 'LLY', 'ALNY', 'HALO']

# IRA (~66%) - Core ETFs
CORE_ETFS = ['COPX', 'GLD', 'XLI', 'VOO', 'DXJ', 'INDA', 'SIL', 'EEM']

# IRA - Grid-to-Chip
GRID_TO_CHIP = ['NLR', 'VRT', 'CEG', 'PWR', 'GEV', 'ETN', 'GRID', 'NVT', 'FIX', 'CCJ', 'APH', 'HUBB']

# IRA - AI Semis
AI_SEMIS = ['MU', 'AVGO', 'TSM', 'ANET', 'WDC', 'MRVL', 'ASML', 'AMD', 'ALAB', 'STX']

# All individual stocks (non-ETF)
PORTFOLIO_TICKERS = DEFENSE_AEROSPACE + GRID_TO_CHIP + AI_SEMIS + BIOTECH + ['GOOGL', 'GOOG']

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

#!/usr/bin/env python3
"""
Market Timing System - Data Downloader
Downloads all required market data from various sources.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
import os
import sys
import zipfile
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = '/Users/dansmacmini/.openclaw/workspace/market_timing/data'
os.chdir(DATA_DIR)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def verify_file(filename):
    """Print row count and date range for a CSV file."""
    if os.path.exists(filename):
        df = pd.read_csv(filename)
        if 'date' in df.columns:
            dates = pd.to_datetime(df['date'], errors='coerce').dropna()
            log(f"  ✅ {filename}: {len(df)} rows, {dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}")
        else:
            log(f"  ✅ {filename}: {len(df)} rows")
        return True
    else:
        log(f"  ❌ {filename}: NOT FOUND")
        return False

def fetch_fred(series_id):
    """Fetch a FRED series as a DataFrame."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ['date', series_id.lower()]
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df = df[df['date'] >= '1986-01-01']
    df = df.set_index('date')
    df = df.replace('.', np.nan)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

# ============================================================
# SECTION 1: S&P 500 + SPY Daily OHLCV
# ============================================================
def download_sp500_spy():
    log("=== FILE 1: S&P 500 + SPY Daily OHLCV ===")
    
    gspc = yf.download("^GSPC", start="1986-01-01", end="2026-03-18", auto_adjust=False)
    spy = yf.download("SPY", start="1993-01-01", end="2026-03-18", auto_adjust=False)
    
    # Handle potential MultiIndex columns
    if isinstance(gspc.columns, pd.MultiIndex):
        gspc.columns = gspc.columns.get_level_values(0)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    
    # S&P 500 combined
    df = gspc[['Open','High','Low','Close','Volume']].copy()
    df.columns = ['open','high','low','close','volume']
    df['spy_volume'] = spy['Volume'].reindex(df.index)
    df.index.name = 'date'
    df.index = df.index.strftime('%Y-%m-%d')
    df.to_csv('sp500_daily_ohlcv.csv', na_rep='')
    verify_file('sp500_daily_ohlcv.csv')
    
    # SPY separate
    spy_df = spy[['Open','High','Low','Close','Volume']].copy()
    spy_df.columns = ['open','high','low','close','volume']
    spy_df.index.name = 'date'
    spy_df.index = spy_df.index.strftime('%Y-%m-%d')
    spy_df.to_csv('spy_daily_ohlcv.csv', na_rep='')
    verify_file('spy_daily_ohlcv.csv')

# ============================================================
# SECTION 2: VIX Daily
# ============================================================
def download_vix():
    log("=== FILE 2: VIX Daily ===")
    vix = yf.download("^VIX", start="1990-01-01", end="2026-03-18", auto_adjust=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)
    
    df = vix[['Open','High','Low','Close']].copy()
    df.columns = ['vix_open','vix_high','vix_low','vix_close']
    df.index.name = 'date'
    df.index = df.index.strftime('%Y-%m-%d')
    df.to_csv('vix_daily.csv', na_rep='')
    verify_file('vix_daily.csv')

# ============================================================
# SECTION 3: VIX Term Structure
# ============================================================
def download_vix_term():
    log("=== FILE 3: VIX Term Structure ===")
    data = yf.download(["^VIX", "^VIX3M"], start="2007-01-01", end="2026-03-18", auto_adjust=False)
    
    if isinstance(data.columns, pd.MultiIndex):
        vix_close = data[('Close', '^VIX')]
        vix3m_close = data[('Close', '^VIX3M')]
    else:
        # Fallback: download separately
        vix = yf.download("^VIX", start="2007-01-01", end="2026-03-18", auto_adjust=False)
        vix3m = yf.download("^VIX3M", start="2007-01-01", end="2026-03-18", auto_adjust=False)
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = vix.columns.get_level_values(0)
        if isinstance(vix3m.columns, pd.MultiIndex):
            vix3m.columns = vix3m.columns.get_level_values(0)
        vix_close = vix['Close']
        vix3m_close = vix3m['Close']
    
    df = pd.DataFrame({
        'vix_spot': vix_close,
        'vix_3m': vix3m_close
    })
    df = df.dropna(subset=['vix_spot'])
    df['contango_slope'] = (df['vix_3m'] - df['vix_spot']) / df['vix_spot']
    df.index.name = 'date'
    df.index = df.index.strftime('%Y-%m-%d')
    df.to_csv('vix_term_structure.csv', na_rep='')
    verify_file('vix_term_structure.csv')

# ============================================================
# SECTION 4: Sector ETFs Daily
# ============================================================
def download_sector_etfs():
    log("=== FILE 4: Sector ETFs Daily ===")
    sector_map = {
        'XLF': 'Financials', 'XLK': 'Technology', 'XLE': 'Energy',
        'XLV': 'Healthcare', 'XLI': 'Industrials', 'XLP': 'Staples',
        'XLY': 'Discretionary', 'XLU': 'Utilities', 'XLRE': 'Real Estate',
        'XLC': 'Communications', 'XLB': 'Materials'
    }
    
    all_rows = []
    for ticker, sector_name in sector_map.items():
        log(f"  Downloading {ticker}...")
        data = yf.download(ticker, start="1998-01-01", end="2026-03-18", auto_adjust=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if len(data) == 0:
            log(f"  ⚠️ No data for {ticker}")
            continue
        
        temp = data[['Open','High','Low','Close','Volume']].copy()
        temp.columns = ['open','high','low','close','volume']
        temp['ticker'] = ticker
        temp['sector_name'] = sector_name
        temp.index.name = 'date'
        temp = temp.reset_index()
        temp['date'] = temp['date'].dt.strftime('%Y-%m-%d')
        all_rows.append(temp[['date','ticker','sector_name','open','high','low','close','volume']])
    
    df = pd.concat(all_rows, ignore_index=True)
    df.to_csv('sector_etfs_daily.csv', index=False, na_rep='')
    verify_file('sector_etfs_daily.csv')

# ============================================================
# SECTION 5: Intermarket Daily
# ============================================================
def download_intermarket():
    log("=== FILE 5: Intermarket Daily ===")
    name_map = {
        'GLD': 'Gold ETF', 'SLV': 'Silver ETF', 'USO': 'Oil ETF',
        'CPER': 'Copper ETF', 'SMH': 'Semiconductors', 'IYT': 'Transports',
        'KRE': 'Regional Banks', 'KBE': 'Bank ETF', 'EEM': 'Emerging Markets',
        'RSP': 'SP500 Equal Weight', 'IWM': 'Russell 2000',
        'QQQ': 'Nasdaq 100', 'BTC-USD': 'Bitcoin'
    }
    
    all_rows = []
    for ticker, name in name_map.items():
        log(f"  Downloading {ticker}...")
        data = yf.download(ticker, start="1986-01-01", end="2026-03-18", auto_adjust=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if len(data) == 0:
            log(f"  ⚠️ No data for {ticker}")
            continue
        
        temp = data[['Open','High','Low','Close','Volume']].copy()
        temp.columns = ['open','high','low','close','volume']
        temp['ticker'] = ticker
        temp['name'] = name
        temp.index.name = 'date'
        temp = temp.reset_index()
        temp['date'] = temp['date'].dt.strftime('%Y-%m-%d')
        all_rows.append(temp[['date','ticker','name','open','high','low','close','volume']])
    
    df = pd.concat(all_rows, ignore_index=True)
    df.to_csv('intermarket_daily.csv', index=False, na_rep='')
    verify_file('intermarket_daily.csv')

# ============================================================
# SECTION 6: Fixed Income ETFs Daily
# ============================================================
def download_fixed_income():
    log("=== FILE 6: Fixed Income ETFs Daily ===")
    name_map = {
        'TLT': '20+ Year Treasury', 'IEF': '7-10 Year Treasury',
        'SHY': '1-3 Year Treasury', 'LQD': 'Investment Grade Corp',
        'HYG': 'High Yield Corp', 'JNK': 'High Yield Corp 2',
        'AGG': 'US Aggregate Bond'
    }
    
    all_rows = []
    for ticker, name in name_map.items():
        log(f"  Downloading {ticker}...")
        data = yf.download(ticker, start="1986-01-01", end="2026-03-18", auto_adjust=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if len(data) == 0:
            log(f"  ⚠️ No data for {ticker}")
            continue
        
        temp = data[['Open','High','Low','Close','Volume']].copy()
        temp.columns = ['open','high','low','close','volume']
        temp['ticker'] = ticker
        temp['name'] = name
        temp.index.name = 'date'
        temp = temp.reset_index()
        temp['date'] = temp['date'].dt.strftime('%Y-%m-%d')
        all_rows.append(temp[['date','ticker','name','open','high','low','close','volume']])
    
    df = pd.concat(all_rows, ignore_index=True)
    df.to_csv('fixed_income_etfs_daily.csv', index=False, na_rep='')
    verify_file('fixed_income_etfs_daily.csv')

# ============================================================
# SECTION 7: Yield Curve Daily (FRED)
# ============================================================
def download_yield_curve():
    log("=== FILE 7: Yield Curve Daily ===")
    series_map = {
        'DGS1MO': 'treasury_1m', 'DGS3MO': 'treasury_3m',
        'DGS6MO': 'treasury_6m', 'DGS1': 'treasury_1y',
        'DGS2': 'treasury_2y', 'DGS5': 'treasury_5y',
        'DGS10': 'treasury_10y', 'DGS30': 'treasury_30y',
        'T10Y2Y': 'spread_10y_2y', 'T10Y3M': 'spread_10y_3m'
    }
    
    dfs = []
    for series_id, col_name in series_map.items():
        log(f"  Fetching FRED {series_id}...")
        try:
            df = fetch_fred(series_id)
            df.columns = [col_name]
            dfs.append(df)
            time.sleep(0.5)
        except Exception as e:
            log(f"  ⚠️ Failed {series_id}: {e}")
    
    if dfs:
        merged = dfs[0]
        for df in dfs[1:]:
            merged = merged.join(df, how='outer')
        merged = merged.sort_index()
        merged = merged.ffill()
        merged.index.name = 'date'
        merged.index = merged.index.strftime('%Y-%m-%d')
        merged.to_csv('yield_curve_daily.csv', na_rep='')
        verify_file('yield_curve_daily.csv')

# ============================================================
# SECTION 8: Credit Spreads Daily (FRED)
# ============================================================
def download_credit_spreads():
    log("=== FILE 8: Credit Spreads Daily ===")
    series_map = {
        'BAMLH0A0HYM2': 'hy_oas', 'BAMLC0A4CBBB': 'bbb_oas',
        'BAMLC0A1CAAA': 'aaa_oas', 'TEDRATE': 'ted_spread',
        'T10YIE': 'breakeven_10y'
    }
    
    dfs = []
    for series_id, col_name in series_map.items():
        log(f"  Fetching FRED {series_id}...")
        try:
            df = fetch_fred(series_id)
            df.columns = [col_name]
            dfs.append(df)
            time.sleep(0.5)
        except Exception as e:
            log(f"  ⚠️ Failed {series_id}: {e}")
    
    if dfs:
        merged = dfs[0]
        for df in dfs[1:]:
            merged = merged.join(df, how='outer')
        merged = merged[merged.index >= '1996-12-31']
        merged = merged.sort_index()
        merged = merged.ffill()
        merged.index.name = 'date'
        merged.index = merged.index.strftime('%Y-%m-%d')
        merged.to_csv('credit_spreads_daily.csv', na_rep='')
        verify_file('credit_spreads_daily.csv')

# ============================================================
# SECTION 9: Macro Indicators (FRED)
# ============================================================
def download_macro():
    log("=== FILE 9: Macro Indicators ===")
    series_map = {
        'WALCL': 'fed_balance_sheet', 'M2SL': 'm2_money_supply',
        'RRPONTSYD': 'reverse_repo', 'UNRATE': 'unemployment_rate',
        'ICSA': 'initial_claims', 'CCSA': 'continuing_claims',
        'CPIAUCSL': 'cpi_all_urban', 'CPILFESL': 'cpi_core',
        'PCEPI': 'pce_price_index', 'INDPRO': 'industrial_production',
        'RSAFS': 'retail_sales', 'NFCI': 'nfci',
        'STLFSI2': 'st_louis_stress', 'FEDFUNDS': 'fed_funds_rate',
        'DFF': 'fed_funds_effective'
    }
    
    dfs = []
    for series_id, col_name in series_map.items():
        log(f"  Fetching FRED {series_id}...")
        try:
            df = fetch_fred(series_id)
            df.columns = [col_name]
            dfs.append(df)
            time.sleep(0.5)
        except Exception as e:
            log(f"  ⚠️ Failed {series_id}: {e}")
    
    if dfs:
        merged = dfs[0]
        for df in dfs[1:]:
            merged = merged.join(df, how='outer')
        merged = merged.sort_index()
        merged = merged.ffill()
        merged.index.name = 'date'
        merged.index = merged.index.strftime('%Y-%m-%d')
        merged.to_csv('macro_indicators.csv', na_rep='')
        verify_file('macro_indicators.csv')

# ============================================================
# SECTION 10: AAII Sentiment
# ============================================================
def download_aaii():
    log("=== FILE 10: AAII Sentiment ===")
    
    # Approach 1: Direct AAII Excel
    try:
        log("  Trying AAII direct Excel download...")
        url = "https://www.aaii.com/files/surveys/sentiment.xls"
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200 and len(r.content) > 1000:
            df = pd.read_excel(io.BytesIO(r.content), sheet_name=0)
            # Find the right columns - AAII format varies
            # Look for date, bullish, bearish, neutral columns
            log(f"  Excel columns: {list(df.columns)}")
            # Try to identify columns
            date_col = None
            for c in df.columns:
                if 'date' in str(c).lower():
                    date_col = c
                    break
            if date_col is None:
                date_col = df.columns[0]
            
            bull_col = bear_col = neut_col = None
            for c in df.columns:
                cl = str(c).lower()
                if 'bull' in cl:
                    bull_col = c
                elif 'bear' in cl:
                    bear_col = c
                elif 'neut' in cl:
                    neut_col = c
            
            if bull_col and bear_col and neut_col:
                result = pd.DataFrame({
                    'date': pd.to_datetime(df[date_col], errors='coerce'),
                    'bullish': pd.to_numeric(df[bull_col], errors='coerce'),
                    'bearish': pd.to_numeric(df[bear_col], errors='coerce'),
                    'neutral': pd.to_numeric(df[neut_col], errors='coerce'),
                })
                result = result.dropna(subset=['date'])
                # Convert percentages to decimals if needed
                if result['bullish'].max() > 1:
                    result['bullish'] = result['bullish'] / 100
                    result['bearish'] = result['bearish'] / 100
                    result['neutral'] = result['neutral'] / 100
                result['date'] = result['date'].dt.strftime('%Y-%m-%d')
                result.to_csv('aaii_sentiment.csv', index=False, na_rep='')
                verify_file('aaii_sentiment.csv')
                return
        log(f"  AAII direct failed (status={r.status_code})")
    except Exception as e:
        log(f"  AAII direct failed: {e}")
    
    # Approach 2: Nasdaq Data Link
    try:
        log("  Trying Nasdaq Data Link...")
        url = "https://data.nasdaq.com/api/v3/datasets/AAII/AAII_SENTIMENT.csv"
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200 and len(r.content) > 500:
            df = pd.read_csv(io.StringIO(r.text))
            log(f"  Nasdaq columns: {list(df.columns)}")
            result = pd.DataFrame()
            result['date'] = pd.to_datetime(df.iloc[:,0], errors='coerce')
            # Find bullish/bearish/neutral
            for i, c in enumerate(df.columns):
                cl = str(c).lower()
                if 'bull' in cl:
                    result['bullish'] = pd.to_numeric(df[c], errors='coerce')
                elif 'bear' in cl:
                    result['bearish'] = pd.to_numeric(df[c], errors='coerce')
                elif 'neut' in cl:
                    result['neutral'] = pd.to_numeric(df[c], errors='coerce')
            
            result = result.dropna(subset=['date'])
            if result['bullish'].max() > 1:
                result['bullish'] = result['bullish'] / 100
                result['bearish'] = result['bearish'] / 100
                result['neutral'] = result['neutral'] / 100
            result['date'] = result['date'].dt.strftime('%Y-%m-%d')
            result.to_csv('aaii_sentiment.csv', index=False, na_rep='')
            verify_file('aaii_sentiment.csv')
            return
        log(f"  Nasdaq Data Link failed (status={r.status_code})")
    except Exception as e:
        log(f"  Nasdaq Data Link failed: {e}")
    
    log("  ❌ AAII Sentiment: All approaches failed")

# ============================================================
# SECTION 11: Put/Call Ratio
# ============================================================
def download_put_call():
    log("=== FILE 11: Put/Call Ratio ===")
    
    urls_to_try = [
        "https://cdn.cboe.com/api/global/us_options/market_statistics/daily/?output=csv",
        "https://cdn.cboe.com/data/us/options/market_statistics/historical-options-data/total_pc_ratio.csv",
        "https://www.cboe.com/publish/scheduledtask/mktdata/cboedailymarketstatistics.csv",
        "https://cdn.cboe.com/api/global/us_options_rest_api/market_statistics/historical-options-data/total_pc_ratio.csv",
    ]
    
    for url in urls_to_try:
        try:
            log(f"  Trying {url[:80]}...")
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and len(r.content) > 500:
                df = pd.read_csv(io.StringIO(r.text))
                log(f"  Got columns: {list(df.columns)[:10]}")
                # Process based on what we get
                if len(df) > 100:
                    df.to_csv('put_call_ratio_raw.csv', index=False)
                    log(f"  Saved raw data: {len(df)} rows")
                    # Try to parse into standard format
                    # ... will need to examine columns
                    break
        except Exception as e:
            log(f"  Failed: {e}")
    
    # If CBOE fails, try to use VIX/options data as proxy
    if not os.path.exists('put_call_ratio.csv'):
        log("  ⚠️ CBOE direct download failed, creating placeholder note")
        # Create minimal file noting the limitation
        pd.DataFrame(columns=['date','total_put_call','equity_put_call','index_put_call']).to_csv(
            'put_call_ratio.csv', index=False)
        log("  ❌ Put/Call Ratio: Created empty placeholder")

# ============================================================
# SECTION 12: NYSE Breadth Daily
# ============================================================
def download_breadth():
    log("=== FILE 12: NYSE Breadth Daily ===")
    
    # Approach 1: Stooq
    stooq_data = {}
    stooq_map = {
        'adv.us': 'nyse_advances',
        'decl.us': 'nyse_declines',
        'adv.q': 'nasdaq_advances',
        'decl.q': 'nasdaq_declines',
    }
    
    success = False
    for symbol, col_name in stooq_map.items():
        try:
            url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
            log(f"  Trying Stooq {symbol}...")
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and len(r.content) > 200:
                df = pd.read_csv(io.StringIO(r.text))
                log(f"  Got {len(df)} rows for {symbol}, columns: {list(df.columns)}")
                if len(df) > 100:
                    df.columns = [c.lower() for c in df.columns]
                    stooq_data[col_name] = df
                    success = True
            time.sleep(1)
        except Exception as e:
            log(f"  Stooq {symbol} failed: {e}")
    
    if success and stooq_data:
        # Merge stooq data
        merged = None
        for col_name, df in stooq_data.items():
            if 'date' in df.columns:
                temp = df[['date']].copy()
                # Use 'close' column as the value
                if 'close' in df.columns:
                    temp[col_name] = df['close'].values
                elif 'value' in df.columns:
                    temp[col_name] = df['value'].values
                temp['date'] = pd.to_datetime(temp['date'], errors='coerce')
                temp = temp.dropna(subset=['date']).set_index('date')
                if merged is None:
                    merged = temp
                else:
                    merged = merged.join(temp, how='outer')
        
        if merged is not None and len(merged) > 100:
            # Add empty columns for missing data
            for col in ['nyse_unchanged', 'nyse_new_highs', 'nyse_new_lows', 'nasdaq_new_highs', 'nasdaq_new_lows']:
                if col not in merged.columns:
                    merged[col] = np.nan
            merged = merged.sort_index()
            merged.index.name = 'date'
            merged.index = merged.index.strftime('%Y-%m-%d')
            expected_cols = ['nyse_advances','nyse_declines','nyse_unchanged','nyse_new_highs','nyse_new_lows',
                           'nasdaq_advances','nasdaq_declines','nasdaq_new_highs','nasdaq_new_lows']
            for c in expected_cols:
                if c not in merged.columns:
                    merged[c] = np.nan
            merged[expected_cols].to_csv('nyse_breadth_daily.csv', na_rep='')
            verify_file('nyse_breadth_daily.csv')
            return
    
    log("  Stooq approach incomplete, trying Yahoo breadth proxies...")
    
    # Approach 2: Use Yahoo Finance advance/decline tickers
    try:
        # Try Yahoo Finance for advance/decline data
        # ^ADV = NYSE advances, ^DECL = NYSE declines  
        adv = yf.download("^ADV", start="2000-01-01", end="2026-03-18", auto_adjust=False)
        decl = yf.download("^DECL", start="2000-01-01", end="2026-03-18", auto_adjust=False)
        
        if len(adv) > 0 and len(decl) > 0:
            if isinstance(adv.columns, pd.MultiIndex):
                adv.columns = adv.columns.get_level_values(0)
            if isinstance(decl.columns, pd.MultiIndex):
                decl.columns = decl.columns.get_level_values(0)
            
            merged = pd.DataFrame({
                'nyse_advances': adv['Close'],
                'nyse_declines': decl['Close'],
            })
            for col in ['nyse_unchanged', 'nyse_new_highs', 'nyse_new_lows',
                        'nasdaq_advances', 'nasdaq_declines', 'nasdaq_new_highs', 'nasdaq_new_lows']:
                merged[col] = np.nan
            merged.index.name = 'date'
            merged.index = merged.index.strftime('%Y-%m-%d')
            merged.to_csv('nyse_breadth_daily.csv', na_rep='')
            verify_file('nyse_breadth_daily.csv')
            return
    except Exception as e:
        log(f"  Yahoo breadth failed: {e}")
    
    log("  ❌ NYSE Breadth: All approaches failed, creating empty placeholder")
    pd.DataFrame(columns=['date','nyse_advances','nyse_declines','nyse_unchanged',
                          'nyse_new_highs','nyse_new_lows','nasdaq_advances','nasdaq_declines',
                          'nasdaq_new_highs','nasdaq_new_lows']).to_csv('nyse_breadth_daily.csv', index=False)

# ============================================================
# SECTION 13: Insider Trading (Optional)
# ============================================================
def download_insider():
    log("=== FILE 13 (OPTIONAL): Insider Trading ===")
    
    try:
        log("  Trying OpenInsider...")
        # Fetch multiple pages from OpenInsider
        all_data = []
        for page in range(1, 3):
            url = f"http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page={page}"
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                tables = pd.read_html(io.StringIO(r.text))
                for t in tables:
                    if len(t) > 10:
                        all_data.append(t)
                        log(f"  Got table with {len(t)} rows from page {page}")
            time.sleep(2)
        
        if all_data:
            # Process the insider data
            df = pd.concat(all_data, ignore_index=True)
            log(f"  Raw insider data columns: {list(df.columns)[:10]}")
            # Try to aggregate by date
            # Look for filing date or trade date column
            date_col = None
            for c in df.columns:
                if 'filing' in str(c).lower() and 'date' in str(c).lower():
                    date_col = c
                    break
                elif 'trade' in str(c).lower() and 'date' in str(c).lower():
                    date_col = c
                    break
            
            if date_col is None:
                # Just use first column that looks like a date
                for c in df.columns:
                    if 'date' in str(c).lower():
                        date_col = c
                        break
            
            if date_col:
                df['parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
                df = df.dropna(subset=['parsed_date'])
                
                # Try to identify buy/sell from transaction type
                trans_col = None
                for c in df.columns:
                    if 'transaction' in str(c).lower() or 'type' in str(c).lower():
                        trans_col = c
                        break
                
                if trans_col:
                    daily = df.groupby(df['parsed_date'].dt.strftime('%Y-%m-%d')).apply(
                        lambda x: pd.Series({
                            'total_insider_buys': (x[trans_col].str.lower().str.contains('purchase|buy', na=False)).sum(),
                            'total_insider_sells': (x[trans_col].str.lower().str.contains('sale|sell', na=False)).sum(),
                        })
                    ).reset_index()
                    daily.columns = ['date', 'total_insider_buys', 'total_insider_sells']
                    daily['buy_sell_ratio'] = daily['total_insider_buys'] / daily['total_insider_sells'].replace(0, np.nan)
                    daily.to_csv('insider_trading.csv', index=False, na_rep='')
                    verify_file('insider_trading.csv')
                    return
        
        log("  ⚠️ Insider trading: Could not parse data properly")
    except Exception as e:
        log(f"  Insider trading failed: {e}")
    
    log("  ❌ Insider Trading: Failed")

# ============================================================
# SECTION 14: COT Positioning (Optional)
# ============================================================
def download_cot():
    log("=== FILE 14 (OPTIONAL): COT Positioning ===")
    
    all_dfs = []
    for year in range(2006, 2027):
        try:
            url = f"https://www.cftc.gov/files/dea/history/fut_fin_xls_{year}.zip"
            log(f"  Trying CFTC financial futures {year}...")
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                z = zipfile.ZipFile(io.BytesIO(r.content))
                for name in z.namelist():
                    if name.endswith('.xls') or name.endswith('.xlsx'):
                        df = pd.read_excel(z.open(name))
                        all_dfs.append(df)
                        log(f"  Got {len(df)} rows for {year}")
                        break
            time.sleep(0.5)
        except Exception as e:
            log(f"  CFTC {year} failed: {e}")
    
    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
        log(f"  Total COT rows: {len(df)}, columns: {list(df.columns)[:15]}")
        
        # Try to filter for S&P 500, VIX, Treasury
        # CFTC uses "Market_and_Exchange_Names" or similar
        name_col = None
        for c in df.columns:
            if 'market' in str(c).lower() and 'name' in str(c).lower():
                name_col = c
                break
        
        if name_col:
            unique_names = df[name_col].unique()
            log(f"  Unique market names (sample): {list(unique_names[:20])}")
            
            # Filter for relevant contracts
            sp_mask = df[name_col].str.contains('S&P|E-MINI|SP 500', case=False, na=False)
            vix_mask = df[name_col].str.contains('VIX|VOLATILITY', case=False, na=False)
            tsy_mask = df[name_col].str.contains('10-YEAR|10 YR|T-NOTE', case=False, na=False)
            
            # Find date column
            date_col = None
            for c in df.columns:
                if 'report' in str(c).lower() and 'date' in str(c).lower():
                    date_col = c
                    break
                elif 'date' in str(c).lower():
                    date_col = c
            
            if date_col:
                # Find commercial/noncommercial columns
                comm_long = None
                comm_short = None
                noncomm_long = None
                noncomm_short = None
                
                for c in df.columns:
                    cl = str(c).lower()
                    if 'dealer' in cl or 'commercial' in cl:
                        if 'long' in cl and 'spread' not in cl:
                            comm_long = c
                        elif 'short' in cl and 'spread' not in cl:
                            comm_short = c
                    if ('leveraged' in cl or 'noncommercial' in cl or 'non-commercial' in cl or 'asset_mgr' in cl):
                        if 'long' in cl and 'spread' not in cl and noncomm_long is None:
                            noncomm_long = c
                        elif 'short' in cl and 'spread' not in cl and noncomm_short is None:
                            noncomm_short = c
                
                log(f"  Found cols: comm_long={comm_long}, comm_short={comm_short}, noncomm_long={noncomm_long}, noncomm_short={noncomm_short}")
                
                results = []
                for mask, prefix in [(sp_mask, 'sp500'), (vix_mask, 'vix'), (tsy_mask, 'treasury10y')]:
                    subset = df[mask].copy()
                    if len(subset) > 0:
                        temp = pd.DataFrame()
                        temp['date'] = pd.to_datetime(subset[date_col], errors='coerce')
                        if comm_long and comm_short:
                            temp[f'{prefix}_commercial_long'] = pd.to_numeric(subset[comm_long], errors='coerce').values
                            temp[f'{prefix}_commercial_short'] = pd.to_numeric(subset[comm_short], errors='coerce').values
                            temp[f'{prefix}_commercial_net'] = temp[f'{prefix}_commercial_long'] - temp[f'{prefix}_commercial_short']
                        if noncomm_long and noncomm_short:
                            temp[f'{prefix}_noncommercial_long'] = pd.to_numeric(subset[noncomm_long], errors='coerce').values
                            temp[f'{prefix}_noncommercial_short'] = pd.to_numeric(subset[noncomm_short], errors='coerce').values
                            temp[f'{prefix}_noncommercial_net'] = temp[f'{prefix}_noncommercial_long'] - temp[f'{prefix}_noncommercial_short']
                        temp = temp.dropna(subset=['date']).set_index('date')
                        results.append(temp)
                
                if results:
                    merged = results[0]
                    for r in results[1:]:
                        merged = merged.join(r, how='outer')
                    merged = merged.sort_index()
                    merged.index.name = 'date'
                    merged.index = merged.index.strftime('%Y-%m-%d')
                    merged.to_csv('cot_positioning.csv', na_rep='')
                    verify_file('cot_positioning.csv')
                    return
    
    log("  ❌ COT Positioning: Failed or insufficient data")

# ============================================================
# MAIN EXECUTION
# ============================================================
if __name__ == '__main__':
    section = sys.argv[1] if len(sys.argv) > 1 else 'all'
    
    sections = {
        'sp500': download_sp500_spy,
        'vix': download_vix,
        'vix_term': download_vix_term,
        'sectors': download_sector_etfs,
        'intermarket': download_intermarket,
        'fixed_income': download_fixed_income,
        'yield_curve': download_yield_curve,
        'credit': download_credit_spreads,
        'macro': download_macro,
        'aaii': download_aaii,
        'put_call': download_put_call,
        'breadth': download_breadth,
        'insider': download_insider,
        'cot': download_cot,
    }
    
    if section == 'all':
        for name, func in sections.items():
            try:
                func()
            except Exception as e:
                log(f"❌ Section {name} failed with error: {e}")
                import traceback
                traceback.print_exc()
            log("")
    elif section in sections:
        sections[section]()
    else:
        print(f"Unknown section: {section}")
        print(f"Available: {', '.join(sections.keys())}")

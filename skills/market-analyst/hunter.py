import yfinance as yf
import pandas as pd
import sys
import argparse

def get_data(ticker):
    try:
        # Fetch 1 year of data
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty:
            return None
        
        # Flatten MultiIndex columns if present (yfinance v0.2+)
        if isinstance(df.columns, pd.MultiIndex):
            # If columns are (Price, Ticker), keep just Price
            try:
                df.columns = df.columns.get_level_values(0)
            except:
                pass
                
        return df
    except Exception as e:
        return None

def calculate_metrics(df, spy_df):
    if len(df) < 200:
        return None
    
    # Current Price
    current_price = df['Close'].iloc[-1]
    
    # Moving Averages
    sma50 = df['Close'].rolling(window=50).mean().iloc[-1]
    sma200 = df['Close'].rolling(window=200).mean().iloc[-1]
    
    # Relative Volume (10-day)
    try:
        avg_vol_10 = float(df['Volume'].rolling(window=10).mean().iloc[-1])
        current_vol = float(df['Volume'].iloc[-1])
    except:
        # Handle cases where Volume might be multi-dimensional or missing
        return None

    rvol = current_vol / avg_vol_10 if avg_vol_10 > 0 else 0
    
    # 52-Week High/Low
    high_52 = df['Close'].max()
    low_52 = df['Close'].min()
    dist_to_high = (high_52 - current_price) / high_52
    
    # Relative Strength vs SPY (3-month)
    # Calculate performance over last 63 trading days (~3 months)
    start_price = df['Close'].iloc[-63] if len(df) >= 63 else df['Close'].iloc[0]
    perf_stock = (current_price - start_price) / start_price
    
    spy_current = spy_df['Close'].iloc[-1]
    spy_start = spy_df['Close'].iloc[-63] if len(spy_df) >= 63 else spy_df['Close'].iloc[0]
    perf_spy = (spy_current - spy_start) / spy_start
    
    rs_score = perf_stock - perf_spy # Simple alpha check
    
    return {
        'price': round(float(current_price), 2),
        'sma50': round(float(sma50), 2),
        'sma200': round(float(sma200), 2),
        'rvol': round(float(rvol), 2),
        'dist_to_high': round(float(dist_to_high), 4),
        'rs_3m': round(float(rs_score), 4),
        'perf_3m': round(float(perf_stock), 4)
    }

def scan(tickers):
    print(f"Scanning {len(tickers)} tickers...")
    
    # Fetch SPY first for benchmark
    spy_df = get_data("SPY")
    if spy_df is None:
        print("Error: Could not fetch SPY data.")
        return

    results = []
    
    for t in tickers:
        df = get_data(t)
        if df is None:
            continue
            
        metrics = calculate_metrics(df, spy_df)
        if not metrics:
            continue
            
        # --- THE HUNTER FILTERS ---
        # 1. Trend: Price > SMA50 > SMA200 (Stage 2 Uptrend)
        trend_ok = (metrics['price'] > metrics['sma50']) and (metrics['sma50'] > metrics['sma200'])
        
        # 2. Structure: Within 15% of 52-Week High
        structure_ok = metrics['dist_to_high'] < 0.15
        
        # 3. Momentum: Outperforming SPY over 3 months
        rs_ok = metrics['rs_3m'] > 0
        
        # 4. Filter out "penny stocks" or ultra-low price
        price_ok = metrics['price'] > 10

        if trend_ok and structure_ok and rs_ok and price_ok:
            metrics['ticker'] = t
            results.append(metrics)
    
    # Sort by Relative Strength (Strongest first)
    results.sort(key=lambda x: x['rs_3m'], reverse=True)
    
    print("\n--- HUNTER SCAN RESULTS ---")
    if not results:
        print("No candidates found matching strict criteria.")
    else:
        print(f"{'TICKER':<8} {'PRICE':<10} {'RVOL':<8} {'DIST.HIGH':<12} {'RS(3m)':<10}")
        print("-" * 55)
        for r in results:
            print(f"{r['ticker']:<8} ${r['price']:<9} {r['rvol']:<8} {r['dist_to_high']:.1%}        {r['rs_3m']:.1%}")

if __name__ == "__main__":
    # Default list of High Quality Industrials/Defense/Financials/Materials (The "GE Style" Universe)
    # This list can be expanded or passed as args later
    default_universe = [
        # DEFENSE
        "GE", "RTX", "LMT", "NOC", "GD", "HWM", "TDG", "LHX", "TXT",
        # INDUSTRIALS / INFRA
        "CAT", "DE", "URI", "PWR", "ETN", "ITW", "PH", "CMI", "PCAR", "EMR", "TT", "CARR",
        # FINANCIALS
        "JPM", "GS", "KKR", "BX", "V", "MA", "MS", "BLK", "AXP", "C", "WFC", "HIG", "CB",
        # MATERIALS / MINING
        "LIN", "SHW", "MLM", "VMC", "FCX", "SCCO", "NEM", "APD", "ECL", "DD",
        # ENERGY
        "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "MPC", "VLO", "HES", "OXY",
        # TECH-INDUSTRIALS
        "APH", "TEL", "AME", "ROP", "GLW"
    ]
    
    scan(default_universe)

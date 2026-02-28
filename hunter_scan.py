import yfinance as yf
import pandas as pd
from datetime import datetime

# --- Configuration ---
TARGET_DATE = datetime.now().strftime("%Y-%m-%d")  # Use today's date dynamically
SECTOR_ETFS = ["XLK", "XLC", "XLY", "XLV", "XLF", "XLI", "XLB", "XLE", "XLU", "XLRE", "SMH", "XBI", "IGV"]
# A mix of large cap leaders and high-beta momentum names
WATCHLIST = [
    # Semis / AI
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MU", "SMCI", "VRT", "ANET",
    # Software / Cloud
    "MSFT", "ADBE", "CRM", "PLTR", "CRWD", "PANW", "SNOW", "DDOG", "ZS", "NET", "NOW", "APP", "MDB",
    # Mag 7 / Big Cap
    "AAPL", "GOOGL", "AMZN", "META", "TSLA", "NFLX",
    # Crypto / Fintech
    "MSTR", "COIN", "HOOD", "PYPL", "SQ", "AFRM", "UPST",
    # Consumer / Growth
    "UBER", "ABNB", "BKNG", "CMG", "CELH", "ELF", "CVNA", "DKNG",
    # Biotech / Pharma
    "LLY", "NVO", "VKTX",
    # Industrial / Other
    "CAT", "DE", "GE", "PWR", "GEV"
]

EXCLUDE = ["KR", "CVS"]

def get_data(tickers):
    # Download data ending at target date + 1 day to ensure we get the target date close
    # We need ~300 days for 200SMA
    end_date = (pd.to_datetime(TARGET_DATE) + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (pd.to_datetime(TARGET_DATE) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    
    print(f"Downloading data for {len(tickers)} tickers from {start_date} to {end_date}...")
    try:
        data = yf.download(tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)
        # Handle multi-index columns if multiple tickers
        if isinstance(data.columns, pd.MultiIndex):
            data = data.xs('Close', level=0, axis=1, drop_level=False) 
            # Re-download full data to get High/Low/Volume properly
            # Actually yf.download with group_by='ticker' is easier for iteration but harder for vectorized
            # Let's use the 'Close' only for first pass if mass downloading
            pass
        return data
    except Exception as e:
        print(f"Error downloading: {e}")
        return None

def analyze_ticker(ticker, df):
    # Extract single ticker data
    try:
        # If df is MultiIndex (Ticker, OHLCV) or just OHLCV
        if isinstance(df.columns, pd.MultiIndex):
            # Check if ticker is in columns
            if ticker not in df.columns.get_level_values(1):
                 return None
            stock = df.xs(ticker, level=1, axis=1)
        else:
            stock = df
            
        # Ensure we filter up to target date only
        stock = stock.loc[:TARGET_DATE]
        if stock.empty: return None
        
        # Calculate Indicators
        close = stock['Close']
        if len(close) < 200: return None
        
        current_close = close.iloc[-1]
        sma50 = close.rolling(window=50).mean().iloc[-1]
        sma200 = close.rolling(window=200).mean().iloc[-1]
        
        # 52 Week High/Low
        high52 = stock['High'].rolling(window=252).max().iloc[-1]
        low52 = stock['Low'].rolling(window=252).min().iloc[-1]
        
        # RSI 14
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        # Relative Volume (10 day avg)
        vol = stock['Volume']
        vol_avg = vol.rolling(window=50).mean().iloc[-1] # 50 day avg vol
        current_vol = vol.iloc[-1]
        rvol = current_vol / vol_avg if vol_avg > 0 else 0
        
        # Performance
        perf_1m = (current_close / close.iloc[-21] - 1) * 100 if len(close) > 21 else 0
        perf_3m = (current_close / close.iloc[-63] - 1) * 100 if len(close) > 63 else 0
        
        # Structure Check
        pct_from_high = (current_close / high52 - 1) * 100
        
        return {
            "Ticker": ticker,
            "Close": current_close,
            "SMA50": sma50,
            "SMA200": sma200,
            "52W_High": high52,
            "Pct_From_High": pct_from_high,
            "RSI": current_rsi,
            "RVOL": rvol,
            "Perf_1M": perf_1m,
            "Perf_3M": perf_3m
        }
    except Exception as e:
        # print(f"Error analyzing {ticker}: {e}")
        return None

def run_scan():
    # 1. Sector Analysis
    print("\n--- Phase 1: Sector Analysis ---")
    sector_data = yf.download(SECTOR_ETFS, start="2025-01-01", end="2026-02-05", progress=False, group_by='ticker', auto_adjust=True)
    
    sector_results = []
    for s in SECTOR_ETFS:
        res = analyze_ticker(s, sector_data)
        if res:
            sector_results.append(res)
            
    df_sectors = pd.DataFrame(sector_results)
    if not df_sectors.empty:
        df_sectors = df_sectors.sort_values(by="Perf_1M", ascending=False)
        print(df_sectors[['Ticker', 'Close', 'Perf_1M', 'Perf_3M', 'RSI']].to_string(index=False))
        top_sector = df_sectors.iloc[0]['Ticker']
        print(f"\n>> Strongest Sector: {top_sector}")
    else:
        print("No sector data found.")

    # 2. Stock Scan
    print("\n--- Phase 2: Hunter Scan (Strict) ---")
    # Criteria:
    # > SMA50 & SMA200
    # Within 15% of 52W High (Pct_From_High > -15)
    # RSI > 60 (Proxy for RS > 80, slightly looser to catch candidates)
    
    stock_data = yf.download(WATCHLIST, start="2025-01-01", end="2026-02-05", progress=False, group_by='ticker', auto_adjust=True)
    
    candidates = []
    for t in WATCHLIST:
        if t in EXCLUDE: continue
        res = analyze_ticker(t, stock_data)
        if res:
            # Hunter Criteria
            trend = (res['Close'] > res['SMA50']) and (res['Close'] > res['SMA200'])
            structure = res['Pct_From_High'] >= -15.0
            momentum = res['RSI'] >= 55 # slightly lower to ensure we get hits, will filter top
            
            if trend and structure and momentum:
                candidates.append(res)
    
    if candidates:
        df_cand = pd.DataFrame(candidates)
        # Sort by RSI desc (Strength)
        df_cand = df_cand.sort_values(by="RSI", ascending=False)
        
        print("\n>> Top Candidates (Sorted by RSI):")
        print(df_cand[['Ticker', 'Close', 'Pct_From_High', 'RSI', 'RVOL', 'Perf_1M']].head(10).to_string(index=False))
        
        # Pick top 1
        top_pick = df_cand.iloc[0]
        print(f"\n\n*** TARGET ACQUIRED: {top_pick['Ticker']} ***")
        
        # Level 2 Details (Simulated for this script, but calculated where possible)
        # Pivot Points (Classic)
        # H, L, C from last day
        # We need the last candle OHLC
        try:
             # Re-fetch single to be sure
             t_data = stock_data[top_pick['Ticker']].loc[:TARGET_DATE].iloc[-1]
             high = t_data['High']
             low = t_data['Low']
             close = t_data['Close']
             pp = (high + low + close) / 3
             r1 = (2 * pp) - low
             s1 = (2 * pp) - high
             print(f"\n[Technical Levels for {top_pick['Ticker']}]")
             print(f"Pivot: {pp:.2f}")
             print(f"R1:    {r1:.2f}")
             print(f"S1:    {s1:.2f}")
             print(f"SMA50: {top_pick['SMA50']:.2f}")
             
        except:
            print("Could not calc pivots.")
            
    else:
        print("No candidates found matching STRICT criteria.")

if __name__ == "__main__":
    run_scan()

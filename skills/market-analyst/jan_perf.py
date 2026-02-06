import yfinance as yf
import pandas as pd

tickers = ["GE", "RTX", "BA", "HWM", "LMT", "LHX", "NOC", "SPY"]
data = yf.download(tickers, start="2026-01-01", end="2026-01-31", progress=False)

if isinstance(data.columns, pd.MultiIndex):
    close = data['Close']
else:
    close = data

# Calculate % change from start of Jan to end of Jan
jan_perf = ((close.iloc[-1] / close.iloc[0]) - 1) * 100

print("January 2026 Performance:")
print("-" * 30)
for t in tickers:
    print(f"{t:<8} {jan_perf[t]:>8.2f}%")

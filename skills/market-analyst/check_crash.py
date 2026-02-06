import yfinance as yf
import pandas as pd

tickers = ["FCX", "SCCO", "NEM", "XLB", "GLD"]
data = yf.download(tickers, period="5d", interval="1d", progress=False)
if isinstance(data.columns, pd.MultiIndex):
    close = data['Close']
else:
    close = data

print(close.tail(2))
print("\nDaily % Change for Friday (Jan 30):")
pct_change = close.pct_change().iloc[-1] * 100
print(pct_change)

import yfinance as yf
from datetime import datetime

tickers = ["SPY", "QQQ", "IWM", "^VIX", "XLK", "XLF", "XLE", "XLI", "XLV", "XLB", "XLC", "XLY", "XLP", "XLU", "XLRE"]
portfolio = ["LHX", "LMT", "NOC", "GE", "PWR", "VRT", "GEV", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "AMD", "AVGO", "TSLA", "LLY", "COPX", "GLD", "GLDM", "ITA", "NLR", "VOO"]

def get_stats(symbol):
    try:
        t = yf.Ticker(symbol)
        data = t.history(period="2d")
        if data.empty: return None
        curr = data['Close'].iloc[-1]
        prev = data['Close'].iloc[-2]
        change = (curr - prev) / prev * 100
        return {"price": curr, "change": change}
    except: return None

print(f"Market Status at {datetime.now().strftime('%H:%M')}")
print("-" * 30)
for s in tickers + portfolio:
    res = get_stats(s)
    if res:
        print(f"{s:<8} {res['price']:>8.2f} {res['change']:>+7.2f}%")

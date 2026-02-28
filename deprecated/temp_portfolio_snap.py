import yfinance as yf
import pandas as pd

def get_snapshot():
    tickers = ['VRT', 'HWM', 'GE', 'PWR', 'MU', 'NVDA', 'LMT', 'NOC', 'LHX', 'COPX', 'GLD', 'ITA']
    print(f"Fetching data for {len(tickers)} holdings...")
    
    try:
        # Fetch 2 days to get prev close for % change
        data = yf.download(tickers, period="5d", progress=False)['Close']
        
        if len(data) < 2:
            print("Not enough data.")
            return

        current = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Calculate changes
        changes = ((current - prev) / prev) * 100
        
        # Create a sorted list by performance
        perf = []
        for t in tickers:
            try:
                perf.append({
                    'Ticker': t,
                    'Price': current[t],
                    'Change': changes[t]
                })
            except:
                pass
        
        perf.sort(key=lambda x: x['Change'], reverse=True)
        
        print("\nLIVE PORTFOLIO SNAPSHOT 🦉")
        print(f"{'TICKER':<8} {'PRICE':<10} {'CHANGE':<8}")
        print("─" * 30)
        for p in perf:
            icon = "🟢" if p['Change'] > 0 else "🔴"
            if abs(p['Change']) < 0.1: icon = "⚪️"
            print(f"{p['Ticker']:<8} ${p['Price']:<9.2f} {p['Change']:>+5.2f}% {icon}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_snapshot()

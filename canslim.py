import sys
import os
import yfinance as yf
import pandas as pd
from market_data import MarketDB

# CANSLIM Rater
# Based on William O'Neil's methodology

def get_canslim_score(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")
        
        if hist.empty: return 0, "No Data"

        score = 0
        details = []

        # C - Current Earnings (Quarterly EPS Growth > 20%)
        # Note: YFinance often lacks quarterly history in 'info', we use 'earningsGrowth' as proxy
        q_eps_growth = info.get('earningsGrowth', 0)
        if q_eps_growth and q_eps_growth > 0.20:
            score += 20
            details.append(f"C: Pass ({q_eps_growth:.0%})")
        else:
            details.append(f"C: Fail ({q_eps_growth:.0%})")

        # A - Annual Earnings (5yr Growth > 20%)
        # Proxy: revenueGrowth or pegRatio check
        # Ideally we want 3-5y CAGR. YF gives 'earningsQuarterlyGrowth' sometimes.
        # Let's use Forward PE vs Trailing PE as a growth proxy if CAGR missing.
        # Better: checking ROE > 17% (O'Neil rule)
        roe = info.get('returnOnEquity', 0)
        if roe and roe > 0.17:
            score += 15
            details.append(f"A: Pass (ROE {roe:.0%})")
        else:
            details.append("A: Fail (Low ROE)")

        # N - New Highs (Within 10% of 52w High)
        high_52 = hist['High'].max()
        current = hist['Close'].iloc[-1]
        dist = (high_52 - current) / high_52
        if dist < 0.10: # Near High
            score += 15
            details.append("N: Pass (Near High)")
        else:
            details.append(f"N: Fail ({dist:.0%} off)")

        # S - Supply/Demand (Volume Surge on Up days)
        # Check if latest up-day volume > avg volume
        avg_vol = hist['Volume'].tail(50).mean()
        last_vol = hist['Volume'].iloc[-1]
        if last_vol > avg_vol and hist['Close'].iloc[-1] > hist['Open'].iloc[-1]:
            score += 10
            details.append("S: Pass (High Demand)")
        else:
            # Or low float? Hard to check float.
            details.append("S: Fail")

        # L - Leader (RS > 80)
        # Using our RS logic vs SPY (approx 3m)
        spy = yf.Ticker("SPY").history(period="3mo")
        stock_3m = hist.tail(63)
        if len(stock_3m) > 0 and len(spy) > 0:
            s_ret = (stock_3m['Close'].iloc[-1] / stock_3m['Close'].iloc[0]) - 1
            m_ret = (spy['Close'].iloc[-1] / spy['Close'].iloc[0]) - 1
            if s_ret > m_ret * 1.5: # Leading market by 1.5x
                score += 20
                details.append(f"L: Pass (RS {s_ret:.1%} vs {m_ret:.1%})")
            else:
                details.append("L: Fail (Lagging)")
        
        # I - Institutional Sponsorship (Held % > 40%)
        inst_held = info.get('heldPercentInstitutions', 0)
        if inst_held and inst_held > 0.40:
            score += 10
            details.append(f"I: Pass ({inst_held:.0%})")
        else:
            details.append("I: Fail")

        # M - Market Direction (Uptrend)
        # Check if SPY > 50sma
        spy_hist = yf.Ticker("SPY").history(period="6mo")
        spy_sma50 = spy_hist['Close'].rolling(50).mean().iloc[-1]
        if spy_hist['Close'].iloc[-1] > spy_sma50:
            score += 10 # Market is confirmed uptrend
            details.append("M: Pass (Uptrend)")
        else:
            details.append("M: Fail (Correction)")

        return score, ", ".join(details)

    except Exception as e:
        return 0, f"Error: {e}"

def scan_canslim():
    tickers = ["MLM", "PWR", "NVDA", "VRT", "LLY", "PLTR", "MSFT", "O", "TPL"]
    print(f"Running CANSLIM Scan on {len(tickers)} top names...\n")
    print(f"{'TICKER':<6} {'SCORE':<5} {'DETAILS'}")
    print("─" * 60)
    
    for t in tickers:
        score, note = get_canslim_score(t)
        print(f"{t:<6} {score:<5} {note}")

if __name__ == "__main__":
    scan_canslim()

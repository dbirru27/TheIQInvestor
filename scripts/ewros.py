#!/usr/bin/env python3
"""
EWROS — Exponential Weighted Relative Outperformance Score

For each stock over the last 63 trading days (~3 months):
  1. daily_alpha = stock_daily_return - SPY_daily_return
  2. weight = e^(-λ × days_ago)   (λ = 0.03, ~33 day half-life)
  3. EWROS_raw = Σ(daily_alpha × weight)
  4. Rank all stocks → percentile 1-99

Saves ewros_score (1-99) and ewros_raw into all_stocks.json.
"""
import json
import math
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE, 'data')
ALL_STOCKS_FILE = os.path.join(DATA_DIR, 'all_stocks.json')

LOOKBACK_DAYS = 63  # ~3 months of trading days
LAMBDA = 0.03       # decay factor, ~33 day half-life
MAX_WORKERS = 10


def fetch_daily_closes(ticker, period='6mo'):
    """Fetch daily closes from Yahoo Finance chart API."""
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={period}&interval=1d'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        result = data.get('chart', {}).get('result', [{}])[0]
        closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
        return [c for c in closes if c is not None]
    except Exception:
        return []


def compute_daily_returns(closes):
    """Convert closes to daily % returns."""
    if len(closes) < 2:
        return []
    returns = []
    for i in range(1, len(closes)):
        if closes[i-1] > 0:
            returns.append((closes[i] - closes[i-1]) / closes[i-1])
        else:
            returns.append(0.0)
    return returns


def compute_ewros_raw(stock_returns, spy_returns):
    """
    Compute EWROS raw score.
    Aligns the last N days of both return series,
    computes daily alpha, applies exponential weighting.
    """
    n = min(len(stock_returns), len(spy_returns), LOOKBACK_DAYS)
    if n < 20:  # Need at least 20 days
        return None

    # Take the last n days
    s_ret = stock_returns[-n:]
    b_ret = spy_returns[-n:]

    ewros = 0.0
    for i in range(n):
        days_ago = n - 1 - i  # most recent = 0
        alpha = s_ret[i] - b_ret[i]
        weight = math.exp(-LAMBDA * days_ago)
        ewros += alpha * weight

    return ewros


def main():
    print("📊 EWROS — Exponential Weighted Relative Outperformance Score")
    print(f"   Lookback: {LOOKBACK_DAYS} days | λ: {LAMBDA} | Half-life: {int(math.log(2)/LAMBDA)} days")
    print("=" * 60)

    # Load all stocks
    with open(ALL_STOCKS_FILE) as f:
        data = json.load(f)

    stocks = data.get('stocks', data)
    tickers = list(stocks.keys())
    print(f"📈 Scoring {len(tickers)} stocks...")

    # Fetch SPY benchmark first
    print("   Fetching SPY benchmark...")
    spy_closes = fetch_daily_closes('SPY')
    spy_returns = compute_daily_returns(spy_closes)
    if len(spy_returns) < LOOKBACK_DAYS:
        print(f"❌ SPY data insufficient ({len(spy_returns)} days). Aborting.")
        sys.exit(1)
    print(f"   SPY: {len(spy_returns)} daily returns ✓")

    # Fetch all stock data in parallel
    raw_scores = {}
    failed = 0
    completed = 0

    def process_ticker(ticker):
        closes = fetch_daily_closes(ticker)
        returns = compute_daily_returns(closes)
        score = compute_ewros_raw(returns, spy_returns)
        return ticker, score

    print(f"   Fetching {len(tickers)} stocks ({MAX_WORKERS} threads)...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_ticker, t): t for t in tickers}
        for f in as_completed(futures):
            completed += 1
            ticker, score = f.result()
            if score is not None:
                raw_scores[ticker] = score
            else:
                failed += 1
            if completed % 100 == 0:
                print(f"   ... {completed}/{len(tickers)} done")

    print(f"\n✅ Scored {len(raw_scores)} stocks ({failed} failed)")

    # Rank → percentile 1-99
    sorted_tickers = sorted(raw_scores.keys(), key=lambda t: raw_scores[t])
    total = len(sorted_tickers)

    percentiles = {}
    for rank, ticker in enumerate(sorted_tickers):
        pct = int(((rank + 1) / total) * 99)
        pct = max(1, min(99, pct))
        percentiles[ticker] = pct

    # Save back into all_stocks.json
    for ticker in stocks:
        if ticker in percentiles:
            stocks[ticker]['ewros_score'] = percentiles[ticker]
            stocks[ticker]['ewros_raw'] = round(raw_scores[ticker] * 10000, 2)  # basis points
        else:
            stocks[ticker]['ewros_score'] = None
            stocks[ticker]['ewros_raw'] = None

    with open(ALL_STOCKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    # Print top/bottom
    print(f"\n🏆 TOP 10 EWROS:")
    for ticker in sorted_tickers[-10:][::-1]:
        print(f"   {ticker:6s}  RS {percentiles[ticker]:2d}  raw={raw_scores[ticker]*10000:+.1f}bps")

    print(f"\n📉 BOTTOM 10 EWROS:")
    for ticker in sorted_tickers[:10]:
        print(f"   {ticker:6s}  RS {percentiles[ticker]:2d}  raw={raw_scores[ticker]*10000:+.1f}bps")

    # Portfolio highlights
    print(f"\n💼 Portfolio EWROS:")
    portfolio_file = os.path.join(DATA_DIR, 'watchlist.json')
    if os.path.exists(portfolio_file):
        with open(portfolio_file) as f:
            wl = json.load(f)
        holdings = [h['ticker'] for h in wl.get('all', [])]
        for t in sorted(holdings):
            if t in percentiles:
                indicator = '🟢' if percentiles[t] >= 70 else '🟡' if percentiles[t] >= 40 else '🔴'
                print(f"   {indicator} {t:6s}  RS {percentiles[t]:2d}  raw={raw_scores[t]*10000:+.1f}bps")

    print(f"\n💾 Saved to {ALL_STOCKS_FILE}")


if __name__ == '__main__':
    main()

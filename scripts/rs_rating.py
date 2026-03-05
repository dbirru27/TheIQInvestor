#!/usr/bin/env python3
"""
RS Rating Calculator — Relative Strength percentile ranking (1-99).
Fetches 12-month daily closes for all stocks in all_stocks.json via Yahoo Finance chart API.
Weights: 40% last 3 months + 20% each prior quarter.
Saves rs_rating into all_stocks.json for each stock.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
ALL_STOCKS_FILE = os.path.join(DATA_DIR, 'all_stocks.json')


def fetch_12mo_closes(ticker):
    """Fetch 12 months of daily closes from Yahoo Finance chart API."""
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        result = data.get('chart', {}).get('result', [{}])[0]
        closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
        valid = [c for c in closes if c is not None]
        return valid
    except Exception:
        return []


def compute_weighted_return(closes):
    """
    Compute weighted performance from daily closes.
    Split into 4 quarters (most recent ~63 trading days each).
    Weight: Q4 (most recent) 40%, Q3 20%, Q2 20%, Q1 20%.
    """
    if len(closes) < 60:
        return None

    # Split into 4 roughly equal quarters
    n = len(closes)
    q_size = n // 4
    if q_size < 10:
        return None

    # Q1 = oldest, Q4 = newest
    q1_start, q1_end = 0, q_size
    q2_start, q2_end = q_size, 2 * q_size
    q3_start, q3_end = 2 * q_size, 3 * q_size
    q4_start, q4_end = 3 * q_size, n

    def quarter_return(start, end):
        s = closes[start]
        e = closes[end - 1]
        if s and s > 0:
            return (e - s) / s * 100
        return 0

    r1 = quarter_return(q1_start, q1_end)
    r2 = quarter_return(q2_start, q2_end)
    r3 = quarter_return(q3_start, q3_end)
    r4 = quarter_return(q4_start, q4_end)

    weighted = r4 * 0.40 + r3 * 0.20 + r2 * 0.20 + r1 * 0.20
    return weighted


def main():
    print(f"[RS Rating] Starting at {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M EST')}")

    with open(ALL_STOCKS_FILE) as f:
        data = json.load(f)

    stocks = data.get('stocks', {})
    tickers = list(stocks.keys())
    print(f"[RS Rating] Processing {len(tickers)} tickers...")

    # Fetch prices and compute weighted returns
    from concurrent.futures import ThreadPoolExecutor, as_completed

    raw_scores = {}
    failed = 0

    def process_ticker(ticker):
        closes = fetch_12mo_closes(ticker)
        wr = compute_weighted_return(closes)
        return ticker, wr

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_ticker, t): t for t in tickers}
        done = 0
        for f in as_completed(futures):
            ticker, wr = f.result()
            done += 1
            if wr is not None:
                raw_scores[ticker] = wr
            else:
                failed += 1
            if done % 50 == 0:
                print(f"  ... {done}/{len(tickers)} processed")

    print(f"[RS Rating] Got scores for {len(raw_scores)} stocks ({failed} failed)")

    if not raw_scores:
        print("[RS Rating] No scores computed, aborting.")
        sys.exit(1)

    # Percentile rank 1-99
    sorted_tickers = sorted(raw_scores.keys(), key=lambda t: raw_scores[t])
    n = len(sorted_tickers)

    for rank_idx, ticker in enumerate(sorted_tickers):
        percentile = int((rank_idx / (n - 1)) * 98) + 1 if n > 1 else 50
        percentile = max(1, min(99, percentile))
        if ticker in stocks:
            stocks[ticker]['rs_rating'] = percentile

    # Stocks without data get rs_rating = 0 (unknown)
    for ticker in tickers:
        if ticker not in raw_scores:
            stocks[ticker]['rs_rating'] = 0

    data['stocks'] = stocks
    with open(ALL_STOCKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    # Print top 10
    top = sorted(raw_scores.keys(), key=lambda t: stocks[t].get('rs_rating', 0), reverse=True)[:10]
    print("\n[RS Rating] Top 10:")
    for t in top:
        print(f"  {t:8s}  RS={stocks[t]['rs_rating']:3d}  raw={raw_scores[t]:+.1f}%")

    print(f"\n[RS Rating] Done. Updated {len(raw_scores)} stocks in all_stocks.json")


if __name__ == '__main__':
    main()

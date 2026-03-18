#!/usr/bin/env python3
"""
Live Market Internals Updater
==============================
Runs every 15 minutes during market hours (9:30 AM – 4:15 PM ET, Mon–Fri).
Writes data/market_internals.json and pushes to GitHub Pages so the
static website gets live market stage data without needing a Flask server.

Cron schedule: */15 9-16 * * 1-5  America/New_York
"""

import os, sys, json, time
import yfinance as yf
import pandas as pd
from datetime import datetime, date
from zoneinfo import ZoneInfo

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

from scripts.market_stage import compute_market_stage

ET = ZoneInfo("America/New_York")
OUT_PATH = os.path.join(WORKSPACE, "data/market_internals.json")


def is_market_hours():
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=15, second=0, microsecond=0)
    return market_open <= now <= market_close


def fetch_spy_live_quote():
    """Get today's SPY intraday change and volume."""
    try:
        spy = yf.Ticker("SPY")
        fast = spy.fast_info
        return {
            "price":        round(float(fast.last_price), 2),
            "change_pct":   round((float(fast.last_price) / float(fast.previous_close) - 1) * 100, 2),
            "volume":       int(fast.three_month_average_volume),   # approx; today's vol below
            "prev_close":   round(float(fast.previous_close), 2),
        }
    except Exception:
        return {}


def fetch_breadth():
    """Up/down ratio of major large-caps as a breadth proxy."""
    TICKERS = ['AAPL','MSFT','NVDA','AMZN','GOOGL','META','JPM','BAC',
               'XOM','CVX','HD','PG','JNJ','UNH','V','MA','AVGO','ORCL','CSCO','TXN']
    try:
        data = yf.download(TICKERS, period="2d", auto_adjust=False,
                           progress=False, group_by='ticker')
        up = 0
        for t in TICKERS:
            try:
                closes = data[t]['Close'].dropna().tolist()
                if len(closes) >= 2 and closes[-1] > closes[-2]:
                    up += 1
            except Exception:
                pass
        return {"up": up, "total": len(TICKERS), "pct": round(up / len(TICKERS) * 100, 1)}
    except Exception:
        return {}


def main():
    print(f"[{datetime.now(ET).strftime('%H:%M ET')}] Updating market internals...")

    # Fetch SPY history (used for market stage + volume avg)
    spy = yf.Ticker("SPY")
    hist = spy.history(period="6mo", auto_adjust=False)

    # Market stage (proper IBD FTD logic)
    stage = compute_market_stage(hist)

    # Volume comparison: today vs 50-day avg
    volume_data = {}
    if len(hist) >= 2:
        avg_50 = hist['Volume'].iloc[-51:-1].mean() if len(hist) > 51 else hist['Volume'].iloc[:-1].mean()
        today_vol   = int(hist['Volume'].iloc[-1])
        yesterday_vol = int(hist['Volume'].iloc[-2])
        vol_vs_avg  = round((today_vol / avg_50 - 1) * 100, 1) if avg_50 else 0
        volume_data = {
            "today":       today_vol,
            "yesterday":   yesterday_vol,
            "avg_50d":     int(avg_50),
            "vs_avg_pct":  vol_vs_avg,
            "above_avg":   vol_vs_avg > 0,
        }

    # Live quote
    quote = fetch_spy_live_quote()

    # Breadth
    breadth = fetch_breadth()

    result = {
        "market_stage": stage,
        "volume":       volume_data,
        "spy_quote":    quote,
        "breadth":      breadth,
        "updated_at":   datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET"),
        "market_open":  is_market_hours(),
    }

    def default_serializer(obj):
        if isinstance(obj, bool):
            return bool(obj)
        if hasattr(obj, 'item'):   # numpy scalar
            return obj.item()
        raise TypeError(f"Not serializable: {type(obj)}")

    with open(OUT_PATH, 'w') as f:
        json.dump(result, f, indent=2, default=default_serializer)

    print(f"  Stage: {stage['stage']}")
    print(f"  Distribution days: {stage['distribution_days']}")
    print(f"  FTD: {stage['follow_through_day'] or 'None'}")
    print(f"  Rally day: {stage.get('rally_day') or 'N/A'}")
    print(f"  Written to {OUT_PATH}")

    # Push to GitHub Pages so the static site is live
    ts = datetime.now(ET).strftime("%H:%M")
    os.system(f"cd {WORKSPACE} && git add -f data/market_internals.json && "
              f"git commit -m 'live: market internals {ts}' -q && git push -q")
    print("  Pushed to GitHub Pages.")


if __name__ == "__main__":
    main()

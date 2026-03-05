#!/usr/bin/env python3
"""
Smart Alerts Checker — Cron script to evaluate alerts defined in data/alerts.json.
Alert types:
  - price_above / price_below: trigger when current price crosses threshold
  - rotation_above / rotation_below: trigger on rotation score threshold
  - ins_above / ins_below: trigger on insider score threshold

Triggered alerts get marked with triggered=true and triggered_at timestamp.
Run via cron (e.g., every 15 min during market hours).
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
ALERTS_FILE = os.path.join(DATA_DIR, 'alerts.json')
ALL_STOCKS_FILE = os.path.join(DATA_DIR, 'all_stocks.json')


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else []


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def fetch_live_prices(tickers):
    """Fetch current prices for a list of tickers."""
    results = {}
    batch_size = 15
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        symbols = ','.join(batch)
        url = f'https://query1.finance.yahoo.com/v8/finance/spark?symbols={symbols}&range=1d&interval=1m'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read())
            for sym, info in data.items():
                closes = info.get('close', [])
                if closes:
                    results[sym] = closes[-1]
        except Exception:
            pass
    return results


def main():
    now = datetime.now(ZoneInfo('America/New_York'))
    print(f"[Alerts] Checking alerts at {now.strftime('%Y-%m-%d %H:%M EST')}")

    alerts = load_json(ALERTS_FILE, [])
    if not alerts:
        print("[Alerts] No alerts configured.")
        return

    # Filter to active (not yet triggered) alerts
    active = [a for a in alerts if not a.get('triggered')]
    if not active:
        print("[Alerts] No active alerts.")
        return

    print(f"[Alerts] {len(active)} active alerts to check")

    # Gather unique tickers
    tickers = list(set(a['ticker'] for a in active))

    # Load all_stocks for rotation/insider scores
    all_stocks = load_json(ALL_STOCKS_FILE, {}).get('stocks', {})

    # Fetch live prices for price-type alerts
    price_alert_tickers = [a['ticker'] for a in active if a['type'].startswith('price_')]
    live_prices = fetch_live_prices(list(set(price_alert_tickers))) if price_alert_tickers else {}

    triggered_count = 0
    for alert in alerts:
        if alert.get('triggered'):
            continue

        ticker = alert['ticker']
        atype = alert['type']
        threshold = alert['threshold']

        triggered = False

        if atype == 'price_above':
            price = live_prices.get(ticker)
            if price is not None and price >= threshold:
                triggered = True
                alert['current_value'] = round(price, 2)

        elif atype == 'price_below':
            price = live_prices.get(ticker)
            if price is not None and price <= threshold:
                triggered = True
                alert['current_value'] = round(price, 2)

        elif atype == 'rotation_above':
            stock = all_stocks.get(ticker, {})
            rot = stock.get('rotation_score', 0)
            if rot >= threshold:
                triggered = True
                alert['current_value'] = rot

        elif atype == 'rotation_below':
            stock = all_stocks.get(ticker, {})
            rot = stock.get('rotation_score', 0)
            if rot <= threshold:
                triggered = True
                alert['current_value'] = rot

        elif atype == 'ins_above':
            stock = all_stocks.get(ticker, {})
            ins = stock.get('ins_score', 0)
            if ins >= threshold:
                triggered = True
                alert['current_value'] = ins

        elif atype == 'ins_below':
            stock = all_stocks.get(ticker, {})
            ins = stock.get('ins_score', 0)
            if ins <= threshold:
                triggered = True
                alert['current_value'] = ins

        if triggered:
            alert['triggered'] = True
            alert['triggered_at'] = now.isoformat()
            triggered_count += 1
            print(f"  TRIGGERED: {ticker} {atype} threshold={threshold} value={alert.get('current_value')}")

    save_json(ALERTS_FILE, alerts)
    print(f"[Alerts] Done. {triggered_count} alerts triggered.")


if __name__ == '__main__':
    main()

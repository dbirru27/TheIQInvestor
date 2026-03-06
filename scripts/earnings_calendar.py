#!/usr/bin/env python3
"""
Earnings Calendar — Daily fetch + email alerts for upcoming earnings.
Fetches earnings dates for all portfolio holdings from yfinance,
caches to data/earnings_calendar.json, and emails alerts for
earnings within ALERT_DAYS_THRESHOLD days.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

# Config
ALERT_DAYS_THRESHOLD = 7  # Email alert if earnings within this many days
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(WORKSPACE, 'data', 'earnings_calendar.json')
EMAIL_TO = 'dbirru@gmail.com'

# Supabase config
sys.path.insert(0, WORKSPACE)
try:
    from config import SUPABASE_URL, SUPABASE_KEY
except ImportError:
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# FOMC dates 2026
FOMC_DATES = [
    {'date': '2026-03-18', 'label': 'FOMC Mar 18-19'},
    {'date': '2026-05-06', 'label': 'FOMC May 6-7'},
    {'date': '2026-06-17', 'label': 'FOMC Jun 17-18'},
    {'date': '2026-07-29', 'label': 'FOMC Jul 29-30'},
    {'date': '2026-09-16', 'label': 'FOMC Sep 16-17'},
    {'date': '2026-11-04', 'label': 'FOMC Nov 4-5'},
    {'date': '2026-12-16', 'label': 'FOMC Dec 16-17'},
]


def fetch_portfolio_tickers():
    """Get all portfolio tickers from Supabase"""
    tickers = []
    baskets_map = {}
    try:
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/baskets?select=name,holdings(ticker)',
            headers=headers
        )
        baskets_raw = json.loads(urllib.request.urlopen(req).read())
        for b in baskets_raw:
            for h in b.get('holdings', []):
                t = h['ticker']
                tickers.append(t)
                baskets_map[t] = b['name']
    except Exception as e:
        print(f"⚠️  Supabase fetch failed: {e}")
    return list(set(tickers)), baskets_map


def fetch_earnings(ticker, today):
    """Fetch earnings date for a single ticker"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if cal is None or (hasattr(cal, 'empty') and cal.empty):
            return None

        ed = None
        if isinstance(cal, dict):
            ed = cal.get('Earnings Date')
            if isinstance(ed, list) and ed:
                ed = ed[0]
        else:
            if 'Earnings Date' in cal.columns:
                ed = cal['Earnings Date'].iloc[0]
            elif 'Earnings Date' in cal.index:
                val = cal.loc['Earnings Date']
                ed = val.iloc[0] if hasattr(val, 'iloc') else val

        if ed is None:
            return None

        if hasattr(ed, 'date'):
            ed_date = ed.date()
        elif isinstance(ed, str):
            ed_date = datetime.strptime(ed[:10], '%Y-%m-%d').date()
        elif isinstance(ed, date):
            ed_date = ed
        else:
            return None

        days_until = (ed_date - today).days
        return {
            'ticker': ticker,
            'earnings_date': ed_date.isoformat(),
            'days_until': days_until
        }
    except Exception:
        return None


def build_alert_email(upcoming, today_str):
    """Build HTML email for upcoming earnings alerts"""
    rows = ''
    for e in upcoming:
        days = e['days_until']
        basket = e.get('basket', '')
        urgency = '🔴' if days <= 2 else '🟡' if days <= 4 else '🟢'
        rows += f"""
        <tr>
            <td style="padding: 10px 16px; border-bottom: 1px solid #2d3748;">{urgency} {e['ticker']}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #2d3748;">{basket}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #2d3748;">{e['earnings_date']}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #2d3748; font-weight: 700;">{days} day{'s' if days != 1 else ''}</td>
        </tr>"""

    return f"""
    <html>
    <body style="background: #0f172a; color: #f8fafc; font-family: 'Inter', Arial, sans-serif; padding: 24px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #38bdf8; margin-bottom: 4px;">📅 Earnings Alert</h1>
            <p style="color: #94a3b8; margin-top: 0;">The IQ Investor · {today_str}</p>
            
            <p style="color: #e2e8f0;">{len(upcoming)} holding{'s' if len(upcoming) != 1 else ''} reporting earnings within {ALERT_DAYS_THRESHOLD} days:</p>
            
            <table style="width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden;">
                <thead>
                    <tr style="background: #161b2a;">
                        <th style="padding: 10px 16px; text-align: left; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase;">Ticker</th>
                        <th style="padding: 10px 16px; text-align: left; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase;">Basket</th>
                        <th style="padding: 10px 16px; text-align: left; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase;">Date</th>
                        <th style="padding: 10px 16px; text-align: left; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase;">In</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            
            <p style="color: #64748b; font-size: 0.8rem; margin-top: 20px;">
                🔴 ≤2 days &nbsp; 🟡 3-4 days &nbsp; 🟢 5-7 days<br>
                Consider reviewing positions before earnings. Check the 
                <a href="https://qortexai.com/#calendar" style="color: #38bdf8;">Calendar</a> for details.
            </p>
        </div>
    </body>
    </html>"""


def send_alert(html_body, count, today_str):
    """Send earnings alert email"""
    try:
        sys.path.insert(0, os.path.join(WORKSPACE, 'tools'))
        from email_sender import send_email
        subject = f"📅 Earnings Alert: {count} holding{'s' if count != 1 else ''} reporting this week — {today_str}"
        send_email(EMAIL_TO, subject, html_body)
        return True
    except Exception as e:
        print(f"⚠️  Email send failed: {e}")
        return False


def main():
    now = datetime.now(ZoneInfo("America/New_York"))
    today = now.date()
    today_str = today.strftime('%b %d, %Y')

    print(f"📅 Earnings Calendar — {today_str}")
    print("=" * 50)

    # Fetch portfolio
    tickers, baskets_map = fetch_portfolio_tickers()
    if not tickers:
        print("❌ No tickers found")
        sys.exit(1)
    print(f"📊 Scanning {len(tickers)} portfolio tickers...")

    # Fetch earnings dates
    events = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_earnings, t, today): t for t in tickers}
        for f in as_completed(futures):
            result = f.result()
            if result:
                result['basket'] = baskets_map.get(result['ticker'], '')
                events.append(result)

    events.sort(key=lambda x: x['earnings_date'])
    print(f"✅ Found {len(events)} earnings dates")

    # Add FOMC days_until
    fomc = []
    for f in FOMC_DATES:
        fd = datetime.strptime(f['date'], '%Y-%m-%d').date()
        f_copy = dict(f)
        f_copy['days_until'] = (fd - today).days
        fomc.append(f_copy)

    # Save cache
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    output = {
        'earnings': events,
        'fomc': fomc,
        'timestamp': now.strftime("%Y-%m-%d %H:%M:%S EST"),
        'ticker_count': len(tickers)
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"💾 Saved to {OUTPUT_FILE}")

    # Check for upcoming earnings needing alerts
    upcoming = [e for e in events if 0 <= e['days_until'] <= ALERT_DAYS_THRESHOLD]

    if upcoming:
        print(f"\n🚨 {len(upcoming)} earnings within {ALERT_DAYS_THRESHOLD} days:")
        for e in upcoming:
            print(f"   {e['ticker']:6s} — {e['earnings_date']} ({e['days_until']}d) [{e['basket']}]")

        html = build_alert_email(upcoming, today_str)
        if send_alert(html, len(upcoming), today_str):
            print("📧 Alert email sent!")
        else:
            print("⚠️  Alert email failed")
    else:
        print(f"\n✅ No earnings within {ALERT_DAYS_THRESHOLD} days — no alert needed")

    # Summary
    print(f"\n📋 Summary:")
    print(f"   Total earnings dates: {len(events)}")
    print(f"   Within 7 days: {len(upcoming)}")
    next_up = [e for e in events if e['days_until'] >= 0]
    if next_up:
        n = next_up[0]
        print(f"   Next up: {n['ticker']} on {n['earnings_date']} ({n['days_until']}d)")


if __name__ == '__main__':
    main()

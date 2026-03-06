#!/usr/bin/env python3
"""
Earnings Recap — Post-earnings summary email for:
  1. Portfolio holdings (from Supabase)
  2. Watchlist tickers
  3. Rotation scan A/B rated stocks (from all_stocks.json)

Checks which tickers reported earnings today/yesterday,
fetches results, and emails a recap.

Runs daily at 5:30 PM ET (Mon-Fri).
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMAIL_TO = 'dbirru@gmail.com'
LOOKBACK_DAYS = 2  # Catch after-close + pre-market reports

sys.path.insert(0, WORKSPACE)
try:
    from config import SUPABASE_URL, SUPABASE_KEY
except ImportError:
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')


def fetch_portfolio_tickers():
    """Get portfolio tickers + basket mapping from Supabase"""
    tickers = set()
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
                tickers.add(t)
                baskets_map[t] = b['name']
    except Exception as e:
        print(f"⚠️  Supabase fetch failed: {e}")
    return tickers, baskets_map


def fetch_watchlist_tickers():
    """Get watchlist tickers"""
    tickers = set()
    path = os.path.join(WORKSPACE, 'data', 'watchlist.json')
    try:
        with open(path) as f:
            data = json.load(f)
        for item in data.get('all', []):
            tickers.add(item['ticker'])
    except Exception:
        pass
    return tickers


def fetch_rotation_ab_tickers():
    """Get A and B rated tickers from all_stocks.json (rotation candidates)"""
    tickers = set()
    names_map = {}
    path = os.path.join(WORKSPACE, 'data', 'all_stocks.json')
    try:
        with open(path) as f:
            data = json.load(f)
        stocks = data.get('stocks', data)
        for ticker, info in stocks.items():
            grade = info.get('grade', '')
            if grade in ('A', 'B'):
                tickers.add(ticker)
                names_map[ticker] = info.get('name', ticker)
    except Exception:
        pass
    return tickers, names_map


def fetch_earnings_result(ticker):
    """Fetch recent earnings results for a ticker"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        result = {
            'ticker': ticker,
            'name': info.get('shortName', info.get('longName', ticker)),
            'sector': info.get('sector', ''),
        }

        # EPS from earnings_dates
        try:
            import pandas as pd
            ed = stock.earnings_dates
            if ed is not None and not ed.empty:
                reported = ed[ed['Reported EPS'].notna()]
                if not reported.empty:
                    latest = reported.iloc[0]
                    result['eps_actual'] = float(latest['Reported EPS']) if pd.notna(latest.get('Reported EPS')) else None
                    result['eps_estimate'] = float(latest['EPS Estimate']) if pd.notna(latest.get('EPS Estimate')) else None
                    result['surprise_pct'] = float(latest['Surprise(%)']) if pd.notna(latest.get('Surprise(%)')) else None
                    result['earnings_date'] = str(latest.name.date()) if hasattr(latest.name, 'date') else str(latest.name)[:10]
        except Exception:
            pass

        # Revenue from quarterly financials
        try:
            qf = stock.quarterly_financials
            if qf is not None and not qf.empty:
                if 'Total Revenue' in qf.index:
                    rev = qf.loc['Total Revenue']
                    if len(rev) >= 2:
                        result['revenue_current'] = float(rev.iloc[0])
                        prior_idx = min(3, len(rev) - 1)
                        result['revenue_prior_year'] = float(rev.iloc[prior_idx])
                        if result['revenue_prior_year'] > 0:
                            result['revenue_growth'] = ((result['revenue_current'] - result['revenue_prior_year']) / result['revenue_prior_year']) * 100
        except Exception:
            pass

        # Price reaction
        try:
            hist = stock.history(period='5d')
            if hist is not None and len(hist) >= 2:
                result['price'] = float(hist['Close'].iloc[-1])
                result['prev_close'] = float(hist['Close'].iloc[-2])
                result['price_change_pct'] = ((result['price'] - result['prev_close']) / result['prev_close']) * 100
        except Exception:
            pass

        # Forward estimates
        result['forward_pe'] = info.get('forwardPE')
        result['analyst_target'] = info.get('targetMeanPrice')

        return result
    except Exception as e:
        print(f"  ⚠️  {ticker}: {e}")
        return None


def get_recently_reported(tickers):
    """Find which tickers reported earnings in the last LOOKBACK_DAYS"""
    import yfinance as yf
    today = datetime.now(ZoneInfo("America/New_York")).date()
    cutoff = today - timedelta(days=LOOKBACK_DAYS)
    reported = []

    def check_ticker(ticker):
        try:
            stock = yf.Ticker(ticker)
            ed = stock.earnings_dates
            if ed is not None and not ed.empty:
                import pandas as pd
                has_actual = ed[ed['Reported EPS'].notna()]
                if not has_actual.empty:
                    latest_date = has_actual.index[0]
                    if hasattr(latest_date, 'date'):
                        report_date = latest_date.date()
                    else:
                        report_date = datetime.strptime(str(latest_date)[:10], '%Y-%m-%d').date()
                    if report_date >= cutoff:
                        return ticker, report_date
        except Exception:
            pass
        return None, None

    print(f"🔍 Checking {len(tickers)} tickers for recent earnings reports...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_ticker, t): t for t in tickers}
        for f in as_completed(futures):
            ticker, report_date = f.result()
            if ticker:
                reported.append((ticker, report_date))

    return sorted(reported, key=lambda x: x[1], reverse=True)


def build_recap_email(sections, today_str):
    """Build HTML email with earnings recap, organized by section"""

    all_results = []
    for section in sections:
        all_results.extend(section['results'])

    total = len(all_results)
    beats = sum(1 for r in all_results if r.get('surprise_pct') and r['surprise_pct'] > 0)
    misses = sum(1 for r in all_results if r.get('surprise_pct') is not None and r['surprise_pct'] < 0)

    sections_html = ''
    for section in sections:
        if not section['results']:
            continue

        cards = ''
        for r in section['results']:
            ticker = r['ticker']
            surprise = r.get('surprise_pct')
            if surprise is not None:
                if surprise > 0:
                    verdict = f'✅ BEAT +{surprise:.1f}%'
                    verdict_color = '#10b981'
                elif surprise < 0:
                    verdict = f'❌ MISS {surprise:.1f}%'
                    verdict_color = '#ef4444'
                else:
                    verdict = '➖ IN LINE'
                    verdict_color = '#eab308'
            else:
                verdict = '—'
                verdict_color = '#94a3b8'

            eps_line = ''
            eps_actual = r.get('eps_actual')
            eps_estimate = r.get('eps_estimate')
            if eps_actual is not None:
                est_str = f' vs ${eps_estimate:.2f} est' if eps_estimate else ''
                eps_line = f'EPS: <b>${eps_actual:.2f}</b>{est_str}'

            rev_line = ''
            rev = r.get('revenue_current')
            rev_growth = r.get('revenue_growth')
            if rev:
                rev_b = rev / 1e9
                g_str = f' ({rev_growth:+.1f}% YoY)' if rev_growth else ''
                g_color = '#10b981' if (rev_growth and rev_growth > 0) else '#ef4444'
                rev_line = f' · Rev: ${rev_b:.2f}B<span style="color:{g_color}">{g_str}</span>'

            price_line = ''
            pc = r.get('price_change_pct')
            price = r.get('price')
            if pc is not None and price is not None:
                pc_color = '#10b981' if pc > 0 else '#ef4444'
                price_line = f' · <span style="color:{pc_color}">${price:.2f} ({pc:+.1f}%)</span>'

            basket = r.get('source_label', '')
            report_date = r.get('earnings_date', '')

            cards += f"""
            <div style="background:#1e293b; border:1px solid #2d3748; border-radius:10px; padding:16px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:1.2rem; font-weight:800; color:#38bdf8;">{ticker}</span>
                        <span style="font-size:0.8rem; color:#64748b; margin-left:8px;">{r.get('name','')}</span>
                    </div>
                    <span style="background:{verdict_color}22; color:{verdict_color}; padding:3px 10px; border-radius:16px; font-size:0.75rem; font-weight:700;">{verdict}</span>
                </div>
                <div style="font-size:0.7rem; color:#64748b; margin:4px 0 8px;">{basket} · {report_date}</div>
                <div style="font-size:0.85rem;">{eps_line}{rev_line}{price_line}</div>
            </div>"""

        sections_html += f"""
        <div style="margin-bottom:24px;">
            <h3 style="color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:2px; margin-bottom:12px;">{section['title']} ({len(section['results'])})</h3>
            {cards}
        </div>"""

    return f"""
    <html>
    <body style="background:#0f172a; color:#f8fafc; font-family:'Inter',Arial,sans-serif; padding:24px;">
        <div style="max-width:640px; margin:0 auto;">
            <h1 style="color:#38bdf8; margin-bottom:4px;">📊 Earnings Recap</h1>
            <p style="color:#94a3b8; margin-top:0;">The IQ Investor · {today_str}</p>

            <div style="background:#1e293b; border-radius:10px; padding:16px; margin-bottom:24px; display:flex; gap:24px;">
                <div><span style="font-size:1.5rem; font-weight:800;">{total}</span><br><span style="font-size:0.7rem; color:#94a3b8;">Reported</span></div>
                <div><span style="font-size:1.5rem; font-weight:800; color:#10b981;">{beats}</span><br><span style="font-size:0.7rem; color:#94a3b8;">Beat</span></div>
                <div><span style="font-size:1.5rem; font-weight:800; color:#ef4444;">{misses}</span><br><span style="font-size:0.7rem; color:#94a3b8;">Missed</span></div>
            </div>

            {sections_html}

            <p style="color:#64748b; font-size:0.75rem; margin-top:20px;">
                <a href="https://qortexai.com/#calendar" style="color:#38bdf8;">The IQ Investor</a> · Earnings Recap
            </p>
        </div>
    </body>
    </html>"""


def send_recap(html_body, count, today_str):
    """Send earnings recap email"""
    try:
        sys.path.insert(0, os.path.join(WORKSPACE, 'tools'))
        from email_sender import send_email
        subject = f"📊 Earnings Recap: {count} stock{'s' if count != 1 else ''} reported — {today_str}"
        send_email(EMAIL_TO, subject, html_body)
        return True
    except Exception as e:
        print(f"⚠️  Email send failed: {e}")
        return False


def main():
    now = datetime.now(ZoneInfo("America/New_York"))
    today = now.date()
    today_str = today.strftime('%b %d, %Y')

    print(f"📊 Earnings Recap — {today_str}")
    print("=" * 50)

    # Gather all tickers from 3 sources
    portfolio_tickers, baskets_map = fetch_portfolio_tickers()
    watchlist_tickers = fetch_watchlist_tickers()
    rotation_tickers, rotation_names = fetch_rotation_ab_tickers()

    # Remove overlap: portfolio > watchlist > rotation
    watchlist_only = watchlist_tickers - portfolio_tickers
    rotation_only = rotation_tickers - portfolio_tickers - watchlist_tickers

    all_tickers = portfolio_tickers | watchlist_only | rotation_only
    print(f"📊 Scanning: {len(portfolio_tickers)} portfolio, {len(watchlist_only)} watchlist, {len(rotation_only)} rotation A/B")
    print(f"   Total unique: {len(all_tickers)}")

    # Find who reported recently
    recently_reported = get_recently_reported(all_tickers)

    if not recently_reported:
        print("\n✅ No tickers reported earnings in the last 2 days. No email needed.")
        sys.exit(0)

    print(f"\n📋 {len(recently_reported)} tickers reported recently:")
    for ticker, dt in recently_reported:
        print(f"   {ticker:6s} — {dt}")

    # Fetch detailed results and categorize
    print(f"\n📈 Fetching earnings details...")
    portfolio_results = []
    watchlist_results = []
    rotation_results = []

    for ticker, report_date in recently_reported:
        result = fetch_earnings_result(ticker)
        if not result:
            continue

        if ticker in portfolio_tickers:
            result['source_label'] = baskets_map.get(ticker, 'Portfolio')
            portfolio_results.append(result)
        elif ticker in watchlist_only:
            result['source_label'] = 'Watchlist'
            watchlist_results.append(result)
        elif ticker in rotation_only:
            result['source_label'] = 'Rotation (A/B)'
            rotation_results.append(result)

    sections = [
        {'title': '🏦 Portfolio Holdings', 'results': portfolio_results},
        {'title': '👀 Watchlist', 'results': watchlist_results},
        {'title': '🔄 Rotation Scan (A/B Rated)', 'results': rotation_results},
    ]

    total = sum(len(s['results']) for s in sections)
    if total == 0:
        print("⚠️  Could not fetch any earnings details")
        sys.exit(1)

    # Print summary
    print(f"\n📊 Results:")
    for section in sections:
        if section['results']:
            print(f"\n  {section['title']}:")
            for r in section['results']:
                surprise = r.get('surprise_pct', 0)
                verdict = 'BEAT' if surprise and surprise > 0 else 'MISS' if surprise and surprise < 0 else 'N/A'
                eps = f"${r.get('eps_actual', 0):.2f}" if r.get('eps_actual') is not None else 'N/A'
                print(f"    {r['ticker']:6s} EPS: {eps:>8s}  {verdict:>6s}  ({surprise:+.1f}%)")

    # Build and send email
    html = build_recap_email(sections, today_str)
    if send_recap(html, total, today_str):
        print(f"\n📧 Recap email sent to {EMAIL_TO}!")
    else:
        print(f"\n⚠️  Email failed")


if __name__ == '__main__':
    main()

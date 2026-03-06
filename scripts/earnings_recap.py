#!/usr/bin/env python3
"""
Earnings Recap — Post-earnings summary email for portfolio holdings.
Checks which holdings reported earnings recently, fetches results,
and emails a summary to the user.

Run daily at ~7:30 AM ET to catch after-close + pre-market reports.
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
LOOKBACK_DAYS = 2  # Check earnings from last 2 days to catch after-close reports

sys.path.insert(0, WORKSPACE)
try:
    from config import SUPABASE_URL, SUPABASE_KEY
except ImportError:
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')


def fetch_portfolio_tickers():
    """Get all portfolio tickers + basket mapping from Supabase"""
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


def fetch_earnings_result(ticker):
    """Fetch recent earnings results for a ticker using yfinance"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # Get earnings history (quarterly)
        earnings_hist = None
        try:
            earnings_hist = stock.earnings_history
        except Exception:
            pass

        # Get quarterly earnings
        quarterly = None
        try:
            quarterly = stock.quarterly_earnings
        except Exception:
            pass

        # Get most recent quarter from earnings
        result = {
            'ticker': ticker,
            'name': info.get('shortName', info.get('longName', ticker)),
            'sector': info.get('sector', ''),
            'market_cap': info.get('marketCap', 0),
        }

        # EPS data
        eps_actual = info.get('trailingEps')
        eps_estimate = info.get('targetMeanPrice')  # Not ideal, check earnings_dates

        # Try earnings_dates for actual vs estimate
        try:
            import pandas as pd
            ed = stock.earnings_dates
            if ed is not None and not ed.empty:
                # Get most recent reported (has actual EPS)
                reported = ed[ed['Reported EPS'].notna()]
                if not reported.empty:
                    latest = reported.iloc[0]
                    result['eps_actual'] = float(latest['Reported EPS']) if pd.notna(latest.get('Reported EPS')) else None
                    result['eps_estimate'] = float(latest['EPS Estimate']) if pd.notna(latest.get('EPS Estimate')) else None
                    result['surprise_pct'] = float(latest['Surprise(%)']) if pd.notna(latest.get('Surprise(%)')) else None
                    result['earnings_date'] = str(latest.name.date()) if hasattr(latest.name, 'date') else str(latest.name)[:10]
        except Exception:
            pass

        # Revenue data from quarterly financials
        try:
            qf = stock.quarterly_financials
            if qf is not None and not qf.empty:
                if 'Total Revenue' in qf.index:
                    rev = qf.loc['Total Revenue']
                    if len(rev) >= 2:
                        result['revenue_current'] = float(rev.iloc[0])
                        result['revenue_prior_year'] = float(rev.iloc[min(3, len(rev)-1)])  # 4 quarters ago if available
                        if result['revenue_prior_year'] > 0:
                            result['revenue_growth'] = ((result['revenue_current'] - result['revenue_prior_year']) / result['revenue_prior_year']) * 100
        except Exception:
            pass

        # Current price + recent move
        try:
            hist = stock.history(period='5d')
            if hist is not None and len(hist) >= 2:
                result['price'] = float(hist['Close'].iloc[-1])
                result['prev_close'] = float(hist['Close'].iloc[-2])
                result['price_change_pct'] = ((result['price'] - result['prev_close']) / result['prev_close']) * 100
        except Exception:
            pass

        # Guidance / forward estimates
        result['forward_pe'] = info.get('forwardPE')
        result['forward_eps'] = info.get('forwardEps')
        result['analyst_target'] = info.get('targetMeanPrice')
        result['recommendation'] = info.get('recommendationKey', '')

        return result
    except Exception as e:
        print(f"  ⚠️  {ticker}: {e}")
        return None


def get_recently_reported(tickers, baskets_map):
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
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(check_ticker, t): t for t in tickers}
        for f in as_completed(futures):
            ticker, report_date = f.result()
            if ticker:
                reported.append((ticker, report_date))

    return sorted(reported, key=lambda x: x[1], reverse=True)


def build_recap_email(results, baskets_map, today_str):
    """Build HTML email with earnings recap"""
    cards = ''
    for r in results:
        ticker = r['ticker']
        basket = baskets_map.get(ticker, '')

        # EPS beat/miss
        eps_actual = r.get('eps_actual')
        eps_estimate = r.get('eps_estimate')
        surprise = r.get('surprise_pct')

        if surprise is not None:
            if surprise > 0:
                verdict = f'✅ BEAT by {surprise:.1f}%'
                verdict_color = '#10b981'
            elif surprise < 0:
                verdict = f'❌ MISSED by {abs(surprise):.1f}%'
                verdict_color = '#ef4444'
            else:
                verdict = '➖ IN LINE'
                verdict_color = '#eab308'
        else:
            verdict = '—'
            verdict_color = '#94a3b8'

        eps_line = ''
        if eps_actual is not None:
            est_str = f' vs ${eps_estimate:.2f} est' if eps_estimate else ''
            eps_line = f'<div style="font-size:0.85rem; margin-top:6px;">EPS: <b>${eps_actual:.2f}</b>{est_str}</div>'

        # Revenue
        rev_line = ''
        rev_current = r.get('revenue_current')
        rev_growth = r.get('revenue_growth')
        if rev_current:
            rev_b = rev_current / 1e9
            growth_str = f' ({rev_growth:+.1f}% YoY)' if rev_growth else ''
            rev_color = '#10b981' if (rev_growth and rev_growth > 0) else '#ef4444' if (rev_growth and rev_growth < 0) else '#94a3b8'
            rev_line = f'<div style="font-size:0.85rem; margin-top:4px;">Revenue: <b>${rev_b:.2f}B</b> <span style="color:{rev_color}">{growth_str}</span></div>'

        # Price reaction
        price_line = ''
        price_change = r.get('price_change_pct')
        price = r.get('price')
        if price_change is not None and price is not None:
            pcolor = '#10b981' if price_change > 0 else '#ef4444'
            price_line = f'<div style="font-size:0.85rem; margin-top:4px;">Price: ${price:.2f} <span style="color:{pcolor}">({price_change:+.1f}%)</span></div>'

        # Forward
        fwd_line = ''
        fwd_pe = r.get('forward_pe')
        analyst_target = r.get('analyst_target')
        parts = []
        if fwd_pe:
            parts.append(f'Fwd P/E: {fwd_pe:.1f}')
        if analyst_target:
            parts.append(f'Target: ${analyst_target:.0f}')
        if parts:
            fwd_line = f'<div style="font-size:0.8rem; color:#94a3b8; margin-top:4px;">{" · ".join(parts)}</div>'

        report_date = r.get('earnings_date', '')

        cards += f"""
        <div style="background: #1e293b; border: 1px solid #2d3748; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                    <span style="font-size: 1.3rem; font-weight: 800; color: #38bdf8;">{ticker}</span>
                    <span style="font-size: 0.8rem; color: #64748b; margin-left: 8px;">{r.get('name', '')}</span>
                </div>
                <span style="background: {verdict_color}22; color: {verdict_color}; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 700;">{verdict}</span>
            </div>
            <div style="font-size: 0.75rem; color: #64748b; margin-bottom: 8px;">{basket} · Reported {report_date}</div>
            {eps_line}
            {rev_line}
            {price_line}
            {fwd_line}
        </div>"""

    beats = sum(1 for r in results if r.get('surprise_pct', 0) and r['surprise_pct'] > 0)
    misses = sum(1 for r in results if r.get('surprise_pct') is not None and r['surprise_pct'] < 0)

    return f"""
    <html>
    <body style="background: #0f172a; color: #f8fafc; font-family: 'Inter', Arial, sans-serif; padding: 24px;">
        <div style="max-width: 640px; margin: 0 auto;">
            <h1 style="color: #38bdf8; margin-bottom: 4px;">📊 Earnings Recap</h1>
            <p style="color: #94a3b8; margin-top: 0;">The IQ Investor · {today_str}</p>
            
            <div style="background: #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 20px; display: flex; gap: 24px;">
                <div><span style="font-size: 1.5rem; font-weight: 800;">{len(results)}</span><br><span style="font-size: 0.75rem; color: #94a3b8;">Reported</span></div>
                <div><span style="font-size: 1.5rem; font-weight: 800; color: #10b981;">{beats}</span><br><span style="font-size: 0.75rem; color: #94a3b8;">Beat</span></div>
                <div><span style="font-size: 1.5rem; font-weight: 800; color: #ef4444;">{misses}</span><br><span style="font-size: 0.75rem; color: #94a3b8;">Missed</span></div>
            </div>

            {cards}
            
            <p style="color: #64748b; font-size: 0.8rem; margin-top: 20px;">
                View full details on <a href="https://qortexai.com/#calendar" style="color: #38bdf8;">The IQ Investor</a>
            </p>
        </div>
    </body>
    </html>"""


def send_recap(html_body, count, today_str):
    """Send earnings recap email"""
    try:
        sys.path.insert(0, os.path.join(WORKSPACE, 'tools'))
        from email_sender import send_email
        subject = f"📊 Earnings Recap: {count} holding{'s' if count != 1 else ''} reported — {today_str}"
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

    # Get portfolio
    tickers, baskets_map = fetch_portfolio_tickers()
    if not tickers:
        print("❌ No tickers found")
        sys.exit(1)

    # Find who reported recently
    recently_reported = get_recently_reported(tickers, baskets_map)

    if not recently_reported:
        print("✅ No portfolio holdings reported earnings in the last 2 days.")
        sys.exit(0)

    print(f"\n📋 {len(recently_reported)} holdings reported recently:")
    for ticker, date in recently_reported:
        print(f"   {ticker:6s} — {date}")

    # Fetch detailed results
    print(f"\n📈 Fetching earnings details...")
    results = []
    for ticker, report_date in recently_reported:
        result = fetch_earnings_result(ticker)
        if result:
            result['basket'] = baskets_map.get(ticker, '')
            results.append(result)

    if not results:
        print("⚠️  Could not fetch any earnings details")
        sys.exit(1)

    # Print summary
    print(f"\n📊 Results:")
    for r in results:
        surprise = r.get('surprise_pct')
        verdict = f"{'BEAT' if surprise and surprise > 0 else 'MISS' if surprise and surprise < 0 else 'N/A'}"
        eps = f"${r.get('eps_actual', 0):.2f}" if r.get('eps_actual') is not None else 'N/A'
        print(f"   {r['ticker']:6s} EPS: {eps:>8s}  {verdict:>6s}  ({r.get('surprise_pct', 0):+.1f}%)")

    # Build and send email
    html = build_recap_email(results, baskets_map, today_str)
    if send_recap(html, len(results), today_str):
        print(f"\n📧 Recap email sent to {EMAIL_TO}!")
    else:
        print(f"\n⚠️  Email failed")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
InvestIQ Insider Transaction Scanner
Fetches Form 4 filings from SEC EDGAR for all portfolio holdings.
Calculates Insider Net Score (INS) per ticker.
Runs daily as a cron job.

INS Scoring:
  Cluster buy (3+ insiders in 30d): +3
  CEO/CFO buy: +2 each
  Director/Officer buy: +1 each
  Buy > $500K: +1 bonus, > $1M: +2 bonus
  Cluster sell (3+ insiders in 30d): -3
  CEO/CFO sell: -2 each
  Director/Officer sell: -1 each
  Sell > 25% of holdings: -2
  All sells, no buys in 90d: -2

Signal:
  INS >= +3  → 🟢 Accumulating
  INS -2..+2 → ⚪ Neutral
  INS <= -3  → 🔴 Dumping
"""

import urllib.request
import json
import xml.etree.ElementTree as ET
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(WORKSPACE, 'data', 'insider_signals.json')
SEC_USER_AGENT = 'InvestIQ ***REMOVED***'
LOOKBACK_DAYS = 90

# CIK cache file
CIK_CACHE_FILE = os.path.join(WORKSPACE, 'data', 'cik_cache.json')


def load_cik_cache():
    if os.path.exists(CIK_CACHE_FILE):
        with open(CIK_CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cik_cache(cache):
    with open(CIK_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def get_cik_for_ticker(ticker, cache):
    """Get CIK number from SEC EDGAR company tickers JSON"""
    if ticker in cache:
        return cache[ticker]

    try:
        url = 'https://www.sec.gov/files/company_tickers.json'
        req = urllib.request.Request(url, headers={'User-Agent': SEC_USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())

        # Build ticker -> CIK mapping
        for _, entry in data.items():
            t = entry.get('ticker', '').upper()
            cik = str(entry.get('cik_str', '')).zfill(10)
            cache[t] = cik

        save_cik_cache(cache)
        return cache.get(ticker)
    except Exception as e:
        print(f"  Error fetching CIK list: {e}")
        return None


def get_form4_filings(cik, lookback_days=90):
    """Get recent Form 4 filing accession numbers from SEC EDGAR"""
    try:
        url = f'https://data.sec.gov/submissions/CIK{cik}.json'
        req = urllib.request.Request(url, headers={'User-Agent': SEC_USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())

        filings = data.get('filings', {}).get('recent', {})
        forms = filings.get('form', [])
        dates = filings.get('filingDate', [])
        accessions = filings.get('accessionNumber', [])

        cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        form4s = []
        for i, form in enumerate(forms):
            if form == '4' and i < len(dates) and dates[i] >= cutoff:
                form4s.append({
                    'filing_date': dates[i],
                    'accession': accessions[i],
                    'cik': cik
                })

        return form4s
    except Exception as e:
        print(f"  Error fetching filings for CIK {cik}: {e}")
        return []


def parse_form4_xml(cik, accession):
    """Parse a Form 4 XML filing to extract transaction details"""
    try:
        acc_clean = accession.replace('-', '')
        cik_int = str(int(cik))

        # Get filing index to find XML file
        index_url = f'https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{accession}-index.htm'
        req = urllib.request.Request(index_url, headers={'User-Agent': SEC_USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=10)
        content = resp.read().decode()

        import re
        # Find non-XSL XML files
        xml_files = re.findall(r'href="(/Archives/edgar/data/[^"]+\.xml)"', content)
        # Filter out XSL-transformed versions
        raw_xmls = [f for f in xml_files if 'xsl' not in f.lower()]

        if not raw_xmls:
            return None

        xml_url = f'https://www.sec.gov{raw_xmls[0]}'
        req2 = urllib.request.Request(xml_url, headers={'User-Agent': SEC_USER_AGENT})
        resp2 = urllib.request.urlopen(req2, timeout=10)
        xml_content = resp2.read().decode()

        root = ET.fromstring(xml_content)

        # Extract owner info
        owner_name = None
        owner_title = None
        is_officer = False
        is_director = False
        is_ceo_cfo = False

        owner_el = root.find('.//reportingOwner')
        if owner_el is not None:
            name_el = owner_el.find('.//rptOwnerName')
            title_el = owner_el.find('.//officerTitle')
            officer_el = owner_el.find('.//isOfficer')
            director_el = owner_el.find('.//isDirector')

            owner_name = name_el.text if name_el is not None else 'Unknown'
            owner_title = title_el.text if title_el is not None else ''
            is_officer = officer_el is not None and officer_el.text in ('1', 'true')
            is_director = director_el is not None and director_el.text in ('1', 'true')

            title_lower = (owner_title or '').lower()
            is_ceo_cfo = any(t in title_lower for t in ['ceo', 'cfo', 'chief executive', 'chief financial',
                                                          'president', 'chairman'])

        # Extract transactions
        transactions = []
        for txn in root.findall('.//nonDerivativeTransaction'):
            date_el = txn.find('.//transactionDate/value')
            code_el = txn.find('.//transactionCoding/transactionCode')
            shares_el = txn.find('.//transactionAmounts/transactionShares/value')
            price_el = txn.find('.//transactionAmounts/transactionPricePerShare/value')
            acq_disp_el = txn.find('.//transactionAmounts/transactionAcquiredDisposedCode/value')
            owned_after_el = txn.find('.//postTransactionAmounts/sharesOwnedFollowingTransaction/value')

            txn_code = code_el.text if code_el is not None else ''
            acq_disp = acq_disp_el.text if acq_disp_el is not None else ''

            # S = open market sale, P = open market purchase
            # A = grant/award (ignore), M = option exercise (ignore)
            # F = tax withholding (ignore)
            if txn_code not in ('S', 'P'):
                continue

            try:
                shares = float(shares_el.text) if shares_el is not None else 0
                price = float(price_el.text) if price_el is not None and price_el.text else 0
                owned_after = float(owned_after_el.text) if owned_after_el is not None else 0
            except (ValueError, TypeError):
                shares, price, owned_after = 0, 0, 0

            value = shares * price
            is_buy = txn_code == 'P'

            # Calculate % of holdings sold
            pct_sold = 0
            if not is_buy and owned_after > 0 and shares > 0:
                pct_sold = round(shares / (owned_after + shares) * 100, 1)

            transactions.append({
                'date': date_el.text if date_el is not None else '',
                'type': 'BUY' if is_buy else 'SELL',
                'shares': shares,
                'price': round(price, 2),
                'value': round(value, 0),
                'pct_of_holdings': pct_sold,
                'owner': owner_name,
                'title': owner_title,
                'is_officer': is_officer,
                'is_director': is_director,
                'is_c_suite': is_ceo_cfo
            })

        return transactions

    except Exception as e:
        return None


def calculate_ins_score(all_transactions):
    """Calculate Insider Net Score from aggregated transactions.
    
    IMPORTANT: Score per UNIQUE PERSON, not per transaction.
    One person selling 30 times = one seller, not 30 sell signals.
    """
    if not all_transactions:
        return 0, 'neutral', []

    score = 0
    reasons = []

    buys = [t for t in all_transactions if t['type'] == 'BUY']
    sells = [t for t in all_transactions if t['type'] == 'SELL']

    # Aggregate by unique person
    unique_buyers = {}
    for t in buys:
        name = t['owner']
        if name not in unique_buyers:
            unique_buyers[name] = {'total_value': 0, 'is_c_suite': t['is_c_suite'],
                                    'is_officer': t['is_officer'], 'is_director': t['is_director'],
                                    'title': t['title'], 'count': 0}
        unique_buyers[name]['total_value'] += t['value']
        unique_buyers[name]['count'] += 1

    unique_sellers = {}
    for t in sells:
        name = t['owner']
        if name not in unique_sellers:
            unique_sellers[name] = {'total_value': 0, 'is_c_suite': t['is_c_suite'],
                                     'is_officer': t['is_officer'], 'is_director': t['is_director'],
                                     'title': t['title'], 'count': 0, 'max_pct_sold': 0}
        unique_sellers[name]['total_value'] += t['value']
        unique_sellers[name]['count'] += 1
        if t['pct_of_holdings'] > unique_sellers[name]['max_pct_sold']:
            unique_sellers[name]['max_pct_sold'] = t['pct_of_holdings']

    # Cluster detection (3+ unique insiders)
    if len(unique_buyers) >= 3:
        score += 3
        reasons.append(f"Cluster buy: {len(unique_buyers)} insiders")

    if len(unique_sellers) >= 3:
        score -= 3
        reasons.append(f"Cluster sell: {len(unique_sellers)} insiders")

    # Score per unique person (not per transaction)
    for name, info in unique_buyers.items():
        if info['is_c_suite']:
            score += 2
            reasons.append(f"C-suite buy: {name} (${info['total_value']:,.0f})")
        elif info['is_officer'] or info['is_director']:
            score += 1

    for name, info in unique_sellers.items():
        if info['is_c_suite']:
            score -= 2
            reasons.append(f"C-suite sell: {name} (${info['total_value']:,.0f})")
        elif info['is_officer'] or info['is_director']:
            score -= 1

    # Large transaction bonuses (aggregate)
    total_buy_value = sum(t['value'] for t in buys)
    total_sell_value = sum(t['value'] for t in sells)

    if total_buy_value > 1_000_000:
        score += 2
        reasons.append(f"Large buys total: ${total_buy_value:,.0f}")
    elif total_buy_value > 500_000:
        score += 1
        reasons.append(f"Significant buys: ${total_buy_value:,.0f}")

    # Heavy selling: any person sold >25% of their holdings
    heavy_sellers = {name: info for name, info in unique_sellers.items() if info['max_pct_sold'] > 25}
    if heavy_sellers:
        score -= 2
        for name, info in heavy_sellers.items():
            reasons.append(f"Heavy sell: {name} dumped {info['max_pct_sold']:.0f}%")

    # All sells, no buys
    if unique_sellers and not unique_buyers:
        score -= 2
        reasons.append("All sells, zero buys in period")

    # Determine signal
    if score >= 3:
        signal = 'accumulating'
    elif score <= -3:
        signal = 'dumping'
    else:
        signal = 'neutral'

    return score, signal, reasons


def scan_ticker(ticker, cik_cache):
    """Scan a single ticker for insider activity"""
    cik = get_cik_for_ticker(ticker, cik_cache)
    if not cik:
        return ticker, None

    # Rate limit: SEC asks for max 10 req/sec
    time.sleep(0.15)

    filings = get_form4_filings(cik, LOOKBACK_DAYS)
    if not filings:
        return ticker, {
            'ins_score': 0,
            'signal': 'neutral',
            'signal_emoji': '⚪',
            'transactions': 0,
            'buys': 0,
            'sells': 0,
            'reasons': ['No Form 4 filings in last 90 days'],
            'details': []
        }

    # Parse each filing (limit to 15 most recent to stay fast)
    all_transactions = []
    parsed = 0
    for filing in filings[:15]:
        time.sleep(0.12)  # Rate limit
        txns = parse_form4_xml(cik, filing['accession'])
        if txns:
            all_transactions.extend(txns)
            parsed += 1

    score, signal, reasons = calculate_ins_score(all_transactions)

    emoji_map = {'accumulating': '🟢', 'neutral': '⚪', 'dumping': '🔴'}

    buys = [t for t in all_transactions if t['type'] == 'BUY']
    sells = [t for t in all_transactions if t['type'] == 'SELL']

    # Top 5 most notable transactions
    notable = sorted(all_transactions, key=lambda t: abs(t['value']), reverse=True)[:5]
    details = []
    for t in notable:
        details.append({
            'date': t['date'],
            'owner': t['owner'],
            'title': t['title'],
            'type': t['type'],
            'shares': int(t['shares']),
            'price': t['price'],
            'value': t['value']
        })

    return ticker, {
        'ins_score': score,
        'signal': signal,
        'signal_emoji': emoji_map.get(signal, '⚪'),
        'transactions': len(all_transactions),
        'buys': len(buys),
        'sells': len(sells),
        'total_buy_value': sum(t['value'] for t in buys),
        'total_sell_value': sum(t['value'] for t in sells),
        'reasons': reasons,
        'details': details
    }


def get_portfolio_tickers():
    """Get all portfolio tickers from Supabase"""
    # Load .env manually (no dotenv dependency)
    env_path = os.path.join(WORKSPACE, '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

    supabase_url = os.environ.get('SUPABASE_URL', 'https://jvgxgfbthfsdqtvzeuqz.supabase.co')
    supabase_key = os.environ.get('SUPABASE_KEY', '')

    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}'
    }
    req = urllib.request.Request(
        f'{supabase_url}/rest/v1/baskets?select=name,holdings(ticker)&order=sort_order',
        headers=headers
    )
    baskets = json.loads(urllib.request.urlopen(req).read())

    tickers = set()
    for b in baskets:
        for h in b.get('holdings', []):
            t = h['ticker']
            # Skip ETFs (they don't have insider filings)
            if t in ('VOO', 'XLI', 'GLD', 'GLDM', 'COPX', 'SIL', 'NLR', 'DXJ',
                      'INDA', 'XBI', 'VGT', 'VUG', 'UFO', 'GRID', 'ITA', 'SHLD', 'EUAD'):
                continue
            tickers.add(t)

    return sorted(tickers)


def main():
    print(f"🔍 InvestIQ Insider Transaction Scanner")
    print(f"   Lookback: {LOOKBACK_DAYS} days")
    print(f"   Source: SEC EDGAR Form 4")
    print()

    tickers = get_portfolio_tickers()
    print(f"📊 Scanning {len(tickers)} portfolio stocks...")
    print()

    cik_cache = load_cik_cache()
    results = {}
    alerts = []

    # Sequential to respect SEC rate limits
    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}...", end='', flush=True)
        _, data = scan_ticker(ticker, cik_cache)
        if data:
            results[ticker] = data
            emoji = data['signal_emoji']
            print(f" {emoji} INS={data['ins_score']:+d} ({data['buys']}B/{data['sells']}S)")

            if data['signal'] == 'dumping':
                alerts.append(f"🔴 {ticker}: INS={data['ins_score']:+d} — {'; '.join(data['reasons'])}")
            elif data['signal'] == 'accumulating':
                alerts.append(f"🟢 {ticker}: INS={data['ins_score']:+d} — {'; '.join(data['reasons'])}")
        else:
            print(f" ⚠️ No CIK found")

    # Save results
    output = {
        'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'lookback_days': LOOKBACK_DAYS,
        'tickers_scanned': len(tickers),
        'signals': results
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Results saved to {OUTPUT_FILE}")

    # Summary
    dumping = [t for t, d in results.items() if d['signal'] == 'dumping']
    accumulating = [t for t, d in results.items() if d['signal'] == 'accumulating']
    neutral = [t for t, d in results.items() if d['signal'] == 'neutral']

    print(f"\n{'='*50}")
    print(f"INSIDER SIGNAL SUMMARY")
    print(f"{'='*50}")
    print(f"🟢 Accumulating: {len(accumulating)} — {', '.join(accumulating) if accumulating else 'none'}")
    print(f"⚪ Neutral:      {len(neutral)}")
    print(f"🔴 Dumping:      {len(dumping)} — {', '.join(dumping) if dumping else 'none'}")

    if alerts:
        print(f"\n🚨 ALERTS:")
        for a in alerts:
            print(f"  {a}")

    # Build and send email report
    send_email_report(results, dumping, accumulating, neutral)


def send_email_report(results, dumping, accumulating, neutral):
    """Send insider scan results as a formatted HTML email"""
    scan_date = datetime.now().strftime('%b %d, %Y')

    html = f"""<html><body style="font-family: -apple-system, Arial, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 20px;">
<div style="max-width: 700px; margin: 0 auto;">
<h1 style="color: #fff; border-bottom: 2px solid #ef4444; padding-bottom: 10px;">
🔍 Insider Transaction Report — {scan_date}</h1>

<div style="display: flex; gap: 20px; margin: 20px 0;">
  <div style="background: rgba(239,68,68,0.15); border: 1px solid #ef4444; border-radius: 8px; padding: 15px; flex: 1; text-align: center;">
    <div style="font-size: 2rem; font-weight: 800; color: #ef4444;">{len(dumping)}</div>
    <div style="color: #ef4444;">🔴 Dumping</div>
  </div>
  <div style="background: rgba(200,200,200,0.1); border: 1px solid #666; border-radius: 8px; padding: 15px; flex: 1; text-align: center;">
    <div style="font-size: 2rem; font-weight: 800; color: #999;">{len(neutral)}</div>
    <div style="color: #999;">⚪ Neutral</div>
  </div>
  <div style="background: rgba(16,185,129,0.15); border: 1px solid #10b981; border-radius: 8px; padding: 15px; flex: 1; text-align: center;">
    <div style="font-size: 2rem; font-weight: 800; color: #10b981;">{len(accumulating)}</div>
    <div style="color: #10b981;">🟢 Accumulating</div>
  </div>
</div>
"""

    # Sort dumping by severity
    sorted_dumping = sorted(dumping, key=lambda t: results[t]['ins_score'])

    if sorted_dumping:
        html += """<h2 style="color: #ef4444; margin-top: 30px;">🔴 Insider Dumping Signals</h2>
<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
<tr style="background: #1a1a1a; color: #999; text-align: left;">
  <th style="padding: 10px; border-bottom: 1px solid #333;">Ticker</th>
  <th style="padding: 10px; border-bottom: 1px solid #333;">INS</th>
  <th style="padding: 10px; border-bottom: 1px solid #333;">Sells</th>
  <th style="padding: 10px; border-bottom: 1px solid #333;">$ Sold</th>
  <th style="padding: 10px; border-bottom: 1px solid #333;">Key Details</th>
</tr>"""
        for ticker in sorted_dumping:
            d = results[ticker]
            sell_val = d.get('total_sell_value', 0)
            sell_str = f"${sell_val/1e6:.1f}M" if sell_val >= 1e6 else f"${sell_val:,.0f}"
            # Top 3 reasons
            top_reasons = d['reasons'][:3]
            reasons_html = '<br>'.join(f"• {r}" for r in top_reasons)
            bg = '#1a0000' if d['ins_score'] <= -10 else '#111'
            html += f"""<tr style="background: {bg}; border-bottom: 1px solid #222;">
  <td style="padding: 10px; font-weight: 700; color: #fff;">{ticker}</td>
  <td style="padding: 10px; color: #ef4444; font-weight: 700;">{d['ins_score']:+d}</td>
  <td style="padding: 10px;">{d['sells']}</td>
  <td style="padding: 10px; color: #ef4444;">{sell_str}</td>
  <td style="padding: 10px; font-size: 0.8rem; color: #ccc;">{reasons_html}</td>
</tr>"""
        html += "</table>"

    if accumulating:
        html += """<h2 style="color: #10b981; margin-top: 30px;">🟢 Insider Accumulating</h2>
<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
<tr style="background: #1a1a1a; color: #999; text-align: left;">
  <th style="padding: 10px;">Ticker</th><th style="padding: 10px;">INS</th>
  <th style="padding: 10px;">Buys</th><th style="padding: 10px;">Details</th>
</tr>"""
        for ticker in accumulating:
            d = results[ticker]
            reasons_html = '<br>'.join(f"• {r}" for r in d['reasons'][:3])
            html += f"""<tr style="border-bottom: 1px solid #222;">
  <td style="padding: 10px; font-weight: 700; color: #10b981;">{ticker}</td>
  <td style="padding: 10px; color: #10b981; font-weight: 700;">{d['ins_score']:+d}</td>
  <td style="padding: 10px;">{d['buys']}</td>
  <td style="padding: 10px; font-size: 0.8rem;">{reasons_html}</td>
</tr>"""
        html += "</table>"

    if neutral:
        html += f"""<h2 style="color: #999; margin-top: 30px;">⚪ Neutral ({len(neutral)} stocks)</h2>
<p style="color: #666;">{', '.join(sorted(neutral))}</p>"""

    html += """
<hr style="border-color: #333; margin-top: 30px;">
<p style="color: #666; font-size: 0.75rem;">
Source: SEC EDGAR Form 4 filings (90-day lookback) · INS = Insider Net Score · 
Scoring: cluster ±3, C-suite ±2/person, officer/director ±1/person, heavy sell (&gt;25%) -2, all sells no buys -2<br>
⚠️ Many routine sales are 10b5-1 pre-planned. Focus on cluster sells and heavy % dumps.
</p>
</div></body></html>"""

    # Save HTML report
    report_path = os.path.join(WORKSPACE, 'reports', 'latest_insider_report.html')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(html)
    print(f"\n📄 HTML report saved to {report_path}")

    # Send email
    try:
        import configparser
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        config = configparser.ConfigParser()
        config.read(os.path.join(WORKSPACE, '.email_config.ini'))
        smtp_cfg = config['smtp']

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🔍 Insider Report: {len(dumping)} dumping, {len(accumulating)} accumulating — {scan_date}'
        msg['From'] = smtp_cfg.get('from', smtp_cfg.get('from_email', smtp_cfg.get('username')))
        msg['To'] = 'dbirru@gmail.com'
        msg.attach(MIMEText(html, 'html'))

        server = smtplib.SMTP(smtp_cfg.get('host', smtp_cfg.get('server')), int(smtp_cfg['port']))
        server.starttls()
        server.login(smtp_cfg['username'], smtp_cfg['password'])
        server.send_message(msg)
        server.quit()
        print("📧 Email report sent to dbirru@gmail.com!")
    except Exception as e:
        print(f"⚠️ Email send failed: {e}")


if __name__ == '__main__':
    main()

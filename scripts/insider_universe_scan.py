#!/usr/bin/env python3
"""
InvestIQ Universe-Wide Insider Scan
Scans ALL stocks in all_stocks.json for insider activity.
Attaches INS (Insider Net Score) to each stock.

Two-tier approach for speed:
  Tier 1: Fetch submissions JSON — count Form 4 filings (fast, 1 req/ticker)
  Tier 2: Deep XML parse for stocks with 3+ filings (detailed scoring)

Output: data/insider_universe.json (ticker -> INS score + details)
Also patches data/all_stocks.json with ins_score field.

Designed to run as daily cron after market close.
"""

import urllib.request
import json
import xml.etree.ElementTree as ET
import os
import re
import time
import sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_STOCKS_FILE = os.path.join(WORKSPACE, 'data', 'all_stocks.json')
OUTPUT_FILE = os.path.join(WORKSPACE, 'data', 'insider_universe.json')
CIK_CACHE_FILE = os.path.join(WORKSPACE, 'data', 'cik_cache.json')
SEC_USER_AGENT = 'InvestIQ ***REMOVED***'
LOOKBACK_DAYS = 90

# Rate limiting
SEC_RATE_LIMIT = 8  # requests per second (SEC allows 10, we stay under)
_last_request_time = 0


def rate_limited_fetch(url):
    """Fetch URL with SEC rate limiting"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    min_interval = 1.0 / SEC_RATE_LIMIT
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    
    req = urllib.request.Request(url, headers={'User-Agent': SEC_USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=15)
    _last_request_time = time.time()
    return resp


def load_cik_cache():
    if os.path.exists(CIK_CACHE_FILE):
        with open(CIK_CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cik_cache(cache):
    with open(CIK_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def build_cik_map():
    """Build complete ticker -> CIK mapping from SEC"""
    cache = load_cik_cache()
    if len(cache) > 500:
        return cache  # Already built
    
    print("  Fetching SEC company tickers list...")
    try:
        resp = rate_limited_fetch('https://www.sec.gov/files/company_tickers.json')
        data = json.loads(resp.read())
        for _, entry in data.items():
            ticker = entry.get('ticker', '').upper()
            cik = str(entry.get('cik_str', '')).zfill(10)
            cache[ticker] = cik
        save_cik_cache(cache)
        print(f"  Cached {len(cache)} CIKs")
    except Exception as e:
        print(f"  ⚠️ CIK fetch failed: {e}")
    return cache


def tier1_count_filings(cik, cutoff_date):
    """Tier 1: Quick count of Form 4 filings from submissions JSON"""
    try:
        resp = rate_limited_fetch(f'https://data.sec.gov/submissions/CIK{cik}.json')
        data = json.loads(resp.read())
        
        filings = data.get('filings', {}).get('recent', {})
        forms = filings.get('form', [])
        dates = filings.get('filingDate', [])
        accessions = filings.get('accessionNumber', [])
        
        form4s = []
        for i, form in enumerate(forms):
            if form == '4' and i < len(dates) and dates[i] >= cutoff_date:
                form4s.append({
                    'date': dates[i],
                    'accession': accessions[i]
                })
        
        return form4s
    except Exception:
        return []


def tier2_parse_filing(cik, accession):
    """Tier 2: Parse a single Form 4 XML for transaction details"""
    try:
        acc_clean = accession.replace('-', '')
        cik_int = str(int(cik))
        
        index_url = f'https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{accession}-index.htm'
        resp = rate_limited_fetch(index_url)
        content = resp.read().decode()
        
        xml_files = re.findall(r'href="(/Archives/edgar/data/[^"]+\.xml)"', content)
        raw_xmls = [f for f in xml_files if 'xsl' not in f.lower()]
        if not raw_xmls:
            return None
        
        xml_url = f'https://www.sec.gov{raw_xmls[0]}'
        resp2 = rate_limited_fetch(xml_url)
        root = ET.fromstring(resp2.read().decode())
        
        owner_el = root.find('.//reportingOwner')
        owner_name = 'Unknown'
        owner_title = ''
        is_officer = False
        is_director = False
        is_c_suite = False
        
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
            is_c_suite = any(t in title_lower for t in ['ceo', 'cfo', 'chief executive', 'chief financial',
                                                         'president', 'chairman'])
        
        transactions = []
        for txn in root.findall('.//nonDerivativeTransaction'):
            code_el = txn.find('.//transactionCoding/transactionCode')
            txn_code = code_el.text if code_el is not None else ''
            if txn_code not in ('S', 'P'):
                continue
            
            shares_el = txn.find('.//transactionAmounts/transactionShares/value')
            price_el = txn.find('.//transactionAmounts/transactionPricePerShare/value')
            owned_after_el = txn.find('.//postTransactionAmounts/sharesOwnedFollowingTransaction/value')
            date_el = txn.find('.//transactionDate/value')
            
            try:
                shares = float(shares_el.text) if shares_el is not None else 0
                price = float(price_el.text) if price_el is not None and price_el.text else 0
                owned_after = float(owned_after_el.text) if owned_after_el is not None else 0
            except (ValueError, TypeError):
                shares, price, owned_after = 0, 0, 0
            
            is_buy = txn_code == 'P'
            pct_sold = 0
            if not is_buy and owned_after > 0 and shares > 0:
                pct_sold = round(shares / (owned_after + shares) * 100, 1)
            
            transactions.append({
                'type': 'BUY' if is_buy else 'SELL',
                'shares': shares,
                'value': round(shares * price, 0),
                'pct_of_holdings': pct_sold,
                'owner': owner_name,
                'title': owner_title,
                'is_officer': is_officer,
                'is_director': is_director,
                'is_c_suite': is_c_suite
            })
        
        return transactions
    except Exception:
        return None


def calculate_ins_score(all_transactions):
    """Calculate Insider Net Score per unique person"""
    if not all_transactions:
        return 0, 'neutral', []
    
    score = 0
    reasons = []
    buys = [t for t in all_transactions if t['type'] == 'BUY']
    sells = [t for t in all_transactions if t['type'] == 'SELL']
    
    unique_buyers = {}
    for t in buys:
        name = t['owner']
        if name not in unique_buyers:
            unique_buyers[name] = {'total_value': 0, 'is_c_suite': t['is_c_suite'],
                                    'is_officer': t['is_officer'], 'is_director': t['is_director'],
                                    'title': t['title']}
        unique_buyers[name]['total_value'] += t['value']
    
    unique_sellers = {}
    for t in sells:
        name = t['owner']
        if name not in unique_sellers:
            unique_sellers[name] = {'total_value': 0, 'is_c_suite': t['is_c_suite'],
                                     'is_officer': t['is_officer'], 'is_director': t['is_director'],
                                     'title': t['title'], 'max_pct_sold': 0}
        unique_sellers[name]['total_value'] += t['value']
        if t['pct_of_holdings'] > unique_sellers[name]['max_pct_sold']:
            unique_sellers[name]['max_pct_sold'] = t['pct_of_holdings']
    
    if len(unique_buyers) >= 3:
        score += 3
        reasons.append(f"Cluster buy: {len(unique_buyers)} insiders")
    if len(unique_sellers) >= 3:
        score -= 3
        reasons.append(f"Cluster sell: {len(unique_sellers)} insiders")
    
    for name, info in unique_buyers.items():
        if info['is_c_suite']:
            score += 2
            reasons.append(f"C-suite buy: {name}")
        elif info['is_officer'] or info['is_director']:
            score += 1
    
    for name, info in unique_sellers.items():
        if info['is_c_suite']:
            score -= 2
            reasons.append(f"C-suite sell: {name}")
        elif info['is_officer'] or info['is_director']:
            score -= 1
    
    total_buy = sum(info['total_value'] for info in unique_buyers.values())
    if total_buy > 1_000_000:
        score += 2
        reasons.append(f"Large buys: ${total_buy:,.0f}")
    elif total_buy > 500_000:
        score += 1
    
    heavy = [n for n, i in unique_sellers.items() if i['max_pct_sold'] > 25]
    if heavy:
        score -= 2
        reasons.append(f"Heavy dumps: {', '.join(heavy[:3])}")
    
    if unique_sellers and not unique_buyers:
        score -= 2
        reasons.append("All sells, zero buys")
    
    signal = 'accumulating' if score >= 3 else ('dumping' if score <= -3 else 'neutral')
    return score, signal, reasons


def main():
    start_time = time.time()
    print(f"🔍 InvestIQ Universe Insider Scan")
    print(f"   Lookback: {LOOKBACK_DAYS} days | Source: SEC EDGAR Form 4")
    
    # Load all stocks
    with open(ALL_STOCKS_FILE) as f:
        all_data = json.load(f)
    stocks = all_data['stocks']
    
    # Filter to individual stocks only (skip ETFs)
    etf_tickers = {'VOO', 'XLI', 'GLD', 'GLDM', 'COPX', 'SIL', 'NLR', 'DXJ',
                   'INDA', 'XBI', 'VGT', 'VUG', 'UFO', 'GRID', 'ITA', 'SHLD', 'EUAD',
                   'SPY', 'QQQ', 'IWM', 'XLK', 'XLF', 'XLE', 'XLV', 'XLB', 'XLRE',
                   'XLY', 'XLP', 'XLU', 'XLC'}
    tickers = [t for t in stocks.keys() if t not in etf_tickers]
    print(f"   Scanning {len(tickers)} stocks\n")
    
    # Build CIK map
    cik_map = build_cik_map()
    cutoff = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    
    # ═══ TIER 1: Count Form 4 filings for all stocks ═══
    print(f"\n📋 Tier 1: Counting Form 4 filings...")
    tier1_results = {}
    no_cik = 0
    errors = 0
    
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0 or i == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(tickers) - i) / rate / 60 if rate > 0 else 0
            print(f"  [{i+1}/{len(tickers)}] {ticker}... ({rate:.1f}/sec, ETA: {eta:.0f}min)")
        
        cik = cik_map.get(ticker)
        if not cik:
            no_cik += 1
            tier1_results[ticker] = {'filings': 0, 'accessions': []}
            continue
        
        try:
            form4s = tier1_count_filings(cik, cutoff)
            tier1_results[ticker] = {
                'filings': len(form4s),
                'accessions': [f['accession'] for f in form4s[:15]],  # Cap at 15 for deep scan
                'cik': cik
            }
        except Exception:
            errors += 1
            tier1_results[ticker] = {'filings': 0, 'accessions': []}
    
    print(f"\n  ✅ Tier 1 complete: {len(tier1_results)} stocks scanned, {no_cik} no CIK, {errors} errors")
    
    # Stats
    with_filings = {t: r for t, r in tier1_results.items() if r['filings'] > 0}
    print(f"  📊 {len(with_filings)} stocks have Form 4 filings in last {LOOKBACK_DAYS} days")
    
    # ═══ TIER 2: Deep parse stocks with 3+ filings ═══
    deep_scan_tickers = [t for t, r in tier1_results.items() if r['filings'] >= 3]
    print(f"\n🔬 Tier 2: Deep parsing {len(deep_scan_tickers)} stocks with 3+ filings...")
    
    results = {}
    
    for i, ticker in enumerate(deep_scan_tickers):
        if (i + 1) % 20 == 0 or i == 0:
            print(f"  [{i+1}/{len(deep_scan_tickers)}] {ticker} ({tier1_results[ticker]['filings']} filings)...")
        
        cik = tier1_results[ticker].get('cik')
        accessions = tier1_results[ticker].get('accessions', [])
        
        all_transactions = []
        for acc in accessions[:10]:  # Parse max 10 filings per ticker
            txns = tier2_parse_filing(cik, acc)
            if txns:
                all_transactions.extend(txns)
        
        score, signal, reasons = calculate_ins_score(all_transactions)
        
        buys = [t for t in all_transactions if t['type'] == 'BUY']
        sells = [t for t in all_transactions if t['type'] == 'SELL']
        
        results[ticker] = {
            'ins_score': score,
            'signal': signal,
            'filings': tier1_results[ticker]['filings'],
            'buys': len(buys),
            'sells': len(sells),
            'total_sell_value': sum(t['value'] for t in sells),
            'total_buy_value': sum(t['value'] for t in buys),
            'reasons': reasons[:5]
        }
    
    # Add tier-1-only stocks (0-2 filings) with quick scores
    for ticker in tickers:
        if ticker not in results:
            filings = tier1_results.get(ticker, {}).get('filings', 0)
            if filings == 0:
                results[ticker] = {
                    'ins_score': 0, 'signal': 'neutral', 'filings': 0,
                    'buys': 0, 'sells': 0, 'total_sell_value': 0, 'total_buy_value': 0,
                    'reasons': ['No Form 4 filings in period']
                }
            else:
                # 1-2 filings: can't tell much, mark neutral
                results[ticker] = {
                    'ins_score': 0, 'signal': 'neutral', 'filings': filings,
                    'buys': 0, 'sells': 0, 'total_sell_value': 0, 'total_buy_value': 0,
                    'reasons': [f'{filings} filings (below deep-scan threshold)']
                }
    
    # ═══ Save Results ═══
    output = {
        'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'lookback_days': LOOKBACK_DAYS,
        'tickers_scanned': len(tickers),
        'deep_scanned': len(deep_scan_tickers),
        'signals': results
    }
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ Universe insider data saved to {OUTPUT_FILE}")
    
    # ═══ Patch all_stocks.json with INS scores ═══
    patched = 0
    for ticker, stock in stocks.items():
        if ticker in results:
            stock['ins_score'] = results[ticker]['ins_score']
            stock['insider_signal'] = results[ticker]['signal']
            patched += 1
        else:
            stock['ins_score'] = 0
            stock['insider_signal'] = 'neutral'
    
    with open(ALL_STOCKS_FILE, 'w') as f:
        json.dump(all_data, f, indent=2)
    print(f"📊 Patched {patched} stocks in all_stocks.json with INS scores")
    
    # ═══ Summary ═══
    dumping = sorted([t for t, d in results.items() if d['signal'] == 'dumping'],
                     key=lambda t: results[t]['ins_score'])
    accumulating = sorted([t for t, d in results.items() if d['signal'] == 'accumulating'],
                          key=lambda t: -results[t]['ins_score'])
    neutral = [t for t, d in results.items() if d['signal'] == 'neutral']
    
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"UNIVERSE INSIDER SCAN SUMMARY ({elapsed/60:.1f} min)")
    print(f"{'='*60}")
    print(f"🟢 Accumulating: {len(accumulating)}")
    if accumulating[:10]:
        for t in accumulating[:10]:
            d = results[t]
            print(f"   {t:6s} INS={d['ins_score']:+3d}  {'; '.join(d['reasons'][:2])}")
    
    print(f"\n⚪ Neutral: {len(neutral)}")
    
    print(f"\n🔴 Dumping: {len(dumping)}")
    if dumping[:15]:
        for t in dumping[:15]:
            d = results[t]
            sell_str = f"${d['total_sell_value']/1e6:.1f}M" if d['total_sell_value'] >= 1e6 else f"${d['total_sell_value']:,.0f}"
            print(f"   {t:6s} INS={d['ins_score']:+3d}  sold {sell_str}  {'; '.join(d['reasons'][:2])}")
    
    # Git commit
    print(f"\n📦 Committing to git...")
    os.system(f'cd {WORKSPACE} && git add data/insider_universe.json data/all_stocks.json data/cik_cache.json && '
              f'git commit -m "Auto: universe insider scan $(date +%Y-%m-%d)" && '
              f'git push origin main')
    
    print(f"\n🏁 Done in {elapsed/60:.1f} minutes")


if __name__ == '__main__':
    main()

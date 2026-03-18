#!/usr/bin/env python3
"""
InvestIQ Fundamentals Refresh
==============================
Single source of truth for keeping fundamental data up to date.
Runs as part of the daily pipeline (after price cache, before scoring).

Data sources (in priority order):
  1. SEC EDGAR bulk data (data/sec_fundamentals.json) — historical, no rate limits
  2. yfinance — current-quarter data, fundamentals snapshot

Responsibilities:
  1. Ensure quarterly_revenue has 8+ quarters per stock
  2. Ensure quarterly_eps has 8+ quarters per stock
  3. Compute derived fields that yfinance stopped returning (pegRatio, etc.)
  4. Validate coverage after refresh and report gaps
  5. Update sec_fundamentals.json from SEC EDGAR quarterly when needed

Run: python3 scripts/refresh_fundamentals.py
     python3 scripts/refresh_fundamentals.py --validate-only
     python3 scripts/refresh_fundamentals.py --sec-update   (re-download SEC data)
"""

import os
import sys
import json
import sqlite3
import argparse
import requests
import zipfile
import io
import time
import logging
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

DB_PATH = os.path.join(WORKSPACE, 'data/market_data.db')
SEC_PATH = os.path.join(WORKSPACE, 'data/sec_fundamentals.json')
MAX_WORKERS = 8
REQUIRED_QUARTERS = 8  # minimum for TTM-vs-TTM comparisons

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ── Schema setup ─────────────────────────────────────────────────────────────

def ensure_schema(conn):
    """Create tables if they don't exist."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS quarterly_revenue (
            symbol TEXT NOT NULL,
            year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            revenue REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, year, quarter)
        );
        CREATE TABLE IF NOT EXISTS quarterly_eps (
            symbol TEXT NOT NULL,
            year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            eps REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, year, quarter)
        );
    ''')
    conn.commit()


# ── SEC fundamentals backfill ─────────────────────────────────────────────────

def backfill_from_sec(conn, sec_data):
    """
    Populate quarterly_revenue and quarterly_eps from sec_fundamentals.json.
    This is the primary historical data source — fast, no rate limits.
    """
    c = conn.cursor()
    rev_written = eps_written = 0

    for symbol, data in sec_data.items():
        # Revenue
        for entry in data.get('revenue', []):
            end_date = entry.get('end') or entry.get('date')
            val = entry.get('val')
            form = entry.get('form', '')
            frame = entry.get('frame', '')
            if not end_date or not val or val <= 0:
                continue
            if form == '10-K' or ('Q' not in frame and 'CY20' in frame):
                continue  # skip annual rows
            dt = pd.Timestamp(end_date)
            c.execute('''
                INSERT OR REPLACE INTO quarterly_revenue
                (symbol, year, quarter, revenue, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (symbol, dt.year, (dt.month - 1) // 3 + 1, float(val)))
            rev_written += 1

        # EPS
        for entry in data.get('eps', []):
            end_date = entry.get('end') or entry.get('date')
            val = entry.get('val')
            form = entry.get('form', '')
            frame = entry.get('frame', '')
            if not end_date or val is None:
                continue
            if form == '10-K' or ('Q' not in frame and 'CY20' in frame):
                continue
            dt = pd.Timestamp(end_date)
            c.execute('''
                INSERT OR REPLACE INTO quarterly_eps
                (symbol, year, quarter, eps, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (symbol, dt.year, (dt.month - 1) // 3 + 1, float(val)))
            eps_written += 1

    conn.commit()
    return rev_written, eps_written


# ── yfinance top-up (most recent quarters SEC may not have yet) ────────────────

def topup_from_yfinance(symbol, conn):
    """
    Fetch the most recent 4 quarters from yfinance to fill gaps
    SEC data may not yet have (new filings take weeks to appear).
    """
    c = conn.cursor()
    try:
        t = yf.Ticker(symbol)

        # Revenue top-up
        stmt = t.quarterly_income_stmt
        if stmt is not None and not stmt.empty and 'Total Revenue' in stmt.index:
            for date_col, val in stmt.loc['Total Revenue'].items():
                if pd.notna(val) and val > 0:
                    dt = pd.Timestamp(date_col)
                    c.execute('''
                        INSERT OR REPLACE INTO quarterly_revenue
                        (symbol, year, quarter, revenue, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (symbol, dt.year, (dt.month - 1) // 3 + 1, float(val)))

        # EPS top-up — prefer earnings_history (actual reported EPS, not estimated)
        eh = t.earnings_history
        if eh is not None and not eh.empty and 'epsActual' in eh.columns:
            for _, row in eh.iterrows():
                eps_val = row.get('epsActual')
                period = row.get('period') or row.name
                if pd.notna(eps_val) and period is not None:
                    try:
                        dt = pd.Timestamp(period)
                        c.execute('''
                            INSERT OR REPLACE INTO quarterly_eps
                            (symbol, year, quarter, eps, updated_at)
                            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ''', (symbol, dt.year, (dt.month - 1) // 3 + 1, float(eps_val)))
                    except Exception:
                        pass

        conn.commit()
        return True
    except Exception:
        return False


# ── Derived fields: compute what yfinance stopped returning ───────────────────

def compute_derived_fields(conn):
    """
    Patch fundamentals rows with computed derived fields:
      - pegRatio: forwardPE / (earningsGrowth * 100)
      - ttm_eps_growth: from quarterly_eps table
      - ttm_rev_growth: from quarterly_revenue (if not already populated)
    """
    c = conn.cursor()
    c.execute("SELECT symbol, data FROM fundamentals")
    rows = c.fetchall()
    updated = 0

    for symbol, data_str in rows:
        try:
            info = json.loads(data_str)
            changed = False

            # Compute and store pegRatio
            fwd_pe  = info.get('forwardPE')
            earn_g  = info.get('earningsGrowth')
            earn_qg = info.get('earningsQuarterlyGrowth')
            trail_pe = info.get('trailingPE')

            peg = None
            if fwd_pe and earn_g and earn_g > 0:
                peg = round(float(fwd_pe) / (float(earn_g) * 100), 4)
            elif trail_pe and earn_qg and earn_qg > 0:
                peg = round(float(trail_pe) / (float(earn_qg) * 100), 4)

            if peg is not None and info.get('pegRatio') != peg:
                info['pegRatio'] = peg
                changed = True

            # Compute TTM EPS growth from quarterly_eps and store as earningsGrowth
            # if the yfinance value is missing
            if not earn_g:
                c2 = conn.cursor()
                c2.execute('''
                    SELECT eps FROM quarterly_eps WHERE symbol=?
                    ORDER BY year DESC, quarter DESC LIMIT 8
                ''', (symbol,))
                eps_rows = [r[0] for r in c2.fetchall()]
                if len(eps_rows) >= 8:
                    ttm_curr = sum(eps_rows[:4])
                    ttm_prev = sum(eps_rows[4:8])
                    if ttm_prev != 0 and ttm_curr > 0 and ttm_prev > 0:
                        growth = (ttm_curr - ttm_prev) / abs(ttm_prev)
                        info['earningsGrowth'] = round(growth, 4)
                        # Recompute PEG with this growth
                        if fwd_pe or trail_pe:
                            pe = float(fwd_pe or trail_pe)
                            info['pegRatio'] = round(pe / (growth * 100), 4)
                        changed = True

            if changed:
                c.execute(
                    "UPDATE fundamentals SET data=?, updated_at=CURRENT_TIMESTAMP WHERE symbol=?",
                    (json.dumps(info), symbol)
                )
                updated += 1
        except Exception:
            continue

    conn.commit()
    return updated


# ── SEC EDGAR data refresh (quarterly) ───────────────────────────────────────

def refresh_sec_fundamentals(tickers=None):
    """
    Re-download SEC EDGAR company facts for tickers with stale data.
    Uses SEC EDGAR companyfacts API (free, no key required).
    Updates sec_fundamentals.json in place.
    """
    headers = {'User-Agent': 'InvestIQ research@investiq.com'}

    # Load current sec data
    if os.path.exists(SEC_PATH):
        with open(SEC_PATH) as f:
            sec_data = json.load(f)
    else:
        sec_data = {}

    # Load CIK map from DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT symbol, data FROM fundamentals")
    cik_map = {}
    for sym, data_str in c.fetchall():
        try:
            info = json.loads(data_str)
            cik = info.get('cik') or info.get('CIK')
            if cik:
                cik_map[sym] = str(cik).zfill(10)
        except Exception:
            pass
    conn.close()

    target_tickers = tickers or list(cik_map.keys())
    updated = 0

    for symbol in target_tickers:
        cik = cik_map.get(symbol)
        if not cik:
            continue
        try:
            url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                continue

            facts = r.json()
            us_gaap = facts.get('facts', {}).get('us-gaap', {})

            # Revenue: Revenues or RevenueFromContractWithCustomerExcludingAssessedTax
            rev_entries = []
            for rev_key in ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                            'SalesRevenueNet', 'SalesRevenueGoodsNet']:
                units = us_gaap.get(rev_key, {}).get('units', {}).get('USD', [])
                if units:
                    rev_entries = [
                        {'end': e['end'], 'val': e['val'],
                         'form': e.get('form', ''), 'frame': e.get('frame', '')}
                        for e in units if e.get('form') in ('10-Q', '10-K')
                    ]
                    break

            # EPS: EarningsPerShareBasic or EarningsPerShareDiluted
            eps_entries = []
            for eps_key in ['EarningsPerShareDiluted', 'EarningsPerShareBasic']:
                units = us_gaap.get(eps_key, {}).get('units', {}).get('USD/shares', [])
                if units:
                    eps_entries = [
                        {'end': e['end'], 'val': e['val'],
                         'form': e.get('form', ''), 'frame': e.get('frame', '')}
                        for e in units if e.get('form') in ('10-Q', '10-K')
                    ]
                    break

            if rev_entries or eps_entries:
                sec_data[symbol] = {
                    'revenue': rev_entries,
                    'eps': eps_entries,
                    'updated': date.today().isoformat()
                }
                updated += 1

            time.sleep(0.1)  # SEC rate limit: 10 req/sec max
        except Exception:
            continue

    with open(SEC_PATH, 'w') as f:
        json.dump(sec_data, f)

    logger.info(f"SEC fundamentals refreshed: {updated} tickers updated")
    return updated


# ── Validation ────────────────────────────────────────────────────────────────

def validate_coverage(conn):
    """
    Check coverage of all required fields. Returns a dict of field → coverage %.
    """
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM fundamentals")
    total = c.fetchone()[0]

    required = [
        'forwardPE', 'earningsGrowth', 'returnOnEquity', 'operatingMargins',
        'freeCashflow', 'marketCap', 'sector', 'pegRatio', 'revenueGrowth',
    ]

    coverage = {}
    for field in required:
        try:
            c.execute(f"SELECT COUNT(*) FROM fundamentals WHERE json_extract(data,'$.{field}') IS NOT NULL")
            present = c.fetchone()[0]
            coverage[field] = round(present / total * 100, 1) if total else 0
        except Exception:
            coverage[field] = 0

    # Quarterly data coverage
    c.execute("SELECT COUNT(DISTINCT symbol) FROM quarterly_revenue")
    rev_syms = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM quarterly_revenue WHERE (SELECT COUNT(*) FROM quarterly_revenue r2 WHERE r2.symbol=quarterly_revenue.symbol) >= 8")
    rev_8plus = c.fetchone()[0] // 8  # approx

    c.execute("SELECT COUNT(DISTINCT symbol) FROM quarterly_eps")
    eps_syms = c.fetchone()[0]

    c.execute("SELECT AVG(cnt) FROM (SELECT COUNT(*) cnt FROM quarterly_revenue GROUP BY symbol)")
    avg_rev = c.fetchone()[0] or 0
    c.execute("SELECT AVG(cnt) FROM (SELECT COUNT(*) cnt FROM quarterly_eps GROUP BY symbol)")
    avg_eps = c.fetchone()[0] or 0

    coverage['_quarterly_revenue_symbols'] = rev_syms
    coverage['_quarterly_eps_symbols'] = eps_syms
    coverage['_avg_revenue_quarters'] = round(avg_rev, 1)
    coverage['_avg_eps_quarters'] = round(avg_eps, 1)
    coverage['_total_stocks'] = total

    return coverage


def print_coverage(coverage):
    total = coverage.get('_total_stocks', 0)
    print(f"\n{'FIELD':<30} {'COVERAGE':>10}")
    print("-" * 44)
    fields = [k for k in coverage if not k.startswith('_')]
    for f in fields:
        pct = coverage[f]
        flag = " ⚠️" if pct < 70 else (" ❌" if pct < 40 else "")
        print(f"  {f:<28} {pct:>5.1f}%{flag}")
    print(f"\nQuarterly Revenue: {coverage['_quarterly_revenue_symbols']} stocks, "
          f"avg {coverage['_avg_revenue_quarters']:.1f} quarters")
    print(f"Quarterly EPS:     {coverage['_avg_eps_quarters']:.1f} avg quarters")
    print(f"Total stocks: {total}")


# ── Main ─────────────────────────────────────────────────────────────────────

def run(validate_only=False, sec_update=False, tickers=None):
    start = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    if validate_only:
        logger.info("Validate-only mode")
        cov = validate_coverage(conn)
        print_coverage(cov)
        conn.close()
        return cov

    logger.info("=== Fundamentals Refresh ===")

    # Step 1: Re-download SEC data if requested or stale
    if sec_update:
        logger.info("Step 1: Re-downloading SEC EDGAR data...")
        n = refresh_sec_fundamentals(tickers)
        logger.info(f"  Updated {n} tickers from SEC EDGAR")

    # Step 2: Backfill quarterly tables from SEC fundamentals JSON
    logger.info("Step 2: Backfilling quarterly data from SEC fundamentals...")
    if os.path.exists(SEC_PATH):
        with open(SEC_PATH) as f:
            sec_data = json.load(f)
        rev_written, eps_written = backfill_from_sec(conn, sec_data)
        logger.info(f"  Revenue rows: {rev_written}, EPS rows: {eps_written}")
    else:
        logger.warning("  sec_fundamentals.json not found — skipping SEC backfill")

    # Step 3: yfinance top-up for stocks with < REQUIRED_QUARTERS quarters
    logger.info("Step 3: yfinance top-up for stocks with insufficient history...")
    c = conn.cursor()
    c.execute('''
        SELECT symbol FROM fundamentals
        WHERE symbol NOT IN (
            SELECT symbol FROM quarterly_revenue
            GROUP BY symbol HAVING COUNT(*) >= ?
        )
        LIMIT 200
    ''', (REQUIRED_QUARTERS,))
    needs_topup = [r[0] for r in c.fetchall()]
    logger.info(f"  {len(needs_topup)} stocks need quarterly top-up")

    topup_ok = 0
    for sym in needs_topup[:100]:  # cap at 100 to avoid rate limits
        if topup_from_yfinance(sym, conn):
            topup_ok += 1
        time.sleep(0.2)
    logger.info(f"  Top-up complete: {topup_ok}/{len(needs_topup[:100])} succeeded")

    # Step 4: Compute derived fields (pegRatio, etc.)
    logger.info("Step 4: Computing derived fields (pegRatio, TTM growth)...")
    n_updated = compute_derived_fields(conn)
    logger.info(f"  Updated {n_updated} fundamentals rows with derived fields")

    # Step 5: Validate and report
    logger.info("Step 5: Validating coverage...")
    cov = validate_coverage(conn)
    print_coverage(cov)

    conn.close()
    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"Fundamentals refresh complete in {elapsed:.1f}s")
    return cov


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--sec-update', action='store_true',
                        help='Re-download SEC EDGAR data (slow, do weekly)')
    parser.add_argument('--ticker', nargs='+', help='Specific tickers to refresh')
    args = parser.parse_args()

    cov = run(
        validate_only=args.validate_only,
        sec_update=args.sec_update,
        tickers=args.ticker
    )

#!/usr/bin/env python3
"""
InvestIQ scan_all.py — Single-source-of-truth scan orchestrator.
Scoring lives in rater.py. EWROS computed separately by scripts/ewros.py.

Usage:
    python3 scan_all.py              # Full scan
    python3 scan_all.py --limit 5    # Test with first 5 tickers
"""
import argparse
import gc
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from utils.logger import get_logger
from rater import BreakoutRater

logger = get_logger('scan_all')

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def run_scan(limit=None):
    logger.info("🚀 Starting InvestIQ scan_all.py (unified scoring pipeline)...")
    
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT DISTINCT symbol FROM prices')
    tickers = [row[0] for row in c.fetchall()]
    
    if limit:
        tickers = tickers[:limit]
        logger.info(f"Limited to {limit} tickers (test mode)")
    
    logger.info(f"Found {len(tickers)} tickers to scan")
    
    rater = BreakoutRater()
    
    # Load existing EWROS + IQ Edge scores (computed separately, must be preserved across scans)
    ewros_scores = {}
    iq_edge_scores = {}
    iq_edge_raw_scores = {}
    try:
        with open('data/all_stocks.json') as f:
            prev = json.load(f)
        for t, s in prev.get('stocks', {}).items():
            ewros_scores[t] = s.get('ewros_score', 0)
            if s.get('iq_edge') is not None:
                iq_edge_scores[t] = s.get('iq_edge')
            if s.get('iq_edge_raw') is not None:
                iq_edge_raw_scores[t] = s.get('iq_edge_raw')
        logger.info(f"Loaded {len(ewros_scores)} EWROS scores, {len(iq_edge_scores)} IQ Edge scores")
    except:
        logger.warning("No previous all_stocks.json found, EWROS/IQ Edge scores will be empty")
    
    logger.info(f"Initialized BreakoutRater")
    
    # Pre-load quoteTypes to skip ETFs/funds from the rater
    etf_types = {'ETF', 'MUTUALFUND', 'MONEYMARKET'}
    quote_types = {}
    try:
        for row in conn.execute('SELECT symbol, data FROM fundamentals'):
            try:
                info = json.loads(row[1])
                qt = info.get('quoteType', '')
                if qt in etf_types:
                    quote_types[row[0]] = qt
            except Exception:
                pass
        logger.info(f"Detected {len(quote_types)} ETF/fund tickers to handle as stubs")
    except Exception as e:
        logger.warning(f"Could not pre-load quoteTypes: {e}")

    results = []
    errors = 0

    for i, ticker in enumerate(tickers, 1):
        try:
            # Skip ETFs — they get stub entries after the main loop
            if ticker in quote_types:
                continue

            data = rater.rate_stock_from_db(ticker, conn)
            if data is None:
                continue
            
            # Preserve externally-computed scores (ewros.py, iq_edge_predict.py)
            data['ewros_score'] = ewros_scores.get(ticker, data.get('ewros_score', 0))
            if ticker in iq_edge_scores:
                data['iq_edge'] = iq_edge_scores[ticker]
                data['iq_edge_raw'] = iq_edge_raw_scores.get(ticker)
            
            results.append(data)
        except Exception as e:
            errors += 1
            logger.error(f"Error scoring {ticker}: {e}")
        
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(tickers)} ({len(results)} scored, {errors} errors)...")
    
    # ── ETF stub entries ────────────────────────────────────────────────────
    # Portfolio ETFs don't have fundamental data, so rater returns None for them.
    # Create minimal "ETF mode" entries so they appear in all_stocks.json,
    # get EWROS scores, and the detail view can show their chart.
    conn_etf = sqlite3.connect(config.DB_PATH)
    # Build ETF stub entries for ALL ETFs in the DB (not just portfolio)
    # — covers portfolio ETFs + any other ETFs that happen to be in the DB
    etf_candidates = set(quote_types.keys()) | {t for t in config.ALL_HOLDINGS if t not in {r['ticker'] for r in results}}
    scored_tickers = {r['ticker'] for r in results}
    etf_stubs = []
    for ticker in etf_candidates:
        if ticker in scored_tickers:
            continue
        try:
            c_etf = conn_etf.cursor()
            c_etf.execute('SELECT data FROM fundamentals WHERE symbol=?', (ticker,))
            row = c_etf.fetchone()
            if not row:
                continue
            info = json.loads(row[0])
            # Only include if genuinely ETF/fund
            if info.get('quoteType') not in etf_types and info.get('sector') not in (None, 'N/A', ''):
                continue
            # Need enough price rows for EWROS
            c_etf.execute('SELECT COUNT(*) FROM prices WHERE symbol=?', (ticker,))
            n_rows = c_etf.fetchone()[0]
            if n_rows < 63:
                continue
            stub = {
                "ticker": ticker,
                "name": info.get('longName') or info.get('shortName', ticker),
                "sector": "ETF",
                "industry": info.get('category') or info.get('quoteType', 'ETF'),
                "score": None,
                "grade": "ETF",
                "max_score": None,
                "technical_score": None,
                "growth_score": None,
                "quality_score": None,
                "context_score": None,
                "moonshot_score": None,
                "criteria": [],
                "market_cap": info.get('totalAssets'),
                "revenue_growth": None,
                "earnings_growth": None,
                "forward_pe": None,
                "trailing_pe": None,
                "peg_ratio": None,
                "recommendation": None,
                "target_mean": None,
                "analyst_count": None,
                "current_price": info.get('regularMarketPrice') or info.get('navPrice'),
                "ewros_score": ewros_scores.get(ticker, 0),
                "ewros_raw": 0,
                "ewros_trend": 0,
                "ewros_prior": 0,
                "ewros_stats": {},
                "iq_edge": iq_edge_scores.get(ticker),
                "iq_edge_raw": iq_edge_raw_scores.get(ticker),
            }
            etf_stubs.append(stub)
            logger.info(f"  ETF stub: {ticker} ({stub['name']})")
        except Exception as e:
            logger.warning(f"ETF stub failed for {ticker}: {e}")
    conn_etf.close()

    if etf_stubs:
        logger.info(f"Added {len(etf_stubs)} ETF stub entries")
        results.extend(etf_stubs)
    # ────────────────────────────────────────────────────────────────────────

    conn.close()

    # Filter & sort (ETFs with score=None are excluded from top_stocks but kept in all_stocks)
    filtered = [r for r in results if r.get('score') is not None and r['score'] >= 55]
    results.sort(key=lambda x: (x.get('score') is None, -(x.get('score') or 0)))
    filtered.sort(key=lambda x: x['score'], reverse=True)
    
    # top_stocks.json — filtered, top 100, list format
    top_output = {
        'version': '5.0',
        'max_score': 100,
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'total_stocks': len(filtered),
        'stocks': filtered[:100]
    }
    
    # In test mode (--limit), write to /tmp to avoid overwriting production data
    top_path = '/tmp/top_stocks_test.json' if limit else 'data/top_stocks.json'
    with open(top_path, 'w') as f:
        json.dump(top_output, f, indent=2, cls=NumpyEncoder)
    
    # all_stocks.json — all stocks, dict keyed by ticker
    top_tickers = set(s['ticker'] for s in filtered)
    portfolio_tickers = set(config.ALL_HOLDINGS)
    keep_criteria = top_tickers | portfolio_tickers
    
    all_stocks_slim = {}
    for s in results:
        is_etf = s.get('grade') == 'ETF'
        if s['ticker'] in keep_criteria or is_etf:
            all_stocks_slim[s['ticker']] = s
        else:
            slim = {k: v for k, v in s.items() if k != 'criteria'}
            all_stocks_slim[s['ticker']] = slim
    
    all_output = {
        'version': '5.1',
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'total_stocks': len(results),
        'stocks': all_stocks_slim
    }
    
    total_count = len(results)
    del results
    gc.collect()
    
    all_path = '/tmp/all_stocks_test.json' if limit else 'data/all_stocks.json'
    with open(all_path, 'w') as f:
        json.dump(all_output, f, indent=2, cls=NumpyEncoder)
    
    logger.info(f"✅ Saved {len(filtered)} top stocks to top_stocks.json")
    logger.info(f"   Saved {total_count} total stocks to all_stocks.json")
    logger.info(f"   Errors: {errors}")
    
    print(f"✅ Scan complete: {len(filtered)} top stocks, {total_count} total, {errors} errors")
    if filtered:
        print(f"   Top 5: {', '.join([s['ticker'] + ' ' + str(s['score']) for s in filtered[:5]])}")
    
    # Git commit
    if not limit:
        try:
            subprocess.run(['git', 'add', 'data/top_stocks.json', 'data/all_stocks.json'], check=True)
            subprocess.run(['git', 'commit', '-m', f'scan: {len(filtered)} top stocks, {total_count} total'], check=True)
            subprocess.run(['git', 'push'], check=True)
            logger.info("Git push complete")
        except Exception as e:
            logger.warning(f"Git push failed: {e}")
    
    print("\n⚠️  NOTE: Update cron job from 'python3 update_web_scan.py' to 'python3 scan_all.py'")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='InvestIQ full stock scan')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of tickers (for testing)')
    args = parser.parse_args()
    run_scan(limit=args.limit)

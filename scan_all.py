#!/usr/bin/env python3
"""
InvestIQ scan_all.py — Single-source-of-truth scan orchestrator.
Replaces update_web_scan.py. Scoring lives in rater.py + rotation_catcher.py.

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
from rotation_catcher import RotationCatcher

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
    rc = RotationCatcher()
    logger.info("Initialized BreakoutRater + RotationCatcher")
    
    results = []
    errors = 0
    
    for i, ticker in enumerate(tickers, 1):
        try:
            data = rater.rate_stock_from_db(ticker, conn)
            if data is None:
                continue
            
            # Add rotation score
            try:
                rot = rc.score(ticker)
                data['rotation_score'] = rot['composite_score']
                data['rotation_signal'] = rot['signal']
                data['rotation_convergence'] = rot['convergence_bonus']
            except Exception as e:
                logger.warning(f"Rotation failed for {ticker}: {e}")
                data['rotation_score'] = 0
                data['rotation_signal'] = 'NO DATA'
                data['rotation_convergence'] = 0
            
            results.append(data)
        except Exception as e:
            errors += 1
            logger.error(f"Error scoring {ticker}: {e}")
        
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(tickers)} ({len(results)} scored, {errors} errors)...")
    
    conn.close()
    
    # Filter & sort
    filtered = [r for r in results if r['score'] >= 55]
    results.sort(key=lambda x: x['score'], reverse=True)
    filtered.sort(key=lambda x: x['score'], reverse=True)
    
    # top_stocks.json — filtered, top 100, list format
    top_output = {
        'version': '5.0',
        'max_score': 100,
        'last_scan': datetime.now().strftime('%Y-%m-%d %H:%M PST'),
        'total_stocks': len(filtered),
        'stocks': filtered[:100]
    }
    
    with open('top_stocks.json', 'w') as f:
        json.dump(top_output, f, indent=2, cls=NumpyEncoder)
    
    # all_stocks.json — all stocks, dict keyed by ticker
    top_tickers = set(s['ticker'] for s in filtered)
    portfolio_tickers = set(config.ALL_HOLDINGS)
    keep_criteria = top_tickers | portfolio_tickers
    
    all_stocks_slim = {}
    for s in results:
        if s['ticker'] in keep_criteria:
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
    
    with open('all_stocks.json', 'w') as f:
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
            subprocess.run(['git', 'add', 'top_stocks.json', 'all_stocks.json'], check=True)
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

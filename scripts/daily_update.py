#!/usr/bin/env python3
"""
InvestIQ Daily Update Orchestrator
====================================
Single entry point for ALL nightly data downloads and calculations.
Replaces 8 individual cron jobs with one script, one cron.

Run via cron after market close (4:30 PM ET Mon-Fri):
  cron 30 16 * * 1-5 @ America/New_York

Order of operations:
  1. refresh_cache.py            — Download fresh prices + fundamentals → SQLite DB
  2. scan_all.py                 — Score all stocks from DB → all_stocks.json, top_stocks.json
  3. scripts/ewros.py            — Compute EWROS scores + stats → update all_stocks.json
  4. scripts/iq_edge_predict.py  — IQ Edge ML predictions
  5. generate_watchlist.py       — Rebuild watchlist.json
  6. Merge EWROS → top_stocks    — Backfill ewros_stats into top_stocks.json
  7. reports/distribution_scan.py  — Detect institutional selling patterns
  8. reports/sector_drivers.py     — Sector leaderboard + email
  9. scripts/earnings_calendar.py  — Update earnings calendar
 10. scripts/earnings_recap.py     — Earnings recap email
 11. scripts/sell_signal_check.py  — Check sell signals → alerts
 12. scripts/insider_scan.py       — Fetch SEC Form 4 insider data
 13. Git commit + push             — Publish all fresh data to GitHub Pages

Usage:
  python3 scripts/daily_update.py
  python3 scripts/daily_update.py --skip-cache    # Skip slow DB refresh
  python3 scripts/daily_update.py --skip-git      # Don't commit/push
  python3 scripts/daily_update.py --dry-run       # Print steps, do nothing
  python3 scripts/daily_update.py --only scan ewros merge  # Run specific steps only
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

TELEGRAM_CHAT_ID = '690660528'
OPENCLAW_API     = 'http://localhost:18789/api/message/send'


def send_telegram(message):
    """Send a Telegram message via OpenClaw gateway. Silent on failure."""
    try:
        payload = json.dumps({
            'channel': 'telegram',
            'to': TELEGRAM_CHAT_ID,
            'message': message
        }).encode()
        req = urllib.request.Request(
            OPENCLAW_API, data=payload,
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f'  [telegram] send failed: {e}')

# ── Color helpers ─────────────────────────────────────────────────────────────

RESET  = '\033[0m'
BOLD   = '\033[1m'
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
CYAN   = '\033[96m'
DIM    = '\033[2m'

def hdr(n, total, name):
    print(f'\n{BOLD}{CYAN}[{n}/{total}] {name}{RESET}')

def ok(msg):    print(f'  {GREEN}✓{RESET} {msg}')
def warn(msg):  print(f'  {YELLOW}⚠{RESET}  {msg}')
def err(msg):   print(f'  {RED}✗{RESET} {msg}')
def info(msg):  print(f'  {DIM}{msg}{RESET}')


# ── Step runner ───────────────────────────────────────────────────────────────

def run_step(fn, dry_run=False):
    """Run a callable step. Returns True on success, False on failure."""
    if dry_run:
        ok('[dry-run] skipped')
        return True
    t0 = time.time()
    try:
        fn()
        ok(f'Done in {time.time() - t0:.1f}s')
        return True
    except SystemExit as e:
        if e.code in (0, None):
            ok(f'Done in {time.time() - t0:.1f}s')
            return True
        err(f'Exited with code {e.code}')
        return False
    except Exception as e:
        err(f'Failed: {e}')
        import traceback
        traceback.print_exc()
        return False


# ── Individual step functions ─────────────────────────────────────────────────

def step_refresh_cache():
    import refresh_cache
    refresh_cache.main()


def step_scan_all():
    # scan_all uses argparse so run as subprocess to avoid argv conflicts
    subprocess.run(
        [sys.executable, os.path.join(WORKSPACE, 'scan_all.py')],
        cwd=WORKSPACE, check=True
    )


def step_ewros():
    sys.argv = ['ewros.py']
    import scripts.ewros as m
    m.main()


def step_iq_edge():
    sys.argv = ['iq_edge_predict.py']
    import scripts.iq_edge_predict as m
    m.main()


def step_generate_watchlist():
    import generate_watchlist
    # generate_watchlist may use argparse — run as subprocess
    subprocess.run(
        [sys.executable, os.path.join(WORKSPACE, 'generate_watchlist.py')],
        cwd=WORKSPACE, check=True
    )


def step_merge_ewros_into_top():
    """Backfill ewros_stats from all_stocks.json into top_stocks.json."""
    all_path = os.path.join(WORKSPACE, 'data', 'all_stocks.json')
    top_path = os.path.join(WORKSPACE, 'data', 'top_stocks.json')

    with open(all_path) as f:
        all_data = json.load(f)
    all_stocks = all_data.get('stocks', all_data)

    with open(top_path) as f:
        top_data = json.load(f)

    fields = ['ewros_score', 'ewros_raw', 'ewros_trend', 'ewros_prior', 'ewros_stats',
              'iq_edge', 'iq_edge_raw']
    updated = 0
    for s in top_data.get('stocks', []):
        ticker = s.get('ticker')
        if ticker and ticker in all_stocks:
            for field in fields:
                s[field] = all_stocks[ticker].get(field)
            updated += 1

    with open(top_path, 'w') as f:
        json.dump(top_data, f, indent=2)
    info(f'Merged EWROS data into {updated} top stocks')


def step_distribution_scan():
    import reports.distribution_scan as m
    m.main()


def step_sector_drivers():
    import reports.sector_drivers as m
    m.main()


def step_earnings_calendar():
    sys.argv = ['earnings_calendar.py']
    import scripts.earnings_calendar as m
    m.main()


def step_earnings_recap():
    sys.argv = ['earnings_recap.py']
    import scripts.earnings_recap as m
    m.main()


def step_sell_signals():
    sys.argv = ['sell_signal_check.py']
    import scripts.sell_signal_check as m
    m.main()


def step_insider_scan():
    sys.argv = ['insider_scan.py']
    import scripts.insider_scan as m
    m.main()


def step_git_push(dry_run=False, skip_git=False):
    if skip_git:
        warn('Git push skipped (--skip-git)')
        return True
    if dry_run:
        ok('[dry-run] would git add + commit + push')
        return True
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M')
        files = [
            'data/all_stocks.json',
            'data/top_stocks.json',
            'data/watchlist.json',
            'data/earnings_calendar.json',
            'data/insider_signals.json',
            'data/cik_cache.json',
            'data/rotation_snapshots.json',
        ]
        subprocess.run(['git', 'add'] + files, cwd=WORKSPACE, check=False)
        result = subprocess.run(
            ['git', 'commit', '-m', f'daily update: {ts}'],
            cwd=WORKSPACE, capture_output=True, text=True
        )
        if 'nothing to commit' in result.stdout + result.stderr:
            info('Nothing new to commit')
            return True
        subprocess.run(['git', 'push'], cwd=WORKSPACE, check=True)
        ok('Pushed to GitHub Pages')
        return True
    except subprocess.CalledProcessError as e:
        err(f'Git failed: {e}')
        return False


# ── Step registry ─────────────────────────────────────────────────────────────

# name → (label, fn, skip_if_no_cache)
ALL_STEPS = [
    ('cache',        'Download prices + fundamentals (refresh_cache)',   step_refresh_cache,      True),
    ('scan',         'Score all stocks (scan_all)',                       step_scan_all,           False),
    ('ewros',        'Compute EWROS scores + stats',                      step_ewros,              False),
    ('iqedge',       'IQ Edge ML predictions (iq_edge_predict)',          step_iq_edge,            False),
    ('watchlist',    'Rebuild watchlist.json (generate_watchlist)',       step_generate_watchlist, False),
    ('merge',        'Merge EWROS → top_stocks.json',                    step_merge_ewros_into_top, False),
    ('distribution', 'Distribution scan (institutional selling)',         step_distribution_scan,  False),
    ('sector',       'Sector drivers report + email',                     step_sector_drivers,     False),
    ('earnings_cal', 'Update earnings calendar',                          step_earnings_calendar,  False),
    ('earnings_rec', 'Earnings recap email',                              step_earnings_recap,     False),
    ('sell',         'Check sell signals → alerts',                       step_sell_signals,       False),
    ('insider',      'Fetch insider transactions (SEC EDGAR)',             step_insider_scan,       False),
]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='InvestIQ Daily Update Orchestrator')
    parser.add_argument('--skip-cache', action='store_true',
                        help='Skip refresh_cache.py (use existing DB data)')
    parser.add_argument('--skip-git', action='store_true',
                        help='Skip git commit + push at the end')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print steps without executing anything')
    parser.add_argument('--only', nargs='+', metavar='STEP',
                        help=f'Run only these steps. Choices: {[s[0] for s in ALL_STEPS]}')
    args = parser.parse_args()

    sep = '=' * 56
    print(f'\n{BOLD}{sep}')
    print(f'  InvestIQ Daily Update — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{sep}{RESET}')

    # Build list of steps to run
    steps_to_run = []
    for name, label, fn, cache_only in ALL_STEPS:
        if args.only and name not in args.only:
            continue
        if not args.only and args.skip_cache and cache_only:
            continue
        steps_to_run.append((name, label, fn))

    total = len(steps_to_run) + 1  # +1 for git
    results = {}
    pipeline_start = time.time()

    # ── Kick-off ping ─────────────────────────────────────────────────────────
    if not args.dry_run:
        send_telegram(
            f'📊 *InvestIQ Daily Pipeline started*\n'
            f'🕐 {datetime.now().strftime("%I:%M %p ET")}\n'
            f'Steps: {len(steps_to_run) + 1} tasks queued'
        )

    # Milestones to ping after (step name → emoji + label)
    MILESTONES = {
        'cache':   ('📥', 'Data download complete'),
        'merge':   ('🧮', 'Scoring + EWROS done'),
        'sell':    ('🚨', 'Sell signals checked'),
        'insider': ('🔍', 'Insider scan done'),
    }

    for i, (name, label, fn) in enumerate(steps_to_run, 1):
        hdr(i, total, label)
        ok_flag = run_step(fn, dry_run=args.dry_run)
        results[name] = ok_flag

        # Send milestone ping
        if not args.dry_run and name in MILESTONES:
            emoji, milestone_label = MILESTONES[name]
            elapsed = int(time.time() - pipeline_start)
            status_char = '✅' if ok_flag else '❌'
            send_telegram(
                f'{status_char} {emoji} *{milestone_label}*\n'
                f'⏱ {elapsed // 60}m {elapsed % 60}s elapsed'
            )

    # Git push always last
    hdr(total, total, 'Git commit + push → GitHub Pages')
    git_ok = step_git_push(dry_run=args.dry_run, skip_git=args.skip_git)

    # Summary
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    total_elapsed = int(time.time() - pipeline_start)
    elapsed_str = f'{total_elapsed // 60}m {total_elapsed % 60}s'

    print(f'\n{BOLD}{sep}')
    status = f'{GREEN}{passed} passed{RESET}{BOLD}'
    if failed:
        status += f'  {RED}{failed} failed{RESET}{BOLD}'
    print(f'  Summary: {status}')
    print(f'{sep}{RESET}')

    for name, label, _ in steps_to_run:
        icon = f'{GREEN}✓{RESET}' if results.get(name) else f'{RED}✗{RESET}'
        print(f'  {icon}  {label}')
    git_icon = f'{GREEN}✓{RESET}' if git_ok else f'{RED}✗{RESET}'
    print(f'  {git_icon}  Git push')

    # ── Final summary ping ────────────────────────────────────────────────────
    if not args.dry_run:
        if failed:
            failed_names = [label for name, label, _ in steps_to_run if not results.get(name)]
            send_telegram(
                f'⚠️ *Daily Pipeline finished with errors*\n'
                f'✅ {passed} passed  ❌ {failed} failed\n'
                f'⏱ Total: {elapsed_str}\n\n'
                f'Failed:\n' + '\n'.join(f'• {l}' for l in failed_names)
            )
        else:
            send_telegram(
                f'✅ *Daily Pipeline complete*\n'
                f'📊 All {passed} tasks succeeded\n'
                f'⏱ Total: {elapsed_str}\n'
                f'🌐 theiqinvestor.com updated'
            )

    if failed:
        print(f'\n{YELLOW}⚠  Some steps failed — check output above.{RESET}')
        sys.exit(1)
    else:
        print(f'\n{GREEN}All steps complete.{RESET}')


if __name__ == '__main__':
    main()

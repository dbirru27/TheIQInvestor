#!/usr/bin/env python3
"""
InvestIQ QA Watchdog — Self-Healing Edition
============================================
Runs as the FINAL step of the daily pipeline (daily_update.py).
Detects, fixes, and re-validates all data and scoring issues automatically.

Every check has three modes:
  1. DETECT  — find the problem
  2. FIX     — auto-repair it (no human needed)
  3. RE-CHECK — verify the fix actually worked
  4. ESCALATE — if fix fails, alert Dan with what to do

Problems this agent catches and fixes by itself:
  A. Scoring output: N/A / "No yfinance data" / "Insufficient data" in any criterion
  B. Yahoo API field renames (e.g. pegRatio → trailingPegRatio)
  C. DB fundamental field coverage < 70% for any critical field
  D. Quarterly revenue/EPS < 8 quarters average
  E. SPY data missing or thin (< 200 rows) — causes RS "Insufficient data"
  F. Grade ordering inversion (Grade B avg EWROS > Grade A)
  G. Stale data files (all_stocks.json not updated today)
  H. Syntax/import bugs in key pipeline scripts
  I. GitHub Pages not pushed today (website out of date)
  J. Pipeline didn't run today or errored

Run: python3 scripts/qa_watchdog.py
"""

import os
import sys
import json
import sqlite3
import subprocess
import traceback
import statistics
import importlib
import py_compile
import tempfile
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field as dc_field
from typing import List, Optional
from collections import defaultdict

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

from scripts.telegram_utils import send_telegram

TODAY     = date.today().strftime("%Y-%m-%d")
NOW       = datetime.now().strftime("%H:%M ET")
DB_PATH   = os.path.join(WORKSPACE, "data/market_data.db")
ALL_PATH  = os.path.join(WORKSPACE, "data/all_stocks.json")
TOP_PATH  = os.path.join(WORKSPACE, "data/top_stocks.json")
WL_PATH   = os.path.join(WORKSPACE, "data/watchlist.json")

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    fixed: bool = False
    fix_detail: str = ""
    critical: bool = True
    recheck_passed: Optional[bool] = None

RESULTS: List[CheckResult] = []

# ── Helpers ───────────────────────────────────────────────────────────────────

def sh(cmd, timeout=120):
    """Run shell command. Return (returncode, stdout, stderr)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       cwd=WORKSPACE, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def pyrun(script_path, args="", timeout=300):
    """Run a python script and return (ok, output)."""
    rc, out, err = sh(f"{sys.executable} {script_path} {args}", timeout=timeout)
    return rc == 0, out + err


def load_json(path):
    with open(path) as f:
        return json.load(f)


def db():
    return sqlite3.connect(DB_PATH)


def all_scored_stocks():
    """Return list of non-ETF stocks with criteria from all_stocks.json."""
    d = load_json(ALL_PATH)
    return [s for s in d['stocks'].values()
            if s.get('grade') not in ('ETF', None) and s.get('criteria')]


def rescan(steps="scan merge git"):
    """Re-run pipeline steps to regenerate scoring output after a fix."""
    ok, out = pyrun(f"{WORKSPACE}/scripts/daily_update.py", f"--only {steps}", timeout=300)
    return ok


# ── CHECK A: Scoring output — N/A / error strings in criteria ─────────────────

def check_scoring_output():
    """
    Scan every criterion for every stock. Any systemic N/A or error string
    means a data source broke silently. Detect → Fix → Re-scan → Re-check.
    """
    BAD = ['n/a', 'no yfinance', 'insufficient data', 'data unavailable',
           'no eps', 'no data', 'calc error', 'error:', 'insufficient quarters']

    def scan_bad():
        stocks = all_scored_stocks()
        n = len(stocks)
        counts = defaultdict(int)
        samples = defaultdict(list)
        for s in stocks:
            for c in s.get('criteria', []):
                val = str(c.get('value', '')).lower()
                cname = c.get('name', '')
                if any(p in val for p in BAD):
                    counts[cname] += 1
                    if len(samples[cname]) < 3:
                        samples[cname].append(s['ticker'])
        return n, counts, samples

    n, counts, samples = scan_bad()
    systemic = {k: v for k, v in counts.items() if v / n > 0.10}
    if not systemic:
        minor = {k: v for k, v in counts.items() if v / n > 0.05}
        detail = f"All {n} stocks scoring cleanly."
        if minor:
            detail = "Minor gaps (<10%): " + "; ".join(f"{k}: {v}" for k, v in minor.items())
        return CheckResult("Scoring Output", passed=not bool(minor), detail=detail, critical=False)

    issue_detail = "; ".join(f"{k}: {v}/{n} ({v/n*100:.0f}%) — e.g. {samples[k]}" for k, v in sorted(systemic.items(), key=lambda x: -x[1]))

    # === FIX PHASE ===
    # Map criterion names to fix actions
    fix_applied = []

    # 1. "Valuation Sanity" N/A → PEG missing → run refresh_fundamentals
    if "Valuation Sanity" in systemic:
        ok, _ = pyrun(f"{WORKSPACE}/scripts/refresh_fundamentals.py", timeout=180)
        if ok:
            fix_applied.append("Ran refresh_fundamentals (PEG/derived fields)")

    # 2. "Relative Strength" / "RS" N/A → SPY thin in DB → backfill SPY
    if any("Strength" in k or "RS" in k for k in systemic):
        fixed = _backfill_spy()
        if fixed:
            fix_applied.append(f"Backfilled SPY history: {fixed}")

    # 3. "Earnings Acceleration" N/A → quarterly_eps missing → SEC backfill
    if "Earnings Acceleration" in systemic:
        ok, _ = pyrun(f"{WORKSPACE}/scripts/refresh_fundamentals.py", timeout=180)
        if ok:
            fix_applied.append("Ran refresh_fundamentals (quarterly EPS backfill)")

    # 4. "Revenue Score" N/A → quarterly_revenue missing → same fix
    if "Revenue Score" in systemic:
        ok, _ = pyrun(f"{WORKSPACE}/scripts/refresh_fundamentals.py", timeout=180)
        if ok:
            fix_applied.append("Ran refresh_fundamentals (quarterly revenue backfill)")

    # Re-run scoring if any fix was applied
    if fix_applied:
        rescan("scan merge git")
        # === RE-CHECK ===
        _, counts2, _ = scan_bad()
        systemic2 = {k: v for k, v in counts2.items() if v / n > 0.10}
        recheck_passed = len(systemic2) == 0
    else:
        recheck_passed = False

    return CheckResult(
        name="Scoring Output",
        passed=False,
        detail=issue_detail,
        fixed=bool(fix_applied),
        fix_detail="; ".join(fix_applied) if fix_applied else "No auto-fix available",
        critical=True,
        recheck_passed=recheck_passed
    )


# ── CHECK B: Yahoo API field renames ─────────────────────────────────────────

def check_yahoo_field_names():
    """
    Probe Yahoo Finance live for a sample of stocks.
    Compare returned keys against what we store in DB.
    Detect renames (e.g. pegRatio → trailingPegRatio) and normalize DB.

    Known rename map: add entries here when Yahoo changes field names.
    """
    RENAME_MAP = {
        # old_name: [new_name_candidates]
        'pegRatio': ['trailingPegRatio'],
        'forwardEps': ['trailingEps', 'epsForward'],
        'enterpriseValue': ['enterpriseValue'],  # stable, just checking
    }

    try:
        import yfinance as yf
        # Probe 5 large-cap stocks
        probe = yf.download(tickers="AAPL MSFT NVDA GOOGL LLY",
                            period="1d", auto_adjust=False, progress=False)
        t = yf.Ticker("NVDA")
        live_keys = set(t.info.keys())
    except Exception as e:
        return CheckResult("Yahoo Field Names", passed=True,
                           detail=f"Could not probe live (skipped): {e}", critical=False)

    db_renames = {}  # old_key → new_key that should be used
    for old, candidates in RENAME_MAP.items():
        if old not in live_keys:
            # Old key gone — find which new candidate Yahoo returns
            for new_key in candidates:
                if new_key in live_keys:
                    db_renames[old] = new_key
                    break

    if not db_renames:
        return CheckResult("Yahoo Field Names", passed=True,
                           detail="All expected Yahoo field names intact.")

    # FIX: normalize in DB
    conn = db()
    c = conn.cursor()
    c.execute("SELECT symbol, data FROM fundamentals")
    rows = c.fetchall()
    updated = 0
    for sym, data_str in rows:
        try:
            info = json.loads(data_str)
            changed = False
            for old_key, new_key in db_renames.items():
                new_val = info.get(new_key)
                if new_val is not None and info.get(old_key) is None:
                    info[old_key] = new_val  # back-populate old key for compatibility
                    changed = True
            if changed:
                c.execute("UPDATE fundamentals SET data=? WHERE symbol=?",
                          (json.dumps(info), sym))
                updated += 1
        except Exception:
            continue
    conn.commit()
    conn.close()

    rename_str = ", ".join(f"{o}→{n}" for o, n in db_renames.items())
    return CheckResult(
        name="Yahoo Field Names",
        passed=False,
        detail=f"Yahoo renamed: {rename_str}",
        fixed=True,
        fix_detail=f"Normalized {updated} DB rows to use new field names",
        critical=False
    )


# ── CHECK C+D: Fundamental field coverage ────────────────────────────────────

def check_fundamentals_coverage():
    """
    Check coverage of critical fundamental fields and quarterly data depth.
    Auto-fix by running refresh_fundamentals.py.
    """
    CRITICAL_FIELDS = {
        'forwardPE': 80,       # min % coverage required
        'earningsGrowth': 70,
        'returnOnEquity': 80,
        'operatingMargins': 80,
        'pegRatio': 70,        # now sourced from trailingPegRatio
        'revenueGrowth': 80,
    }
    MIN_QUARTERS = 8

    conn = db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM fundamentals")
    total = c.fetchone()[0]

    issues = []
    for field, threshold in CRITICAL_FIELDS.items():
        c.execute(f"SELECT COUNT(*) FROM fundamentals WHERE json_extract(data,'$.{field}') IS NOT NULL")
        present = c.fetchone()[0]
        pct = present / total * 100 if total else 0
        if pct < threshold:
            issues.append(f"{field}: {pct:.0f}% (need {threshold}%)")

    c.execute("SELECT AVG(cnt) FROM (SELECT COUNT(*) cnt FROM quarterly_revenue GROUP BY symbol)")
    avg_rev = c.fetchone()[0] or 0
    c.execute("SELECT AVG(cnt) FROM (SELECT COUNT(*) cnt FROM quarterly_eps GROUP BY symbol)")
    avg_eps = c.fetchone()[0] or 0
    conn.close()

    if avg_rev < MIN_QUARTERS:
        issues.append(f"quarterly_revenue avg {avg_rev:.1f}Q (need {MIN_QUARTERS}+)")
    if avg_eps < MIN_QUARTERS:
        issues.append(f"quarterly_eps avg {avg_eps:.1f}Q (need {MIN_QUARTERS}+)")

    if not issues:
        return CheckResult("Fundamentals Coverage", passed=True,
                           detail=f"pegRatio OK, rev {avg_rev:.1f}Q, eps {avg_eps:.1f}Q")

    # FIX: run refresh_fundamentals
    ok, out = pyrun(f"{WORKSPACE}/scripts/refresh_fundamentals.py", timeout=240)

    # RE-CHECK after fix
    conn2 = db()
    c2 = conn2.cursor()
    still_bad = []
    for field, threshold in CRITICAL_FIELDS.items():
        c2.execute(f"SELECT COUNT(*), COUNT(CASE WHEN json_extract(data,'$.{field}') IS NOT NULL THEN 1 END) FROM fundamentals")
        tot, present = c2.fetchone()
        pct = present / tot * 100 if tot else 0
        if pct < threshold:
            still_bad.append(f"{field}: {pct:.0f}%")
    conn2.close()

    return CheckResult(
        name="Fundamentals Coverage",
        passed=False,
        detail="; ".join(issues),
        fixed=ok,
        fix_detail="refresh_fundamentals.py completed" if ok else f"Fix failed: {out[-80:]}",
        recheck_passed=len(still_bad) == 0
    )


# ── CHECK E: SPY data in DB ───────────────────────────────────────────────────

def check_spy_db_coverage():
    """
    RS calculation requires SPY price history in the DB prices table.
    If < 200 rows exist, the cache-poison bug causes all stocks to show
    'Insufficient data'. Detect and auto-fix by fetching full 1-year history.
    """
    conn = db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM prices WHERE symbol='SPY'")
    spy_rows = c.fetchone()[0]
    conn.close()

    if spy_rows >= 200:
        return CheckResult("SPY DB Coverage", passed=True,
                           detail=f"SPY has {spy_rows} rows in DB — sufficient for RS")

    # FIX: fetch full year of SPY
    fix_detail = _backfill_spy()
    conn2 = db()
    c2 = conn2.cursor()
    c2.execute("SELECT COUNT(*) FROM prices WHERE symbol='SPY'")
    new_rows = c2.fetchone()[0]
    conn2.close()

    return CheckResult(
        name="SPY DB Coverage",
        passed=False,
        detail=f"SPY had only {spy_rows} rows (need 200+ for RS calculations)",
        fixed=bool(fix_detail and "failed" not in fix_detail.lower()),
        fix_detail=fix_detail,
        recheck_passed=new_rows >= 200
    )


def _backfill_spy():
    try:
        import yfinance as yf
        hist = yf.Ticker("SPY").history(period="1y", auto_adjust=False)
        if hist.empty or len(hist) < 100:
            return "SPY fetch returned insufficient data"
        conn = db()
        c = conn.cursor()
        written = 0
        for dt, row in hist.iterrows():
            c.execute("""
                INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("SPY", dt.strftime("%Y-%m-%d"),
                  float(row.get("Open", 0)), float(row.get("High", 0)),
                  float(row.get("Low", 0)),  float(row.get("Close", 0)),
                  int(row.get("Volume", 0))))
            written += 1
        conn.commit()
        conn.close()
        return f"Wrote {written} SPY rows to DB"
    except Exception as e:
        return f"SPY backfill failed: {e}"


# ── CHECK F: Grade ordering sanity ───────────────────────────────────────────

def check_grade_sanity():
    """
    Grade A should have higher avg EWROS than Grade B, etc.
    If inverted, the scoring weights are broken. Flag loudly — no auto-fix,
    needs a scoring redesign decision.
    """
    stocks = all_scored_stocks()
    grade_ewros = defaultdict(list)
    for s in stocks:
        g = s.get('grade')
        e = s.get('ewros_score')
        if g and e and g != 'ETF':
            grade_ewros[g].append(float(e))

    avgs = {g: statistics.mean(v) for g, v in grade_ewros.items() if v}
    issues = []
    grade_order = ['A+', 'A', 'A-', 'B', 'C', 'D', 'F']
    prev_g, prev_avg = None, None
    for g in grade_order:
        if g not in avgs:
            continue
        if prev_avg is not None and avgs[g] > prev_avg:
            issues.append(f"Grade {g} avg EWROS ({avgs[g]:.1f}) > Grade {prev_g} ({prev_avg:.1f})")
        prev_g, prev_avg = g, avgs[g]

    count_a = sum(len(grade_ewros.get(g, [])) for g in ['A+', 'A', 'A-'])
    if count_a < 5:
        issues.append(f"Only {count_a} A-grade stocks (threshold may be too tight)")

    summary = " | ".join(f"{g}:{avgs.get(g,0):.0f}" for g in ['A','B','C','D'] if g in avgs)

    if issues:
        return CheckResult(
            name="Grade Sanity",
            passed=False,
            detail="; ".join(issues) + f" | EWROS by grade: {summary}",
            fixed=False,
            fix_detail="Cannot auto-fix: requires scoring redesign (PULSE v6.0). Needs human decision.",
            critical=True
        )
    return CheckResult("Grade Sanity", passed=True, detail=f"EWROS: {summary}")


# ── CHECK G: Data file freshness ──────────────────────────────────────────────

def check_data_freshness():
    issues = []
    for path, key in [(ALL_PATH, 'generated_at'), (TOP_PATH, 'generated_at'), (WL_PATH, 'last_updated')]:
        if not os.path.exists(path):
            issues.append(f"MISSING: {os.path.basename(path)}")
            continue
        d = load_json(path)
        ts = d.get(key) or d.get('timestamp') or d.get('as_of', '')
        if TODAY not in str(ts):
            issues.append(f"STALE: {os.path.basename(path)} → {str(ts)[:10]}")

    rc, out, _ = sh("git log --oneline -1 --format='%ci'")
    if out and TODAY not in out:
        issues.append(f"GitHub Pages: last push {out[:10]}")

    if not issues:
        return CheckResult("Data Freshness", passed=True, detail=f"All files current as of {TODAY}")

    return CheckResult("Data Freshness", passed=False, detail="; ".join(issues), critical=True)


# ── CHECK H: Syntax + import bugs in key scripts ─────────────────────────────

def check_script_health():
    """
    Compile-check all key pipeline scripts. Catch missing imports and
    syntax errors before they silently break the pipeline.
    Also run targeted checks for known recurring bugs.
    """
    KEY_SCRIPTS = [
        "rater.py", "scan_all.py", "refresh_cache.py",
        "scripts/daily_update.py", "scripts/ewros.py",
        "scripts/refresh_fundamentals.py",
    ]
    REQUIRED_IMPORTS = {
        "scripts/daily_update.py": ["import json", "import sys", "import os"],
        "rater.py": ["import sqlite3", "import pandas"],
        "scan_all.py": ["import json"],
    }

    issues = []
    fixed = []

    for relpath in KEY_SCRIPTS:
        fpath = os.path.join(WORKSPACE, relpath)
        if not os.path.exists(fpath):
            issues.append(f"MISSING: {relpath}")
            continue
        # Syntax check
        try:
            py_compile.compile(fpath, doraise=True)
        except py_compile.PyCompileError as e:
            issues.append(f"SYNTAX ERROR in {relpath}: {str(e)[:80]}")
            continue

        # Import checks
        with open(fpath) as f:
            content = f.read()

        for imp in REQUIRED_IMPORTS.get(relpath, []):
            if imp not in content:
                # Auto-fix: insert at top of imports block
                lines = content.split('\n')
                insert_at = next((i for i, l in enumerate(lines)
                                  if l.startswith('import ') or l.startswith('from ')), 0)
                lines.insert(insert_at, imp)
                with open(fpath, 'w') as f:
                    f.write('\n'.join(lines))
                fixed.append(f"Inserted '{imp}' into {relpath}")

    if issues or fixed:
        return CheckResult(
            name="Script Health",
            passed=not bool(issues),
            detail="; ".join(issues) if issues else "No syntax errors",
            fixed=bool(fixed),
            fix_detail="; ".join(fixed) if fixed else "",
            critical=bool(issues)
        )
    return CheckResult("Script Health", passed=True,
                       detail=f"All {len(KEY_SCRIPTS)} scripts compile cleanly")


# ── CHECK I: GitHub Pages pushed today ───────────────────────────────────────

def check_github_push():
    rc, out, _ = sh("git log --oneline -1 --format='%ci|%s'")
    if rc != 0:
        return CheckResult("GitHub Push", passed=False, detail="git log failed", critical=False)
    parts = out.split("|", 1)
    commit_date = parts[0][:10] if parts else "?"
    msg = parts[1].strip()[:60] if len(parts) > 1 else "?"

    if commit_date == TODAY:
        return CheckResult("GitHub Push", passed=True, detail=f"'{msg}'")

    # FIX: push now
    rc2, _, err = sh("git add -A && git commit -m 'chore: QA watchdog re-push' && git push")
    return CheckResult(
        name="GitHub Push",
        passed=False,
        detail=f"Last push was {commit_date}",
        fixed=(rc2 == 0),
        fix_detail="Pushed to GitHub Pages" if rc2 == 0 else f"Push failed: {err[:60]}",
        critical=False
    )


# ── CHECK J: Pipeline ran today ───────────────────────────────────────────────

def check_pipeline_ran():
    runs_dir = os.path.expanduser("~/.openclaw/cron/runs")
    pipeline_id = "5facd568-a287-40d1-ac63-0c36a4310310"
    log_path = os.path.join(runs_dir, f"{pipeline_id}.jsonl")

    if not os.path.exists(log_path):
        return CheckResult("Pipeline Ran Today", passed=False,
                           detail="Run log not found — pipeline may not be configured", critical=True)

    last_run = None
    with open(log_path) as f:
        for line in reversed(f.readlines()):
            try:
                d = json.loads(line)
                if d.get("action") == "finished":
                    last_run = d
                    break
            except Exception:
                continue

    if not last_run:
        return CheckResult("Pipeline Ran Today", passed=False,
                           detail="No finished runs in log", critical=True)

    run_ts = datetime.fromtimestamp(last_run["ts"] / 1000)
    run_date = run_ts.strftime("%Y-%m-%d")
    status = last_run.get("status", "?")

    if run_date != TODAY:
        return CheckResult("Pipeline Ran Today", passed=False,
                           detail=f"Last run: {run_date} (not today). Status: {status}",
                           critical=True)
    if status != "ok":
        return CheckResult("Pipeline Ran Today", passed=False,
                           detail=f"Today's run status: {status} — {last_run.get('error','')[:80]}",
                           critical=False)

    return CheckResult("Pipeline Ran Today", passed=True,
                       detail=f"Ran at {run_ts.strftime('%H:%M ET')}, status: ok")


# ── ORCHESTRATOR ──────────────────────────────────────────────────────────────

CHECKS = [
    # name                      function                    run_order
    ("Script Health",           check_script_health),       # run first — broken scripts break everything
    ("Data Freshness",          check_data_freshness),
    ("Yahoo Field Names",       check_yahoo_field_names),   # detect renames before coverage check
    ("Fundamentals Coverage",   check_fundamentals_coverage),
    ("SPY DB Coverage",         check_spy_db_coverage),
    ("Scoring Output",          check_scoring_output),      # must run after fixes above
    ("Grade Sanity",            check_grade_sanity),
    ("Pipeline Ran Today",      check_pipeline_ran),
    ("GitHub Push",             check_github_push),
]


def run_all_checks():
    global RESULTS
    RESULTS = []

    print(f"\n{'='*62}")
    print(f"  InvestIQ QA Watchdog — {TODAY} {NOW}")
    print(f"{'='*62}\n")

    for name, fn in CHECKS:
        try:
            result = fn()
            result.name = name
        except Exception as e:
            result = CheckResult(name=name, passed=False,
                                 detail=f"Check crashed: {e}", critical=True)

        RESULTS.append(result)

        icon = "✅" if result.passed else ("🔧" if result.fixed and result.recheck_passed else "🚨" if result.critical else "⚠️")
        print(f"  {icon} [{('PASS' if result.passed else 'FIXED' if result.fixed and result.recheck_passed else 'FAIL')}] {result.name}")
        if result.detail:
            print(f"         {result.detail[:120]}")
        if result.fixed:
            status = "✓ verified" if result.recheck_passed else "⚠️ still failing after fix"
            print(f"         Fix: {result.fix_detail[:100]} [{status}]")
        print()

    # ── Summary ──────────────────────────────────────────────────────────────
    passed   = [r for r in RESULTS if r.passed]
    fixed_ok = [r for r in RESULTS if not r.passed and r.fixed and r.recheck_passed]
    still_bad = [r for r in RESULTS if not r.passed and not (r.fixed and r.recheck_passed)]
    critical_unresolved = [r for r in still_bad if r.critical]

    print(f"\n{'='*62}")

    lines = [f"🔬 *QA Watchdog — {TODAY}*\n"]

    if critical_unresolved:
        lines.append(f"🚨 *{len(critical_unresolved)} unresolved critical issue(s):*")
        for r in critical_unresolved:
            lines.append(f"  • *{r.name}*: {r.detail[:100]}")
            if r.fix_detail:
                lines.append(f"    ↳ {r.fix_detail[:80]}")
        lines.append("")

    if fixed_ok:
        lines.append(f"🔧 *Auto-fixed {len(fixed_ok)} issue(s):*")
        for r in fixed_ok:
            lines.append(f"  • *{r.name}*: {r.fix_detail[:80]}")
        lines.append("")

    non_critical_fail = [r for r in still_bad if not r.critical]
    if non_critical_fail:
        lines.append(f"⚠️ *{len(non_critical_fail)} minor issue(s):*")
        for r in non_critical_fail:
            lines.append(f"  • *{r.name}*: {r.detail[:80]}")
        lines.append("")

    total = len(RESULTS)
    ok_count = len(passed) + len(fixed_ok)
    lines.append(f"`{ok_count}/{total} checks passing`")

    if not critical_unresolved and not non_critical_fail:
        lines.append("✅ All systems healthy.")

    report = "\n".join(lines)
    print("TELEGRAM REPORT:")
    print(report)
    print(f"{'='*62}\n")

    send_telegram(report)
    print("✅ QA Watchdog complete")
    return len(critical_unresolved) == 0


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)

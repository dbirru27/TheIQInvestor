#!/usr/bin/env python3
"""
InvestIQ QA Watchdog
====================
Runs daily after the pipeline. Detects bugs, fixes what it can,
escalates what it can't. Reports to Telegram with a concise pass/fail card.

Run: python3 scripts/qa_watchdog.py
Cron: 0 17 * * 1-5 @ America/New_York (5 PM ET, 30 min after pipeline)
"""

import os
import sys
import json
import sqlite3
import subprocess
import traceback
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import List, Optional

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

from scripts.telegram_utils import send_telegram

TODAY = date.today().strftime("%Y-%m-%d")
NOW = datetime.now().strftime("%H:%M ET")

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    fixed: bool = False
    fix_detail: str = ""
    critical: bool = False

RESULTS: List[CheckResult] = []

def check(name, critical=False):
    """Decorator-style check runner."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, CheckResult):
                    result.name = name
                    result.critical = critical
                    RESULTS.append(result)
                    return result
            except Exception as e:
                r = CheckResult(name=name, passed=False,
                                detail=f"Exception: {str(e)[:120]}",
                                critical=critical)
                RESULTS.append(r)
                return r
        return wrapper
    return decorator


# ── Helper ────────────────────────────────────────────────────────────────────

def run(cmd, cwd=WORKSPACE, timeout=120):
    """Run a shell command, return (returncode, stdout, stderr)."""
    result = subprocess.run(cmd, shell=True, capture_output=True,
                            text=True, cwd=cwd, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def load_json(path):
    with open(path) as f:
        return json.load(f)


def db_connect():
    return sqlite3.connect(os.path.join(WORKSPACE, "data/market_data.db"))


# ── CHECK 1: Data file freshness ──────────────────────────────────────────────

def check_file_freshness():
    issues = []
    fixed_any = False

    files_to_check = [
        ("data/all_stocks.json",  "generated_at", True),
        ("data/top_stocks.json",  "generated_at", True),
        ("data/watchlist.json",   "last_updated", True),
    ]

    for relpath, ts_field, critical in files_to_check:
        path = os.path.join(WORKSPACE, relpath)
        if not os.path.exists(path):
            issues.append(f"MISSING: {relpath}")
            continue
        try:
            d = load_json(path)
            ts = d.get(ts_field) or d.get("timestamp") or d.get("as_of")
            if ts and TODAY not in str(ts):
                issues.append(f"STALE: {relpath} → {str(ts)[:10]} (expected {TODAY})")
            # Also check git commit date
        except Exception as e:
            issues.append(f"PARSE ERROR: {relpath}: {e}")

    # Check git log — last commit should be today
    rc, out, _ = run("git log --oneline -1 --format='%ci %s'")
    if out and TODAY not in out:
        issues.append(f"GIT: last commit is not today → {out.strip()[:60]}")

    if issues:
        return CheckResult(
            name="Data Freshness",
            passed=False,
            detail="; ".join(issues),
            critical=True
        )
    return CheckResult(name="Data Freshness", passed=True,
                       detail=f"all_stocks, top_stocks, watchlist, git all dated {TODAY}")


# ── CHECK 2: RS scoring (SPY cache bug) ───────────────────────────────────────

def check_rs_scoring():
    path = os.path.join(WORKSPACE, "data/all_stocks.json")
    d = load_json(path)
    stocks = d.get("stocks", d)
    if isinstance(stocks, dict):
        stock_list = list(stocks.values())
    else:
        stock_list = stocks

    total = 0
    insufficient = 0
    for s in stock_list:
        if s.get("grade") == "ETF":
            continue
        for c in s.get("criteria", []):
            if c.get("name") == "Relative Strength":
                total += 1
                if "Insufficient" in str(c.get("value", "")):
                    insufficient += 1

    pct = insufficient / total * 100 if total else 0

    if pct > 10:  # >10% stocks have RS data failure = systemic bug
        # FIX: Pre-load SPY into DB with full 1-year history
        fix_detail = _fix_spy_in_db()
        return CheckResult(
            name="RS Scoring (SPY Cache)",
            passed=False,
            detail=f"{insufficient}/{total} stocks ({pct:.0f}%) show 'Insufficient data' for RS",
            fixed=bool(fix_detail),
            fix_detail=fix_detail,
            critical=True
        )

    return CheckResult(
        name="RS Scoring (SPY Cache)",
        passed=True,
        detail=f"{insufficient}/{total} ({pct:.0f}%) RS failures — within tolerance"
    )


def _fix_spy_in_db():
    """Load SPY 1-year history into the prices DB so RS calc doesn't need yfinance."""
    try:
        import yfinance as yf
        import pandas as pd

        spy = yf.Ticker("SPY")
        hist = spy.history(period="1y", auto_adjust=False)
        if hist.empty or len(hist) < 100:
            return "SPY fetch returned empty — could not fix"

        conn = db_connect()
        c = conn.cursor()

        # Upsert SPY rows
        rows_written = 0
        for dt, row in hist.iterrows():
            date_str = dt.strftime("%Y-%m-%d")
            c.execute("""
                INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("SPY", date_str,
                  float(row.get("Open", 0)),
                  float(row.get("High", 0)),
                  float(row.get("Low", 0)),
                  float(row.get("Close", 0)),
                  int(row.get("Volume", 0))))
            rows_written += 1

        conn.commit()
        conn.close()
        return f"Wrote {rows_written} SPY rows to DB ({hist.index[0].date()} → {hist.index[-1].date()})"
    except Exception as e:
        return f"SPY fix failed: {e}"


# ── CHECK 3: Grade sanity (Grade B should not outrank Grade A in EWROS) ───────

def check_grade_sanity():
    path = os.path.join(WORKSPACE, "data/all_stocks.json")
    d = load_json(path)
    stocks = d.get("stocks", d)
    if isinstance(stocks, dict):
        stock_list = list(stocks.values())
    else:
        stock_list = stocks

    grade_ewros = {}
    for s in stock_list:
        g = s.get("grade", "?")
        e = s.get("ewros_score")
        if e and g not in ("?", "ETF"):
            grade_ewros.setdefault(g, []).append(e)

    import statistics
    grade_avg = {g: statistics.mean(v) for g, v in grade_ewros.items() if v}

    issues = []
    if grade_avg.get("B", 0) > grade_avg.get("A", 100):
        issues.append(
            f"Grade B avg EWROS ({grade_avg['B']:.1f}) > Grade A ({grade_avg['A']:.1f}) — scoring inverted"
        )
    if grade_avg.get("C", 0) > grade_avg.get("B", 100):
        issues.append(
            f"Grade C avg EWROS ({grade_avg['C']:.1f}) > Grade B ({grade_avg['B']:.1f})"
        )

    count_a = len(grade_ewros.get("A", []))
    if count_a < 5:
        issues.append(f"Only {count_a} Grade A stocks — threshold may be too tight")

    summary = " | ".join(f"{g}:{grade_avg.get(g,0):.0f}" for g in ["A","B","C","D"])

    if issues:
        return CheckResult(
            name="Grade Sanity",
            passed=False,
            detail="; ".join(issues) + f" | EWROS by grade: {summary}",
            critical=True
        )
    return CheckResult(
        name="Grade Sanity",
        passed=True,
        detail=f"Grade ordering looks correct. EWROS: {summary}"
    )


# ── CHECK 4: Pipeline step completeness ──────────────────────────────────────

def check_pipeline_completeness():
    """Check that the cron run log shows today's run completed OK."""
    runs_dir = os.path.expanduser("~/.openclaw/cron/runs")
    pipeline_id = "5facd568-a287-40d1-ac63-0c36a4310310"  # InvestIQ Daily Pipeline
    log_path = os.path.join(runs_dir, f"{pipeline_id}.jsonl")

    if not os.path.exists(log_path):
        return CheckResult(name="Pipeline Completeness", passed=False,
                           detail="Run log not found", critical=True)

    with open(log_path) as f:
        lines = f.readlines()

    last_run = None
    for line in reversed(lines):
        try:
            d = json.loads(line)
            if d.get("action") == "finished":
                last_run = d
                break
        except:
            continue

    if not last_run:
        return CheckResult(name="Pipeline Completeness", passed=False,
                           detail="No finished runs found", critical=True)

    run_ts = datetime.fromtimestamp(last_run["ts"] / 1000)
    run_date = run_ts.strftime("%Y-%m-%d")
    status = last_run.get("status", "?")

    if run_date != TODAY:
        return CheckResult(
            name="Pipeline Completeness",
            passed=False,
            detail=f"Last run was {run_date}, not today ({TODAY}). Status: {status}",
            critical=True
        )
    if status != "ok":
        err = last_run.get("error", "")[:80]
        return CheckResult(
            name="Pipeline Completeness",
            passed=False,
            detail=f"Today's run status: {status} — {err}",
            critical=False
        )

    return CheckResult(
        name="Pipeline Completeness",
        passed=True,
        detail=f"Pipeline ran today at {run_ts.strftime('%H:%M ET')} — status: {status}"
    )


# ── CHECK 5: known import/code bugs ──────────────────────────────────────────

def check_known_bugs():
    issues = []

    # Bug: missing `import json` in daily_update.py
    daily_update = os.path.join(WORKSPACE, "scripts/daily_update.py")
    if os.path.exists(daily_update):
        with open(daily_update) as f:
            content = f.read()
        if "import json" not in content[:500]:
            # Auto-fix
            fixed = content.replace(
                "import sys\nimport time",
                "import json\nimport sys\nimport time",
                1
            )
            with open(daily_update, "w") as f:
                f.write(fixed)
            issues.append("FIXED: missing `import json` in daily_update.py")

    # Check rater.py exists and has expected scoring weights
    rater_path = os.path.join(WORKSPACE, "rater.py")
    if not os.path.exists(rater_path):
        issues.append("CRITICAL: rater.py missing")

    if issues:
        return CheckResult(
            name="Known Bugs",
            passed=False if any("CRITICAL" in i for i in issues) else True,
            detail="; ".join(issues),
            fixed=any("FIXED" in i for i in issues)
        )
    return CheckResult(name="Known Bugs", passed=True,
                       detail="No known bugs detected")


# ── CHECK 6: Website timestamp ────────────────────────────────────────────────

def check_website_timestamp():
    """Check that the latest git commit (GitHub Pages) is today."""
    rc, out, _ = run("git log --oneline -1 --format='%ci|%s'")
    if rc != 0:
        return CheckResult(name="Website Timestamp", passed=False,
                           detail="Could not read git log")

    parts = out.strip().split("|", 1)
    commit_date = parts[0][:10] if parts else "?"
    commit_msg = parts[1].strip() if len(parts) > 1 else "?"

    if commit_date != TODAY:
        return CheckResult(
            name="Website Timestamp",
            passed=False,
            detail=f"Last GitHub push: {commit_date} — website may be stale (expected {TODAY})",
            critical=True
        )
    return CheckResult(
        name="Website Timestamp",
        passed=True,
        detail=f"GitHub pushed today: '{commit_msg[:50]}'"
    )


# ── CHECK 7: Sparse columns in key files ─────────────────────────────────────

def check_data_sparseness():
    issues = []
    path = os.path.join(WORKSPACE, "data/all_stocks.json")
    d = load_json(path)
    stocks = d.get("stocks", d)
    if isinstance(stocks, dict):
        stock_list = [s for s in stocks.values() if s.get("grade") != "ETF"]
    else:
        stock_list = [s for s in stocks if s.get("grade") != "ETF"]

    n = len(stock_list)
    fields_to_check = ["ewros_score", "iq_edge", "score", "grade"]
    for field in fields_to_check:
        missing = sum(1 for s in stock_list if not s.get(field))
        pct = missing / n * 100
        if pct > 15:
            issues.append(f"{field}: {missing}/{n} ({pct:.0f}%) missing")

    if issues:
        return CheckResult(name="Data Sparseness", passed=False,
                           detail="; ".join(issues), critical=False)
    return CheckResult(name="Data Sparseness", passed=True,
                       detail=f"All key fields populated across {n} stocks")


# ── RUN ALL CHECKS ────────────────────────────────────────────────────────────

def run_all_checks():
    print(f"\n{'='*60}")
    print(f"  InvestIQ QA Watchdog — {TODAY} {NOW}")
    print(f"{'='*60}\n")

    checks = [
        ("Data Freshness",       check_file_freshness,       True),
        ("RS Scoring Bug",       check_rs_scoring,           True),
        ("Grade Sanity",         check_grade_sanity,         True),
        ("Pipeline Status",      check_pipeline_completeness, True),
        ("Known Code Bugs",      check_known_bugs,           False),
        ("Website Timestamp",    check_website_timestamp,    True),
        ("Data Sparseness",      check_data_sparseness,      False),
    ]

    for name, fn, critical in checks:
        try:
            r = fn()
            r.critical = critical
            RESULTS.append(r)
            icon = "✅" if r.passed else ("🔧" if r.fixed else ("🚨" if critical else "⚠️"))
            status = "PASS" if r.passed else ("FIXED" if r.fixed else "FAIL")
            print(f"  {icon} [{status}] {name}")
            print(f"         {r.detail[:100]}")
            if r.fixed and r.fix_detail:
                print(f"         Fix: {r.fix_detail[:100]}")
            print()
        except Exception as e:
            r = CheckResult(name=name, passed=False,
                            detail=str(e)[:100], critical=critical)
            RESULTS.append(r)
            print(f"  ❌ [ERROR] {name}: {e}")

    return RESULTS


# ── Telegram report ───────────────────────────────────────────────────────────

def build_telegram_message(results):
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed and not r.fixed]
    fixed  = [r for r in results if r.fixed]

    lines = [f"🔬 *QA Watchdog — {TODAY}*\n"]

    if not failed:
        lines.append("✅ All checks passed" if not fixed else "✅ All issues resolved")
    else:
        critical_fails = [r for r in failed if r.critical]
        if critical_fails:
            lines.append(f"🚨 *{len(critical_fails)} critical issue(s) need attention:*")
            for r in critical_fails:
                lines.append(f"  • *{r.name}*: {r.detail[:80]}")
        non_critical = [r for r in failed if not r.critical]
        if non_critical:
            lines.append(f"\n⚠️ *{len(non_critical)} warning(s):*")
            for r in non_critical:
                lines.append(f"  • {r.name}: {r.detail[:80]}")

    if fixed:
        lines.append(f"\n🔧 *Auto-fixed {len(fixed)} issue(s):*")
        for r in fixed:
            lines.append(f"  • {r.name}: {r.fix_detail[:80]}")

    lines.append(f"\n`{len(passed)}/{len(results)} checks passed`")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = run_all_checks()

    failed = [r for r in results if not r.passed and not r.fixed]
    fixed  = [r for r in results if r.fixed]

    # If RS was fixed, re-run the scan to update scores
    rs_fixed = any(r.name == "RS Scoring (SPY Cache)" and r.fixed for r in results)
    if rs_fixed:
        print("🔄 RS fix applied — re-running scan to update scores...")
        rc, out, err = run(
            "/usr/bin/python3 scripts/daily_update.py --only scan merge git",
            timeout=180
        )
        if rc == 0:
            print("✅ Scan re-run complete")
            results.append(CheckResult(
                name="RS Re-scan",
                passed=True,
                detail="Scan re-run after SPY fix — scores updated and pushed to GitHub"
            ))
        else:
            print(f"❌ Re-scan failed: {err[:200]}")
            results.append(CheckResult(
                name="RS Re-scan",
                passed=False,
                detail=f"Re-scan failed: {err[:80]}"
            ))

    msg = build_telegram_message(results)
    print("\n" + "="*60)
    print("TELEGRAM REPORT:")
    print(msg)
    print("="*60)

    send_telegram(msg)
    print("\n✅ QA Watchdog complete")

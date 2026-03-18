#!/usr/bin/env python3
"""
IBD Market Stage Calculator — Proper O'Neil Rules
===================================================
Implements the exact IBD Follow-Through Day methodology:

  1. CORRECTION: 5+ distribution days in 25 sessions, OR market clearly in downtrend
  2. RALLY ATTEMPT: First day market closes above the prior day's close after a correction low
                    Day 1 = that first up-close day (or any day that doesn't make a new low)
  3. FOLLOW-THROUGH DAY: Day 4 or later of rally attempt, index up ≥1.25% on
                         HIGHER volume than prior day. This confirms the rally.
  4. CONFIRMED RALLY: Follow-through day has occurred and not been invalidated
  5. INVALIDATION: If market undercuts the Day-1 low of the rally attempt → count resets

Distribution day rules (IBD):
  - Index falls ≥0.2% on volume higher than prior session
  - Stalling day: index up <0.4% on volume higher than prior session (churning)
  - Count window: 25 trading sessions
  - If 5+ distribution days: correction confirmed

This module is the single source of truth — used by:
  - scripts/update_market_internals.py (cron, every 15 min)
  - app.py (Flask API fallback)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, date
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def compute_market_stage(hist: pd.DataFrame = None) -> dict:
    """
    Compute IBD market stage from SPY price history.
    
    Args:
        hist: Optional DataFrame with OHLCV columns. If None, fetches SPY live.
    
    Returns:
        dict with stage, color, action, distribution_days, ftd details, rally_day, etc.
    """
    if hist is None:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="6mo", auto_adjust=False)

    if hist is None or len(hist) < 30:
        return {"stage": "UNKNOWN", "color": "gray", "action": "Insufficient data.", "error": True}

    closes  = hist['Close'].tolist()
    volumes = hist['Volume'].tolist()
    dates   = [d.strftime('%Y-%m-%d') for d in hist.index]
    n       = len(closes)

    # ── Step 1: Distribution days (last 25 sessions) ───────────────────────
    DIST_WINDOW = 25
    dist_days   = []   # list of (date, pct_change)
    stall_days  = []

    for i in range(max(1, n - DIST_WINDOW), n):
        pc, cc = closes[i-1], closes[i]
        pv, cv = volumes[i-1], volumes[i]
        if not all([pc, cc, pv, cv]) or pc == 0:
            continue
        pct = (cc - pc) / pc * 100
        if pct <= -0.2 and cv > pv:
            dist_days.append((dates[i], round(pct, 2)))
        elif 0 <= pct < 0.4 and cv > pv * 1.05:
            stall_days.append((dates[i], round(pct, 2)))

    dist_count  = len(dist_days)
    stall_count = len(stall_days)
    total_dist  = dist_count + stall_count

    # ── Step 2: Find the most recent correction low ────────────────────────
    # Look back up to 60 sessions for the lowest close in a meaningful pullback
    LOOKBACK = min(60, n - 1)
    recent_low_idx = n - 1
    recent_low_val = closes[n - 1]
    for i in range(n - LOOKBACK, n):
        if closes[i] < recent_low_val:
            recent_low_val = closes[i]
            recent_low_idx = i

    # If the recent low is within the last 3 sessions, market might still be falling
    in_correction_fall = recent_low_idx >= n - 3

    # ── Step 3: Rally attempt — find Day 1 ────────────────────────────────
    # Day 1 = first day AFTER the low that closes above the prior session's close
    # The low of Day 1 becomes the "line in the sand" — if undercut, count resets
    rally_day1_idx  = None
    rally_day1_low  = None
    rally_day1_date = None

    for i in range(recent_low_idx + 1, n):
        pc, cc = closes[i-1], closes[i]
        if cc > pc:  # up-close day = Day 1 of rally attempt
            rally_day1_idx  = i
            rally_day1_low  = hist['Low'].iloc[i]   # intraday low, not close
            rally_day1_date = dates[i]
            break

    # ── Step 4: Check if rally attempt was invalidated (undercut Day 1 low) ─
    rally_invalidated = False
    if rally_day1_low is not None:
        for i in range(rally_day1_idx + 1, n):
            intraday_low = hist['Low'].iloc[i]
            if intraday_low < rally_day1_low:
                rally_invalidated = True
                # Reset — try to find a new rally attempt after this point
                rally_day1_idx  = None
                rally_day1_low  = None
                rally_day1_date = None
                # Recursively look for new Day 1 after the invalidation
                new_low_idx = i
                for j in range(i, n):
                    if closes[j] < closes[new_low_idx]:
                        new_low_idx = j
                for j in range(new_low_idx + 1, n):
                    if closes[j] > closes[j-1]:
                        rally_day1_idx  = j
                        rally_day1_low  = hist['Low'].iloc[j]
                        rally_day1_date = dates[j]
                        break
                break

    # ── Step 5: Follow-Through Day — Day 4+ of rally attempt ──────────────
    ftd_date  = None
    ftd_pct   = None
    rally_day = None   # current day # of rally attempt

    if rally_day1_idx is not None:
        rally_day = n - rally_day1_idx  # 1-indexed (Day 1 = first up day)

        # Only look for FTD from Day 4 onward
        for i in range(rally_day1_idx + 3, n):  # +3 = Day 4 (0-indexed offset)
            pc, cc = closes[i-1], closes[i]
            pv, cv = volumes[i-1], volumes[i]
            if not all([pc, cc, pv, cv]) or pc == 0:
                continue
            pct = (cc - pc) / pc * 100
            if pct >= 1.25 and cv > pv:
                ftd_date = dates[i]
                ftd_pct  = round(pct, 2)
                break

        # FTD only counts if it wasn't invalidated after it occurred
        if ftd_date and rally_invalidated and ftd_date < rally_day1_date:
            ftd_date = None
            ftd_pct  = None

    # ── Step 6: Determine stage ────────────────────────────────────────────
    if total_dist >= 5:
        stage       = "MARKET IN CORRECTION"
        stage_color = "red"
        action      = "Avoid new buys. Raise cash. Protect profits."
    elif ftd_date and not rally_invalidated:
        if total_dist >= 3:
            stage       = "RALLY UNDER PRESSURE"
            stage_color = "yellow"
            action      = "Follow-through confirmed but distribution elevated. Reduce size. Tighten stops."
        else:
            stage       = "CONFIRMED RALLY"
            stage_color = "green"
            action      = "Follow-through day confirmed. Green light for quality setups."
    elif rally_day1_idx is not None and not rally_invalidated:
        stage       = "RALLY ATTEMPT"
        stage_color = "orange"
        day_str     = f"Day {rally_day}" if rally_day else ""
        action      = f"Rally attempt in progress ({day_str}). Wait for follow-through day (Day 4+, up ≥1.25% on higher volume)."
    elif total_dist >= 3:
        stage       = "RALLY UNDER PRESSURE"
        stage_color = "yellow"
        action      = "Be cautious. Tighten stops. No aggressive new buys."
    else:
        stage       = "CONFIRMED RALLY"
        stage_color = "green"
        action      = "Market healthy. Low distribution. Follow rotation signals."

    # ── Build result ───────────────────────────────────────────────────────
    return {
        "stage":               stage,
        "color":               stage_color,
        "action":              action,
        "distribution_days":   dist_count,
        "stalling_days":       stall_count,
        "total_distribution":  total_dist,
        "distribution_dates":  [d for d, _ in dist_days],
        "follow_through_day":  ftd_date,
        "follow_through_pct":  ftd_pct,
        "rally_attempt_day1":  rally_day1_date,
        "rally_day":           rally_day,
        "rally_invalidated":   rally_invalidated,
        "window":              f"{DIST_WINDOW} sessions",
        "spy_last_close":      round(closes[-1], 2) if closes else None,
        "spy_last_date":       dates[-1] if dates else None,
        "computed_at":         datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET"),
    }


if __name__ == "__main__":
    result = compute_market_stage()
    import json
    print(json.dumps(result, indent=2))

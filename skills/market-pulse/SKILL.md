---
name: market-pulse
description: Daily market analysis delivered 3x (AM, Midday, PM). Analyzes market drivers, smart money flow, sector rotation, portfolio impact, and new opportunities. Triggers on "market pulse", "market analysis", "what's moving", or scheduled cron events.
---

# Market Pulse

Automated market intelligence report delivered to Dan's email at:
- **9:45 AM PST** (Pre-market/Open)
- **12:30 PM PST** (Midday check)
- **6:00 PM PST** (Close summary)

## Report Structure

### 1. Market Snapshot
- SPY, QQQ, IWM, VIX levels and % change
- Sector ETF heatmap (XLK, XLF, XLE, XLI, XLV, XLB, XLC, XLY, XLP, XLU, XLRE)
- 10Y Treasury yield movement

### 2. What's Driving the Market
- Top 3 macro themes (Fed, earnings, geopolitics)
- Key news catalysts
- Unusual volume/options activity

### 3. Smart Money Flow
- Sector rotation signals (RS leaders/laggards)
- Institutional accumulation/distribution
- Dark pool activity indicators

### 4. Portfolio Impact
Reference Dan's baskets:
- **Defense:** LHX, LMT, NOC, GE
- **Grid-to-Chip:** PWR, VRT, GEV
- **TopVOO:** 29 tech/growth stocks
- **Core ETFs:** COPX, GLD, GLDM, ITA, IWM, NLR, VOO, XLI

Show which baskets are working/struggling today.

### 5. Action Items
- Positions to trim (broken charts)
- Positions to add (fresh breakouts)
- New opportunities from the VUG universe

### 6. Theme Watch
- Emerging patterns smart money is chasing
- Sector/industry gaining momentum

## Execution

Run: `python3 skills/market-pulse/scripts/pulse.py [am|mid|pm]`

Output is formatted for email delivery via the message tool.

# MEMORY.md - Long Term Memory

## Project Context: InvestIQ
### v3.5 "Breakout Hunter" (Feb 2026) — CURRENT
- **Philosophy:** "6-month consolidation, then breakout." Rejects steady uptrends.
- **Key Criteria:**
  - Breakout Pattern: Flat ceiling (<10% drift over 6mo) — 20 pts
  - Consolidation: Base depth < 40% — 10 pts
  - Volume Dry-up: < 1.0x avg — 5 pts
  - Industry Strength: Sector vs SPY — 10 pts
- **Tech Stack:** Python (rater.py), Flask (app.py), SQLite (market_data.db)
- **Web App:** http://10.0.0.213:18791 (LaunchAgent for auto-restart)

### Additional Scripts
- `canslim.py` — William O'Neil 7-factor rating
- `value_growth_scan.py` — PE/PEG/Growth filter
- `rate_holdings.py`, `rate_fundamentals.py`, `scan_all_top10.py`

## Dan's Portfolio Baskets
1. **Defense:** LHX, LMT, NOC, GE
2. **Grid-to-Chip:** PWR, VRT, GEV
3. **TopVOO:** 29 stocks (MSFT, AMZN, GOOGL, META, NVDA, AMD, etc.)
4. **Core ETFs:** COPX, GLD, GLDM, ITA, IWM, NLR, VOO, XLI

## User Preferences
- **Dan:** Likes "Quality Growth". Dislikes "fixed row-based date calculations" (drift risk).
- **Communication:** Needs proactive health checks (Liveness Pulse cron installed).
- **Formatting:** No markdown tables in Telegram — use code blocks with ASCII.

## Top Picks (as of Feb 1, 2026)
- **Breakout:** MLM (A+), O (A), MSCI (A-), PWR (B+)
- **CANSLIM:** LLY (100/100 — perfect score)
- **Value Growth:** VRT (PEG 1.02)

## Voice Call Setup (Feb 4, 2026)
- OpenClaw has `@openclaw/voice-call` plugin (currently disabled)
- Requires: Twilio/Telnyx/Plivo account + phone number
- Also needs: ngrok or Tailscale for webhook tunneling
- Guide saved: `VOICE_CALL_SETUP.md`
- Dan asked me to figure this out overnight

## Email Configured (Feb 4, 2026)
- Email: ***REMOVED***
- Config: `.email_config.ini`
- Script: `email_sender.py`
- Can now send emails on demand

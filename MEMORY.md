# MEMORY.md - Long Term Memory

## Project Context: InvestIQ
### v4.4 "Revenue Gate" (Feb 12, 2026) — CURRENT
- **Philosophy:** "BOTH years >= 10% revenue growth required." Strict 2-year consistency gate.
- **Key Criteria (100 Point Scale):**
  - Sales Growth (2yr): 0-30 pts (both years >= 10% required for any points)
  - Breakout Pattern: 22 pts (flat ceiling <10% drift)
  - Trend Alignment: 8 pts (price > 50d > 200d)
  - Technical: 53 pts max (Consolidation, Volume, 52W, Volatility)
  - Growth: 33 pts max (Sales + Earnings)
  - Quality: 18 pts max (ROE, Margin, PEG, FCF)
  - Context: 10 pts max (Sector, RS, Size penalty)
- **Tech Stack:** Python (rater.py), Flask (app.py), SQLite (market_data.db)
- **Web App:** https://qortexai.com (GitHub Pages, reads from cached JSON)
- **Data Files:**
  - `top_stocks.json` — Top 100 filtered stocks (displayed on site)
  - `all_stocks.json` — All 1,012 stocks with full criteria breakdown
  - **Website reads from local cache** — no backend API needed for detail view

### Additional Scripts
- `canslim.py` — William O'Neil 7-factor rating
- `value_growth_scan.py` — PE/PEG/Growth filter
- `rate_holdings.py`, `rate_fundamentals.py`, `scan_all_top10.py`

## Dan's Portfolio Baskets (ALWAYS verify from Supabase - never trust this list blindly)
1. **AI Semis (10):** ALAB, AMD, ANET, ASML, AVGO, MRVL, MU, STX, TSM, WDC
2. **Biotech (4):** ALNY, HALO, LLY, XBI
3. **Defense & Aerospace (10):** EUAD, HEI, HII, HWM, LHX, LMT, NOC, RTX, SHLD, UFO
4. **Grid-to-Chip (12):** APH, CCJ, CEG, ETN, FIX, GEV, GRID, HUBB, NLR, NVT, PWR, VRT
5. **IRA Core ETFs (6):** COPX, DXJ, GLD, SIL, VOO, XLI
6. **Trading Account (3):** GOOGL, VGT, VUG
7. **themastertest (1):** NVDA
- ⚠️ Dan corrected me MULTIPLE TIMES for using stale tickers. Source of truth = Supabase ONLY.

## User Preferences
- **Dan:** Likes "Quality Growth". Dislikes "fixed row-based date calculations" (drift risk).
- **Communication:** Needs proactive health checks (Liveness Pulse cron installed). "Send" always means email me.
- **Formatting:** No markdown tables in Telegram — use code blocks with ASCII.

## Top Picks (as of Feb 12, 2026)
- **Top 5 (Revenue Gate):** RBA (96), IBKR (94), WTM (93), RNR (92), HALO (91)
- **Breakout:** MLM (A+), O (A), MSCI (A-), PWR (B+)
- **CANSLIM:** LLY (100/100 — perfect score)
- **Value Growth:** VRT (PEG 1.02)
- **TenX Hunter Best:** MU (73), NU (72), ANET (67), NVDA (67)

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

## Telegram Group Chat (Feb 7, 2026)
- **Group:** "InvestIQ Terminal" (id: -1003824122919)
- **Privacy Mode:** Disabled — I see all messages
- **Reply Behavior:** Reply to ALL messages (not just tags)
- Dan's preference: "reply to all messages in this group chat"

## Critical Rules (learned the hard way)
- **Frontend = templates/index.html** (Flask serves this, NOT root index.html)
- **Portfolio source of truth = Supabase** (never local JSON/memory)
- **Never skip baskets** — show everything exactly as Supabase returns
- **Realtime = realtime** — use range=1d&interval=1m for intraday prices
- **ETFs = technical signals only** (no fundamentals available)
- **Don't commit large binaries to git** — 33MB SQLite DB broke Vercel deployment (Mar 5, 2026)
- **Domain searches on GoDaddy get front-run** — always use `whois` CLI first, buy on Cloudflare
- **NEVER use stale portfolio from memory** — Dan corrected this multiple times. ALWAYS fetch Supabase.

## Website Features (as of Mar 4, 2026)
- Dashboard, Portfolio, Rotation Scan, Watchlist tabs (existing)
- Signal column on both Portfolio + Watchlist tabs
- Market Pulse tab (market internals dashboard)
- Catalyst Calendar tab (earnings + FOMC dates)
- Sell Signal Check cron (5 PM ET M-F)

## Build Roadmap (Dan approved Mar 4)
- Phase 2: Thesis Journal, Trade Journal + P&L Attribution
- Phase 3: R/R Calculator, Insider Transactions (SEC Form 4), Correlation Dashboard, Pre-Trade Checklist

## Model Preference
- **Always use anthropic/claude-opus-4-6** — Dan's explicit preference (Mar 4, 2026)

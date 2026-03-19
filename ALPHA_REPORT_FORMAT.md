# Daily Alpha Report — Format Specification
## Saved from: March 17, 2026 (Dan's preferred format)

This file defines the exact format, sections, and structure for the Daily Alpha Report HTML.
Always follow this spec precisely. Do not invent new sections or change structure.

---

## Report Identity

- **Filename**: `alpha_report_YYYYMMDD.html`
- **Email to**: `dbirru@gmail.com`
- **Telegram confirm**: InvestIQ Terminal group (`-1003824122919`)
- **Header**: `📊 Daily Alpha Report — [Month DD, YYYY]`
- **Subtitle**: `Portfolio Intelligence for Dan Birru`
- **Dateline**: `[Weekday, Month DD, YYYY] | Market Close 4:00 PM EST`

---

## Required Sections (in order)

### 1. 🌐 Market Snapshot
Ticker cards in a grid row. Each card shows: index/ETF name, price/value, % change (▲/▼), label.

Required tickers:
- S&P 500 (index level, not ETF)
- NASDAQ (composite)
- DOW (DJIA)
- SPY (ETF price)
- QQQ (ETF price)
- IWM (ETF price — small cap health indicator)

### 2. 🔭 Macro Drivers & Key Indicators
Grid of macro indicators with value, direction (▲/▼), and brief narrative paragraph below.

Required indicators:
- VIX (fear gauge — note the significance of the level/move)
- DXY (dollar — note impact on international holdings)
- 10-Year Yield (note impact on growth stocks)
- WTI Oil (note impact on energy/industrials)
- Bitcoin (risk sentiment proxy)

**Below the grid:** 3–4 concise narrative paragraphs interpreting macro conditions and portfolio implications.

### 3. 📰 Today's Key Movers & Catalysts
4–6 callout cards covering the major stories of the day. Each card has:
- Emoji icon (relevant to sector/theme)
- Ticker(s) + % change in bold
- 2–4 sentence analysis: WHY it moved + what it means for Dan's portfolio specifically
- Include both winners AND losers (don't skip bad days)

### 4. 💰 Smart Money Flows
List of 6–8 flow signals with green/red/yellow indicators:
- 🟢 Heavy Inflow
- 🔴 Outflow
- 🟡 Neutral / Mixed
- Add a footnote: *Flow analysis based on price action, volume signals, and sector momentum.*

### 5. 🌡️ Sector Temperature Gauge
7–9 sector rows with temperature emoji and avg % move:
- 🔥 Hot (>2% avg)
- 🟢 Warm (0–2%)
- 🟡 Neutral (~0%)
- 🔴 Cool (negative)
- ❄️ Cold (<−2%)

### 6. 💼 Portfolio Positioning — Live Holdings
**CRITICAL: ALWAYS fetch live from Supabase baskets. NEVER hardcode tickers.**

Show every basket in order:
1. 🧠 AI Semis (% of IRA)
2. 🧬 Biotech (% of IRA)
3. 🛡️ Defense & Aerospace (% of IRA)
4. ⚡ Grid-to-Chip (% of IRA)
5. 📦 IRA Core ETFs (% of IRA)
6. 📈 Trading Account (% of Total)
7. Any other baskets from Supabase

For each holding show:
- Ticker, current price, % weight in basket, % day change
- 🚀 emoji for movers >3%, ⚠️ for drops >3%
- Basket-level estimated return for the day

### 7. 🎯 5 High-Conviction Ideas
5 ideas in card format. Each card has:
- Name: **Company — Brief Thesis Title**
- Conviction badge: ⭐ HIGH CONVICTION — HOLD/ADD/BUY or 👀 WATCH — EVALUATE
- 3–5 sentence thesis (specific to Dan's existing position or new opportunity)
- Entry Zone / Price / Weight / Catalyst / Action fields
- Basket reference if it's an existing position

Ideas should be:
- 3–4 from existing portfolio (reinforce or question existing positions)
- 1–2 new ideas or sector calls
- Always grounded in today's price action

### 8. 💭 Portfolio Positioning Thoughts
2–3 paragraph summary covering:
- Overall portfolio performance estimate for the day
- One thing to watch or consider this week
- Forward-looking macro or sector note

---

## Style Guide

- **Color scheme**: Dark navy/black background with green/gold accents (like a Bloomberg terminal)
- **Font**: Monospace or clean sans-serif
- **Numbers**: Always show ▲/▼ arrows with color (green = up, red = down)
- **Tone**: Professional but direct. No fluff. Dan is a sophisticated investor.
- **Length**: Aim for ~40–50KB HTML — comprehensive but not padded
- **Mobile-friendly**: Cards should stack on mobile

---

## Data Sources (always live, never cached or hallucinated)

```bash
# Run this to get all price data:
cd /Users/dansmacmini/.openclaw/workspace && python3 tools/fetch_realtime.py

# Run this to get portfolio baskets:
# Query Supabase baskets table directly (not hardcoded tickers)
```

---

## What Dan Specifically Liked (March 17, 2026)
- The market snapshot ticker grid at the top
- The macro narrative interpreting VIX/DXY/yields in portfolio context
- Individual movers with explanations WHY they moved
- Smart Money Flows visual with green/red/yellow indicators
- Sector Temperature with emoji heat scale
- Portfolio section organized by basket with per-holding % change
- High-Conviction Ideas tied to his actual positions
- Consistent, clean dark-theme HTML design

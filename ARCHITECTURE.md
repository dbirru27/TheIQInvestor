# InvestIQ WebApp - Implementation Architecture

**Version:** 3.5 "Breakout Hunter"  
**Last Updated:** February 4, 2026  
**Author:** Dagnachew Birru (Dan) + Danswiz AI

---

## 📋 Executive Summary

InvestIQ is a Flask-based stock scanning web application that implements a "Breakout Hunter" investment strategy. The app rates stocks based on 10 criteria across momentum, quality, and growth factors, with real-time data from Yahoo Finance and automated daily scans.

---

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │  Dashboard  │    │ Stock Detail│    │   TradingView Chart │ │
│  │  (Table)    │◄──►│  (Analysis) │◄──►│   (with indicators) │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP/API
┌────────────────────▼────────────────────────────────────────────┐
│                      FLASK BACKEND                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   Routes    │    │   Rater     │    │   Data Fetcher      │ │
│  │  (app.py)   │◄──►│ (rater.py)  │◄──►│  (yfinance)         │ │
│  └─────────────┘    └──────┬──────┘    └─────────────────────┘ │
│                            │                                     │
│                     ┌──────▼──────┐                             │
│                     │  MarketDB   │                             │
│                     │(SQLite Cache)│                            │
│                     └─────────────┘                             │
└────────────────────┬────────────────────────────────────────────┘
                     │ Git Push
┌────────────────────▼────────────────────────────────────────────┐
│                      DEPLOYMENT                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   GitHub    │───►│   Vercel    │───►│   www.qortexai.com  │ │
│  │   (Repo)    │    │   (Hosting) │    │   (Production)      │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                      AUTOMATION (CRON)                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ 2 AM Cache  │    │ 6 AM Scan   │    │  Market Reports     │ │
│  │  Refresh    │    │   + Push    │    │   (3x Daily)        │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 💻 Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | HTML + TailwindCSS + Vanilla JS | Responsive UI, mobile-friendly |
| **Charts** | TradingView Widget | Professional charting (free tier) |
| **Backend** | Flask (Python) | Web server, API endpoints |
| **Data Source** | yfinance (Yahoo Finance) | Real-time stock data |
| **Database** | SQLite | Local caching of prices/fundamentals |
| **Automation** | OpenClaw Cron | Scheduled scans and reports |
| **Hosting** | Vercel | Serverless deployment |
| **Version Control** | Git + GitHub | Code management |

---

## 📁 Project Structure

```
workspace/
├── app.py                      # Flask main application
├── rater.py                    # Core rating engine (Breakout Hunter)
├── market_data.py              # SQLite database interface
├── templates/
│   └── index.html              # Single-page application UI
├── top_stocks.json             # Daily scan results
├── market_data.db              # SQLite cache (prices, fundamentals)
├── 
├── Scripts/
│   ├── update_web_scan.py      # Daily scan + Git push
│   ├── refresh_cache.py        # Nightly cache refresh
│   ├── fetch_realtime.py       # Real-time price fetcher
│   └── get_russell1000.py      # Russell 1000 ticker download
│
└── Skills/
    └── market-pulse/           # Automated market reports
```

---

## 🔧 Core Components

### 1. Rating Engine (`rater.py`)

**10-Factor Scoring System:**

| Category | Criteria | Weight | Threshold |
|----------|----------|--------|-----------|
| **Momentum** | Trend Alignment | 5 pts | Price > SMA50 > SMA200 |
| | Breakout Pattern | 20 pts | Flat base + near highs |
| | Consolidation | 10 pts | Base depth < 40% |
| | Volume Dry-up | 5 pts | Vol < 1.2x average |
| **Quality** | Operating Margin | 10 pts | > 10% |
| | FCF Quality | 5 pts | Positive free cash flow |
| | Debt Safety | 5 pts | Safe debt ratios |
| **Growth** | Sales Growth | 5 pts | > 10% YoY |
| | Earnings Growth | 5 pts | > 15% YoY |
| **Industry** | Industry Strength | 10 pts | Sector beats SPY |

**Scoring:**
- A: 50+ points
- B: 35-49 points
- C: 20-34 points
- D: 10-19 points
- F: < 10 points

### 2. Database Layer (`market_data.py`)

**SQLite Schema:**
```sql
-- Tickers table
CREATE TABLE tickers (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    industry TEXT,
    last_updated DATE
);

-- Price history
CREATE TABLE prices (
    symbol TEXT,
    date DATE,
    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
    PRIMARY KEY (symbol, date)
);

-- Fundamentals cache
CREATE TABLE fundamentals (
    symbol TEXT PRIMARY KEY,
    data JSON,
    updated_at DATETIME
);
```

**Smart Fetching:**
- Checks local cache first (24-hour TTL)
- Downloads only missing/new data
- Avoids Yahoo Finance rate limits

### 3. Frontend (`templates/index.html`)

**Two-View Architecture:**

1. **Dashboard View**
   - Sortable table of top-rated stocks
   - Quick ticker input
   - Last scan timestamp

2. **Detail View**
   - TradingView chart (timeframe persists)
   - 8-factor criteria breakdown
   - Valuation metrics (P/E, PEG)
   - Analyst ratings
   - News feed
   - Ticker input (always accessible)

**Key Features:**
- Mobile-responsive (sidebar navigation)
- Enter key support for ticker input
- LocalStorage for chart settings
- Grade badges (A/B/C/D/F color-coded)

---

## 🔄 Data Flow

### Daily Scan Process
```
1. 2:00 AM - Cache Refresh (refresh_cache.py)
   └─> Downloads price data for 1,014 tickers
   └─> Rate limited: 0.5s delay between requests

2. 6:00 AM - Morning Scan (update_web_scan.py)
   └─> Runs BreakoutRater on all tickers
   └─> Saves results to top_stocks.json
   └─> Git commit + push to GitHub

3. 6:01 AM - Vercel Auto-Deploy
   └─> Detects new commit on main branch
   └─> Builds and deploys to www.qortexai.com
```

### Real-Time Rating (On-Demand)
```
User enters ticker → API call to /api/rate/{ticker}
                           ↓
                    Check SQLite cache
                           ↓
              Cache miss? → Fetch from Yahoo Finance
                           ↓
                    Run BreakoutRater
                           ↓
                    Return JSON with grade + criteria
```

---

## ⏰ Automation Schedule

| Job | Schedule | Purpose |
|-----|----------|---------|
| Nightly Cache Refresh | 2:00 AM PST | Download price data for Russell 1000 |
| Morning Scan | 6:00 AM PST | Rate all stocks, update website |
| Market Pulse AM | 8:00 AM PST | Pre-market report (email) |
| Market Pulse Midday | 12:30 PM PST | Midday market update |
| Market Pulse PM | 3:00 PM PST | Closing bell summary |
| Daily Briefing | 3:15 PM PST | Portfolio performance check |
| Closing Scan | 3:30 PM PST | InvestIQ data update |
| Weekly Summary | Friday 6:30 PM | Comprehensive week review |
| Liveness Pulse | Every 1 hour | Health check heartbeat |

---

## 🚀 Deployment Architecture

```
Local Development (Mac Mini)
├── Flask app on port 18791
├── SQLite database
└── LaunchAgent for auto-restart

GitHub Repository
└── Main branch
    ├── app.py
    ├── templates/
    └── top_stocks.json (updated daily)

Vercel Production
├── Serverless functions (app.py)
├── Static assets (templates, CSS)
└── Custom domain: www.qortexai.com
```

**CI/CD Flow:**
1. Local development on Mac Mini
2. Git push to GitHub
3. Vercel auto-deploy (30 seconds)
4. Website updated globally

---

## 📊 Key Features

### 1. Breakout Hunter Strategy
- Identifies stocks with 6-month consolidation
- Requires flat ceiling (<10% drift)
- Volume dry-up before breakout
- Industry strength relative to SPY

### 2. Russell 1000 Universe
- 1,014 tickers (expanded from original 159)
- Combines: Russell 1000 + VUG + Personal holdings
- Daily cache refresh with rate limiting

### 3. Portfolio Tracking
- 4 baskets (Core + 3 Momentum)
- 100% allocation mapped
- Real-time basket performance

### 4. Model Fallback Chain
```
Flash (primary) → Kimi → Opus
```
- Ensures uptime even if models fail
- Flash for routine tasks
- Opus for coding/analysis

---

## 🔐 Security & Performance

**Security:**
- No API keys stored in code
- SQLite local only (no remote DB)
- No user authentication (personal use)

**Performance:**
- SQLite caching reduces API calls by ~90%
- Rate limiting prevents Yahoo Finance bans
- Lazy loading of chart data
- 30-second Vercel deploys

---

## 🎯 Future Enhancements

1. **Custom Charting** - Replace TradingView with persistent indicators
2. **Alert System** - Breakout notifications via Telegram
3. **Backtesting** - Historical performance of rating system
4. **Options Flow** - Integrate unusual options activity
5. **Mobile App** - React Native wrapper

---

## 📞 Contact & Support

- **Developer:** Dagnachew Birru (Dan)
- **AI Assistant:** Danswiz
- **Website:** www.qortexai.com
- **Repository:** github.com/danswiz/InvestIQ

---

*Generated by Danswiz on February 4, 2026*

"""
Deep Research — Multi-agent stock research pipeline using Anthropic Claude.

7-agent pipeline: Planner → Researcher → Quant → Qual → Moderator → Writer → Risk
Uses yfinance for live market data and InvestIQ local data files for proprietary scores.
"""

import json
import os
import time
import traceback
import urllib.request
from datetime import datetime

import anthropic
import yfinance as yf

# ── Constants ──
MODEL = "claude-opus-4-6"
MODEL_FAST = "claude-sonnet-4-6"  # For verification passes — fast + cheap
MAX_RESEARCH_PASSES = 3
MAX_CYCLES = 5

# Intent → required data types
INTENT_DATA_MAP = {
    "outlook": ["stock_info", "earnings", "price_history", "analyst_recommendations"],
    "comparison": ["stock_info", "earnings", "price_history"],
    "catalyst": ["stock_info", "earnings", "price_history", "analyst_recommendations"],
    "historical": ["stock_info", "price_history", "earnings"],
    "recommendation": ["stock_info", "earnings", "price_history", "analyst_recommendations"],
    "general": ["stock_info", "earnings", "price_history"],
}

# Data sources the Data Scout can tap into
DATA_SOURCES = {
    "hunter": "Top stocks from the IQ scoring system (1000+ universe, sorted by score/grade). Use for: prescreen, top picks, best stocks, highest rated.",
    "portfolio": "User's actual portfolio holdings from Supabase, organized by baskets (AI Semis, Biotech, Defense, etc.). Use for: my portfolio, my holdings, my positions.",
    "ewros": "EWROS rotation momentum leaders — stocks with strong rotation scores (60+). Use for: rotation, momentum, sector leaders, what's rotating.",
    "watchlist": "User's watchlist entries. Use for: my watchlist, watching, tracking.",
    "screener": "Filtered stock universe with custom criteria. Use for: screen, filter, find stocks matching criteria.",
    "sell_signals": "Current sell signal alerts for portfolio. Use for: sell signals, what to sell, risk alerts.",
    "market_internals": "Market health dashboard — indices, VIX, sector performance, breadth. Use for: market condition, market health, is it safe to buy.",
    "calendar": "Upcoming earnings dates and FOMC schedule. Use for: earnings, upcoming catalysts, calendar.",
    "insider": "Insider transaction signals. Use for: insider buying, insider selling, insider activity.",
}


def _load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            with open(_data_path(".env")) as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        key = line.strip().split("=", 1)[1]
        except FileNotFoundError:
            pass
    return key


def _load_portfolio_tickers():
    """Fetch portfolio holdings from Supabase. Returns dict of {basket_name: [tickers]}."""
    supabase_url = os.environ.get('SUPABASE_URL', 'https://jvgxgfbthfsdqtvzeuqz.supabase.co')
    supabase_key = os.environ.get('SUPABASE_KEY', '')
    if not supabase_key:
        try:
            with open(os.path.join(os.path.dirname(__file__), '.env')) as f:
                for line in f:
                    if line.startswith('SUPABASE_KEY='):
                        supabase_key = line.strip().split('=', 1)[1]
        except FileNotFoundError:
            pass
    if not supabase_key:
        return {}, []

    try:
        url = f'{supabase_url}/rest/v1/baskets?select=name,holdings(ticker)&order=sort_order'
        req = urllib.request.Request(url, headers={
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}'
        })
        resp = urllib.request.urlopen(req, timeout=8)
        baskets = json.loads(resp.read())
        
        basket_map = {}
        all_tickers = []
        for b in baskets:
            name = b['name']
            tickers = [h['ticker'] for h in b.get('holdings', [])]
            basket_map[name] = tickers
            all_tickers.extend(tickers)
        return basket_map, list(set(all_tickers))
    except Exception:
        return {}, []


def _is_portfolio_query(query):
    """Detect if user is asking about their portfolio."""
    q = query.lower()
    portfolio_keywords = ['my portfolio', 'my holdings', 'my positions', 'my stocks', 
                         'my baskets', 'my investments', 'positions in my']
    return any(kw in q for kw in portfolio_keywords)


def _data_path(filename):
    """Resolve data file path — tries script dir first, then cwd."""
    base = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, filename)
    if os.path.exists(p):
        return p
    p2 = os.path.join(os.getcwd(), filename)
    if os.path.exists(p2):
        return p2
    return p  # return original, let caller handle FileNotFoundError


def _fetch_data_source(source, params=None):
    """Surgically fetch data from a specific InvestIQ source. Returns a compact summary, not raw dumps."""
    
    if source == "hunter":
        # Load top stocks, sorted by score
        try:
            with open(_data_path("data/all_stocks.json")) as f:
                data = json.load(f)
            stocks = data.get("stocks", {})
            # Sort by score descending, return top N
            limit = (params or {}).get("limit", 20)
            sorted_stocks = sorted(stocks.items(), key=lambda x: x[1].get("score", 0) or 0, reverse=True)[:limit]
            return {
                "source": "hunter",
                "count": len(sorted_stocks),
                "stocks": [
                    {
                        "ticker": t, "name": s.get("name", t), "score": s.get("score", 0),
                        "grade": s.get("grade", "?"), "ewros_score": s.get("ewros_score", 0),
                        "sector": s.get("sector", ""), "industry": s.get("industry", ""),
                        "current_price": s.get("current_price"),
                        "revenue_growth": s.get("revenue_growth"), "earnings_growth": s.get("earnings_growth"),
                        "trailing_pe": s.get("trailing_pe"), "forward_pe": s.get("forward_pe"),
                        "iq_edge": s.get("iq_edge", 0), "moonshot_score": s.get("moonshot_score", 0),
                        "technical_score": s.get("technical_score", 0), "growth_score": s.get("growth_score", 0),
                        "quality_score": s.get("quality_score", 0), "context_score": s.get("context_score", 0),
                    }
                    for t, s in sorted_stocks
                ]
            }
        except Exception as e:
            return {"source": "hunter", "error": str(e)}

    elif source == "portfolio":
        basket_map, all_tickers = _load_portfolio_tickers()
        # Also load scores for portfolio tickers
        try:
            with open(_data_path("data/all_stocks.json")) as f:
                all_stocks = json.load(f).get("stocks", {})
        except Exception:
            all_stocks = {}
        
        baskets = {}
        for name, tickers in basket_map.items():
            baskets[name] = [
                {
                    "ticker": t, "score": all_stocks.get(t, {}).get("score", 0),
                    "grade": all_stocks.get(t, {}).get("grade", "?"),
                    "ewros_score": all_stocks.get(t, {}).get("ewros_score", 0),
                    "current_price": all_stocks.get(t, {}).get("current_price"),
                }
                for t in tickers
            ]
        return {"source": "portfolio", "baskets": baskets, "total_tickers": len(all_tickers)}

    elif source == "ewros":
        try:
            with open(_data_path("data/all_stocks.json")) as f:
                data = json.load(f)
            stocks = data.get("stocks", {})
            limit = (params or {}).get("limit", 20)
            ewros_leaders = sorted(
                [(t, s) for t, s in stocks.items() if (s.get("ewros_score") or 0) >= 60],
                key=lambda x: x[1].get("ewros_score", 0) or 0, reverse=True
            )[:limit]
            return {
                "source": "ewros",
                "count": len(ewros_leaders),
                "stocks": [
                    {
                        "ticker": t, "name": s.get("name", t), "ewros_score": s.get("ewros_score", 0),
                        "score": s.get("score", 0), "grade": s.get("grade", "?"),
                        "sector": s.get("sector", ""), "current_price": s.get("current_price"),
                    }
                    for t, s in ewros_leaders
                ]
            }
        except Exception as e:
            return {"source": "ewros", "error": str(e)}

    elif source == "sell_signals":
        try:
            with open(_data_path("data/sell_signals.json")) as f:
                return {"source": "sell_signals", "data": json.load(f)}
        except Exception:
            return {"source": "sell_signals", "data": {"signals": []}}

    elif source == "calendar":
        try:
            with open(_data_path("data/earnings_calendar.json")) as f:
                cal = json.load(f)
            # Return just upcoming 2 weeks
            return {"source": "calendar", "earnings": cal.get("earnings", [])[:30], "fomc": cal.get("fomc", [])}
        except Exception:
            return {"source": "calendar", "earnings": [], "fomc": []}

    elif source == "insider":
        try:
            with open(_data_path("data/insider_universe.json")) as f:
                data = json.load(f)
            signals = data.get("signals", {})
            # Only return notable signals (score != 0)
            notable = {t: s for t, s in signals.items() if s.get("ins_score", 0) != 0}
            top = sorted(notable.items(), key=lambda x: abs(x[1].get("ins_score", 0)), reverse=True)[:20]
            return {
                "source": "insider",
                "signals": [{"ticker": t, "ins_score": s.get("ins_score"), "signal": s.get("signal")} for t, s in top]
            }
        except Exception:
            return {"source": "insider", "signals": []}

    elif source == "watchlist":
        # Fetch from Supabase
        supabase_url = os.environ.get('SUPABASE_URL', 'https://jvgxgfbthfsdqtvzeuqz.supabase.co')
        supabase_key = os.environ.get('SUPABASE_KEY', '')
        if not supabase_key:
            try:
                with open(_data_path('.env')) as f:
                    for line in f:
                        if line.startswith('SUPABASE_KEY='):
                            supabase_key = line.strip().split('=', 1)[1]
            except FileNotFoundError:
                pass
        try:
            url = f'{supabase_url}/rest/v1/watchlist_items?select=ticker,watchlist_id'
            req = urllib.request.Request(url, headers={
                'apikey': supabase_key, 'Authorization': f'Bearer {supabase_key}'
            })
            items = json.loads(urllib.request.urlopen(req, timeout=8).read())
            return {"source": "watchlist", "items": items}
        except Exception:
            return {"source": "watchlist", "items": []}

    elif source == "screener":
        # Return top by custom params
        try:
            with open(_data_path("data/all_stocks.json")) as f:
                data = json.load(f)
            stocks = data.get("stocks", {})
            sort_by = (params or {}).get("sort_by", "score")
            limit = (params or {}).get("limit", 20)
            filtered = sorted(stocks.items(), key=lambda x: x[1].get(sort_by, 0) or 0, reverse=True)[:limit]
            return {
                "source": "screener",
                "stocks": [
                    {"ticker": t, "score": s.get("score", 0), "grade": s.get("grade", "?"),
                     "ewros_score": s.get("ewros_score", 0), "sector": s.get("sector", ""),
                     sort_by: s.get(sort_by)}
                    for t, s in filtered
                ]
            }
        except Exception as e:
            return {"source": "screener", "error": str(e)}

    return {"source": source, "error": "Unknown source"}


def _preprocess_query(query):
    """Detect references to the website's own pages/tabs and translate them to data source names."""
    import re
    q = query
    # Map website URLs to tab names
    url_map = {
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?hunter': 'hunter tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?portfolio': 'portfolio tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?ewros': 'ewros tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?watchlist': 'watchlist tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?screener': 'screener tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?calendar': 'calendar tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?rotation': 'ewros tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?#?/?dashboard': 'hunter tab',
        r'(?:qortexai\.com|theiqinvestor\.com|localhost:\d+)/?$': 'hunter tab',
    }
    for pattern, replacement in url_map.items():
        q = re.sub(r'https?://(?:www\.)?' + pattern, replacement, q, flags=re.IGNORECASE)
    
    # Also catch plain references like "this website", "the site", "the app"
    q = re.sub(r'\b(?:this website|the website|this site|the site|the app|this app)\b', 'the hunter tab', q, flags=re.IGNORECASE)
    
    return q


def _extract_tickers_from_query(query):
    """Hard-coded ticker extraction — catches obvious ticker mentions without LLM."""
    import re
    # Common name → ticker map
    name_map = {
        'nvidia': 'NVDA', 'apple': 'AAPL', 'microsoft': 'MSFT', 'google': 'GOOGL',
        'alphabet': 'GOOGL', 'amazon': 'AMZN', 'tesla': 'TSLA', 'meta': 'META',
        'facebook': 'META', 'netflix': 'NFLX', 'amd': 'AMD', 'intel': 'INTC',
        'broadcom': 'AVGO', 'palantir': 'PLTR', 'coinbase': 'COIN', 'shopify': 'SHOP',
    }
    q = query.lower()
    
    # Check for company names
    found = []
    for name, ticker in name_map.items():
        if name in q:
            found.append(ticker)
    
    # Check for uppercase ticker patterns (1-5 uppercase letters)
    ticker_pattern = re.findall(r'\b([A-Z]{1,5})\b', query)
    # Filter out common words
    noise = {'A', 'I', 'AM', 'IS', 'IT', 'AT', 'IN', 'ON', 'OR', 'AN', 'TO', 'DO', 'GO',
             'NO', 'IF', 'OF', 'UP', 'BY', 'SO', 'AS', 'BE', 'WE', 'HE', 'ME', 'MY',
             'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS',
             'ONE', 'OUR', 'OUT', 'BUY', 'NOW', 'TOP', 'VS', 'ETF', 'IPO'}
    for t in ticker_pattern:
        if t not in noise and len(t) >= 2:
            found.append(t)
    
    return list(set(found))


def run_data_scout(client, state):
    """Determine which data sources to query and fetch only what's needed."""
    _emit(state, "agent_start", {"agent": "Data Scout", "description": "Identifying relevant data sources..."})

    # Preprocess query to resolve URLs and website references
    processed_query = _preprocess_query(state["user_query"])
    state["_processed_query"] = processed_query
    
    # FAST PATH: If query has obvious tickers and no platform references, skip the LLM call
    explicit = _extract_tickers_from_query(state["user_query"])
    is_platform_query = _is_portfolio_query(state["user_query"]) or any(
        kw in processed_query.lower() for kw in ['hunter', 'top stocks', 'prescreen', 'ewros', 'rotation',
            'watchlist', 'screener', 'sell signal', 'calendar', 'insider', 'portfolio', 'my holdings']
    )
    
    if explicit and not is_platform_query:
        _emit(state, "researcher_step", {"step": f"Direct ticker query: {', '.join(explicit)}"})
        state["_scout_data"] = {}  # No sources fetched
        state["_scout_tickers"] = []  # Don't override planner
        state["_scout_plan"] = {"sources": [], "explicit_tickers": explicit, "reasoning": "Direct ticker query"}
        _emit(state, "agent_done", {"agent": "Data Scout", "result": {"tickers": explicit, "mode": "direct"}})
        return state

    sources_desc = "\n".join([f"  - {name}: {desc}" for name, desc in DATA_SOURCES.items()])

    system = f"""You are a data routing agent for an investment research platform called "The IQ Investor" (qortexai.com / theiqinvestor.com).

The platform has these tabs/data sources:
{sources_desc}

Given a user query, determine which data sources to fetch.

Rules:
- Pick ONLY the sources needed (1-3 max). Don't fetch everything.
- For each source, optionally specify params like {{limit, sort_by}}.
- If the query mentions specific tickers, return those in explicit_tickers.
- If the query references "the hunter tab", "top stocks", "prescreen", "this website" → use the "hunter" source.
- If the query references "my portfolio", "my positions", "my holdings" → use the "portfolio" source.
- If the query mentions specific tickers (e.g. "is NVDA a buy?", "analyze AAPL"), put those in explicit_tickers and set sources to EMPTY []. Do NOT fetch hunter/screener data for specific ticker queries.
- Only use sources (hunter, portfolio, ewros, etc.) when the user asks about the PLATFORM'S data (e.g. "top stocks", "my portfolio", "what's rotating")
- If you truly cannot determine what the user wants, set "abort": true with a helpful message.

Respond in JSON only:
{{"sources": [{{"name": "hunter", "params": {{"limit": 10}}}}], "explicit_tickers": [], "reasoning": "brief explanation", "abort": false, "abort_message": ""}}"""

    result = _call_claude(client, system, processed_query, max_tokens=512, model=MODEL_FAST)

    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        scout_plan = json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        scout_plan = {"sources": [], "explicit_tickers": [], "reasoning": "Parse error"}

    # Handle abort
    if scout_plan.get("abort"):
        msg = scout_plan.get("abort_message", "I couldn't determine what data you need. Please try rephrasing your question or mention specific tickers.")
        _emit(state, "error", {"message": msg})
        state["error"] = msg
        return state

    # Fetch each requested source
    fetched_data = {}
    discovered_tickers = list(scout_plan.get("explicit_tickers", []))

    for src in scout_plan.get("sources", []):
        src_name = src.get("name", "")
        src_params = src.get("params", {})
        if src_name in DATA_SOURCES:
            _emit(state, "researcher_step", {"step": f"Fetching {src_name} data..."})
            try:
                data = _fetch_data_source(src_name, src_params)
                fetched_data[src_name] = data

                # Extract tickers from fetched data for downstream agents
                if "stocks" in data:
                    tickers_found = [s["ticker"] for s in data["stocks"]]
                    discovered_tickers.extend(tickers_found)
                    _emit(state, "researcher_step", {"step": f"Found {len(tickers_found)} tickers from {src_name}: {', '.join(tickers_found[:10])}"})
                elif "baskets" in data:
                    for bname, basket_tickers in data["baskets"].items():
                        bt = [s["ticker"] for s in basket_tickers]
                        discovered_tickers.extend(bt)
                    _emit(state, "researcher_step", {"step": f"Found {len(discovered_tickers)} tickers across {len(data['baskets'])} baskets"})
                elif "error" in data:
                    _emit(state, "researcher_step", {"step": f"⚠️ {src_name} error: {data['error']}"})
                else:
                    _emit(state, "researcher_step", {"step": f"⚠️ {src_name} returned no stocks or baskets"})
            except Exception as e:
                _emit(state, "researcher_step", {"step": f"❌ {src_name} failed: {str(e)}"})

    state["_scout_data"] = fetched_data
    state["_scout_tickers"] = list(set(discovered_tickers))
    state["_scout_plan"] = scout_plan

    _emit(state, "agent_done", {
        "agent": "Data Scout",
        "result": {"sources": [s.get("name") for s in scout_plan.get("sources", [])],
                   "tickers_found": len(state["_scout_tickers"]),
                   "reasoning": scout_plan.get("reasoning", "")}
    })
    return state


def _load_investiq_data(tickers):
    """Load InvestIQ scores, SEC fundamentals, and insider signals for given tickers."""
    result = {}

    # all_stocks.json
    try:
        with open(_data_path("data/all_stocks.json")) as f:
            all_stocks = json.load(f).get("stocks", {})
    except Exception:
        all_stocks = {}

    # sec_fundamentals.json
    try:
        with open(_data_path("data/sec_fundamentals.json")) as f:
            sec_data = json.load(f)
    except Exception:
        sec_data = {}

    # insider_universe.json
    try:
        with open(_data_path("data/insider_universe.json")) as f:
            insider_data = json.load(f).get("signals", {})
    except Exception:
        insider_data = {}

    for ticker in tickers:
        t = ticker.upper()
        info = {}

        # IQ scores
        stock = all_stocks.get(t, {})
        if stock:
            info["iq_scores"] = {
                "score": stock.get("score"),
                "grade": stock.get("grade"),
                "sector": stock.get("sector"),
                "industry": stock.get("industry"),
                "technical_score": stock.get("technical_score"),
                "growth_score": stock.get("growth_score"),
                "quality_score": stock.get("quality_score"),
                "context_score": stock.get("context_score"),
                "moonshot_score": stock.get("moonshot_score"),
                "ewros_score": stock.get("ewros_score"),
                "trailing_pe": stock.get("trailing_pe"),
                "forward_pe": stock.get("forward_pe"),
                "revenue_growth": stock.get("revenue_growth"),
                "earnings_growth": stock.get("earnings_growth"),
            }
            # Include criteria breakdown
            criteria = stock.get("criteria", [])
            if criteria:
                info["iq_criteria"] = [
                    {"name": c.get("name"), "passed": c.get("passed"), "value": c.get("value"), "points": c.get("points")}
                    for c in criteria[:15]
                ]

        # SEC fundamentals
        sec = sec_data.get(t, {})
        if sec:
            fundamentals = {}
            for metric in ["revenue", "eps", "net_income", "operating_cash_flow", "free_cash_flow"]:
                entries = sec.get(metric, [])
                if entries:
                    fundamentals[metric] = entries[-8:]  # Last 8 quarters
            if fundamentals:
                info["sec_fundamentals"] = fundamentals

        # Insider signals
        insider = insider_data.get(t, {})
        if insider:
            info["insider_signals"] = {
                "ins_score": insider.get("ins_score"),
                "signal": insider.get("signal"),
                "buys": insider.get("buys"),
                "sells": insider.get("sells"),
                "total_buy_value": insider.get("total_buy_value"),
                "total_sell_value": insider.get("total_sell_value"),
                "reasons": insider.get("reasons", []),
            }

        result[t] = info

    return result


def _fetch_yfinance_data(ticker, data_types):
    """Fetch financial data from yfinance for a single ticker."""
    result = {}
    try:
        stock = yf.Ticker(ticker)

        if "stock_info" in data_types:
            try:
                info = stock.info
                result[f"{ticker}__stock_info"] = json.dumps({
                    k: info.get(k) for k in [
                        "shortName", "sector", "industry", "marketCap", "enterpriseValue",
                        "trailingPE", "forwardPE", "priceToBook", "debtToEquity",
                        "returnOnEquity", "profitMargins", "revenueGrowth", "earningsGrowth",
                        "currentPrice", "targetMeanPrice", "targetHighPrice", "targetLowPrice",
                        "numberOfAnalystOpinions", "recommendationKey", "fiftyTwoWeekHigh",
                        "fiftyTwoWeekLow", "dividendYield", "beta", "shortRatio",
                        "heldPercentInsiders", "heldPercentInstitutions",
                    ] if info.get(k) is not None
                }, default=str)
            except Exception as e:
                result[f"{ticker}__stock_info"] = f"Error: {e}"

        if "earnings" in data_types:
            try:
                earnings = stock.quarterly_earnings
                if earnings is not None and not earnings.empty:
                    result[f"{ticker}__earnings"] = earnings.tail(8).to_string()
                else:
                    result[f"{ticker}__earnings"] = "No quarterly earnings data available"
            except Exception as e:
                result[f"{ticker}__earnings"] = f"Error: {e}"

        if "price_history" in data_types:
            try:
                hist = stock.history(period="6mo")
                if hist is not None and not hist.empty:
                    # Sample weekly to keep context manageable
                    weekly = hist.resample("W").last().tail(26)
                    result[f"{ticker}__price_history"] = weekly[["Close", "Volume"]].to_string()
                else:
                    result[f"{ticker}__price_history"] = "No price history available"
            except Exception as e:
                result[f"{ticker}__price_history"] = f"Error: {e}"

        if "analyst_recommendations" in data_types:
            try:
                recs = stock.recommendations
                if recs is not None and not recs.empty:
                    result[f"{ticker}__analyst_recommendations"] = recs.tail(10).to_string()
                else:
                    result[f"{ticker}__analyst_recommendations"] = "No analyst recommendations available"
            except Exception as e:
                result[f"{ticker}__analyst_recommendations"] = f"Error: {e}"

    except Exception as e:
        result[f"{ticker}__error"] = str(e)

    return result


def _verify_analysis(client, analysis, source_data, analysis_type, use_fast_model=True):
    """Verify an analysis against source data. Uses fast model by default."""
    verify_system = f"""You are a fact-checker for {analysis_type} financial analysis. Your job:

1. Read the ANALYSIS and the SOURCE DATA side by side
2. For each specific claim (number, metric, trend, rating), check if it exists in the source data
3. KEEP claims that are supported by the source data — this includes data from:
   - InvestIQ scout data (scores, grades, growth rates, PE ratios, EWROS)
   - yfinance data (stock_info, earnings, price_history)
   - SEC fundamentals (revenue, EPS)
   - Insider signals
4. REMOVE or mark as [UNVERIFIED] any claim that cites a specific number NOT found in ANY of the source data
5. KEEP general inferences clearly labeled as inferences
6. Output the CLEANED analysis — same structure, but with hallucinated specifics removed
7. PRESERVE ALL tickers — if the analysis covers 10 stocks, the output must still cover 10 stocks. Never drop a stock.

Important: Do NOT add new information. Only remove or flag unsupported claims.
If the analysis is mostly accurate, return it mostly unchanged. Only strip clear fabrications.
Data from InvestIQ (scout data) is TRUSTED — do not strip scores, grades, or growth rates from it."""

    verify_prompt = f"""ANALYSIS TO VERIFY:
{analysis}

SOURCE DATA:
{source_data[:20000]}

Output the verified analysis. Keep the same format, just remove any claims not supported by the source data."""

    return _call_claude(client, verify_system, verify_prompt, max_tokens=16000, model=MODEL_FAST if use_fast_model else None)


def _call_claude(client, system_prompt, user_prompt, max_tokens=16000, model=None):
    """Make a single Claude API call."""
    resp = client.messages.create(
        model=model or MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text


def _emit(state, event_type, data):
    """Emit a progress event if callback is set."""
    cb = state.get("_emit")
    if cb:
        cb(event_type, data)


# ── Agent Functions ──

def run_planner(client, state):
    """Extract tickers, intents, and timeframe from the user query."""
    _emit(state, "agent_start", {"agent": "Planner", "description": "Analyzing your research query..."})

    # Check if this is a portfolio query — if so, fetch real holdings
    portfolio_context = ""
    if _is_portfolio_query(state["user_query"]):
        _emit(state, "researcher_step", {"step": "Detected portfolio query — fetching your holdings from Supabase..."})
        basket_map, all_tickers = _load_portfolio_tickers()
        if all_tickers:
            state["_portfolio_baskets"] = basket_map
            state["_portfolio_tickers"] = all_tickers
            basket_summary = "\n".join([f"  {name}: {', '.join(tickers)}" for name, tickers in basket_map.items()])
            portfolio_context = f"""

IMPORTANT: The user is asking about THEIR PORTFOLIO. Here are their actual holdings:
{basket_summary}

Total unique tickers: {len(all_tickers)}
You MUST include ALL of these tickers in your response. Do NOT default to SPY.
If there are too many tickers (>15), group your analysis by basket/sector but still cover all positions."""

    system = f"""You are a financial research planner. Given a user query about stocks, extract:
1. tickers: list of stock ticker symbols mentioned or implied
2. intents: list from [outlook, comparison, catalyst, historical, recommendation, general]
3. timeframe: short-term, medium-term, or long-term

If no specific ticker is mentioned but a sector/theme is, suggest 2-3 relevant tickers.
Respond in JSON format only: {{"tickers": [...], "intents": [...], "timeframe": "..."}}{portfolio_context}"""

    # Use processed query if available (URLs resolved to tab names)
    query_for_planner = state.get("_processed_query", state["user_query"])
    
    # Add scout context so Planner knows what data was fetched
    scout_context = ""
    if state.get("_scout_tickers"):
        scout_context = f"\n\nThe Data Scout already identified these tickers from the platform's data: {', '.join(state['_scout_tickers'][:30])}. Use these tickers in your plan."

    result = _call_claude(client, system + scout_context, query_for_planner, max_tokens=1024, model=MODEL_FAST)

    try:
        # Extract JSON from response
        start = result.find("{")
        end = result.rfind("}") + 1
        plan = json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        plan = {"tickers": [], "intents": ["general"], "timeframe": "medium-term"}

    # If Data Scout fetched from a data source (hunter, portfolio, etc.), use those tickers
    # But NOT if scout only found explicit_tickers (user mentioned specific tickers)
    if state.get("_scout_data") and state.get("_scout_tickers"):
        plan["tickers"] = state["_scout_tickers"]
    # For portfolio queries, ensure all tickers are included
    elif state.get("_portfolio_tickers") and len(plan.get("tickers", [])) < len(state["_portfolio_tickers"]):
        plan["tickers"] = state["_portfolio_tickers"]

    if not plan.get("tickers"):
        plan["tickers"] = ["SPY"]
    if not plan.get("intents"):
        plan["intents"] = ["general"]

    state["plan"] = plan
    _emit(state, "agent_done", {"agent": "Planner", "result": plan})
    return state


def run_researcher(client, state):
    """Gather data from yfinance and InvestIQ local data."""
    _emit(state, "agent_start", {"agent": "Researcher", "description": "Gathering financial data..."})

    plan = state["plan"]
    tickers = plan["tickers"]
    intents = plan["intents"]

    # Determine which data types to fetch
    data_types = set()
    for intent in intents:
        data_types.update(INTENT_DATA_MAP.get(intent, INTENT_DATA_MAP["general"]))

    # If moderator requested specific data, focus on that
    if state.get("moderator_request"):
        _emit(state, "researcher_step", {"step": f"Moderator requested: {state['moderator_request']}"})

    research_data = state.get("research_data", {})

    # Inject Data Scout's pre-fetched data (already filtered and compact)
    if state.get("_scout_data"):
        for src_name, src_data in state["_scout_data"].items():
            research_data[f"__scout_{src_name}"] = json.dumps(src_data, default=str)

    # Fetch yfinance data for each ticker (but limit to avoid token bloat)
    if len(tickers) > 15:
        _emit(state, "researcher_step", {"step": f"Limiting yfinance deep fetch to top 15 of {len(tickers)} tickers..."})
        tickers = tickers[:15]

    for ticker in tickers:
        _emit(state, "researcher_step", {"step": f"Fetching market data for {ticker}..."})
        yf_data = _fetch_yfinance_data(ticker, data_types)
        research_data.update(yf_data)

    # Load InvestIQ proprietary data
    _emit(state, "researcher_step", {"step": "Loading InvestIQ scores & fundamentals..."})
    iq_data = _load_investiq_data(tickers)
    for ticker, data in iq_data.items():
        if data:
            research_data[f"{ticker}__investiq"] = json.dumps(data, default=str)

    state["research_data"] = research_data
    state["research_pass_count"] = state.get("research_pass_count", 0) + 1

    sources = state.get("sources", [])
    for ticker in tickers:
        sources.append({"title": f"Yahoo Finance: {ticker}", "ticker": ticker, "url": f"https://finance.yahoo.com/quote/{ticker}"})
    sources.append({"title": "InvestIQ Proprietary Scores", "ticker": ",".join(tickers), "url": ""})
    state["sources"] = sources

    _emit(state, "agent_done", {"agent": "Researcher", "result": {"tickers": tickers, "data_points": len(research_data)}})
    return state


def run_quant_analyst(client, state):
    """Analyze quantitative data."""
    _emit(state, "agent_start", {"agent": "Quant Analyst", "description": "Analyzing numbers & ratios..."})

    plan = state["plan"]
    research_data = state.get("research_data", {})

    # Build context from research data
    data_summary = []
    for key, value in research_data.items():
        data_summary.append(f"=== {key} ===\n{value}\n")
    data_text = "\n".join(data_summary)

    focus = ""
    if state.get("moderator_request"):
        focus = f"\n\nIMPORTANT — The moderator specifically wants you to focus on: {state['moderator_request']}"

    system = """You are a quantitative financial analyst. Analyze ONLY the data provided below — never infer, guess, or use general knowledge for specific numbers.

Rules:
- ONLY cite numbers that appear in the provided data. If a metric isn't in the data, say "Not available in data."
- Every claim must reference the source: e.g. "(per yfinance: trailingPE=25.3)" or "(IQ score: 85/100)"
- Do NOT make up price targets, analyst ratings, or growth numbers
- If data is missing or limited, say so explicitly

Analyze for:
- Valuation metrics (P/E, P/B, EV/EBITDA) — only if present in data
- Revenue and earnings growth trends — only from SEC/yfinance data provided
- InvestIQ scores interpretation (score 0-100, grade A-F, EWROS rotation)
- Price performance from provided history
- Insider signals — only if insider data is provided

Be precise. No filler. If you don't have the data, skip that section."""

    user_prompt = f"""Query: {state['user_query']}
Plan: {json.dumps(plan)}
{focus}

Available Data:
{data_text[:30000]}"""

    raw_analysis = _call_claude(client, system, user_prompt, max_tokens=16000)
    
    # VERIFY: Check analysis against actual data
    _emit(state, "researcher_step", {"step": "Verifying quant claims against source data..."})
    state["quant_analysis"] = _verify_analysis(client, raw_analysis, data_text[:15000], "quantitative")
    
    _emit(state, "agent_done", {"agent": "Quant Analyst", "result": "Analysis verified"})
    return state


def run_qual_analyst(client, state):
    """Analyze qualitative factors."""
    _emit(state, "agent_start", {"agent": "Qual Analyst", "description": "Evaluating qualitative factors..."})

    plan = state["plan"]
    research_data = state.get("research_data", {})

    data_summary = []
    for key, value in research_data.items():
        data_summary.append(f"=== {key} ===\n{value}\n")
    data_text = "\n".join(data_summary)

    focus = ""
    if state.get("moderator_request"):
        focus = f"\n\nIMPORTANT — The moderator specifically wants you to focus on: {state['moderator_request']}"

    system = """You are a qualitative financial analyst. Analyze ONLY what can be inferred from the provided data.

Rules:
- Base your analysis on the DATA PROVIDED — sector, industry, IQ criteria, insider signals, analyst recs
- Do NOT fabricate specific catalysts, product launches, or news events unless they appear in the data
- For competitive positioning: use the sector/industry and IQ scores to infer, but flag it as inference
- For insider signals: only discuss if insider data is present
- If analyst recommendations are provided, cite them. If not, don't make them up
- Clearly separate FACTS (from data) from INFERENCES (your analysis of the data)

Analyze for:
- Competitive positioning (based on sector, scores, and available metrics)
- Management signals (insider data if available)
- Sector context (what the sector/industry classification implies)
- Quality of growth (from revenue/earnings data if present)
- IQ criteria breakdown (what the scoring model rewards/penalizes)

Be honest about data gaps. Say "insufficient data" rather than guessing."""

    user_prompt = f"""Query: {state['user_query']}
Plan: {json.dumps(plan)}
{focus}

Available Data:
{data_text[:30000]}"""

    raw_analysis = _call_claude(client, system, user_prompt, max_tokens=16000)
    
    # VERIFY: Check analysis against actual data
    _emit(state, "researcher_step", {"step": "Verifying qualitative claims against source data..."})
    state["qual_analysis"] = _verify_analysis(client, raw_analysis, data_text[:15000], "qualitative")
    
    _emit(state, "agent_done", {"agent": "Qual Analyst", "result": "Analysis verified"})
    return state


def run_moderator(client, state):
    """Review analyses and decide next action."""
    _emit(state, "agent_start", {"agent": "Moderator", "description": "Reviewing analyses for completeness..."})

    cycle = state.get("cycle_count", 0) + 1
    state["cycle_count"] = cycle

    # Force verdict if at cycle limit
    if cycle >= MAX_CYCLES:
        state["moderator_decision"] = "VERDICT"
        state["moderator_verdict"] = "Forced verdict due to cycle limit."
        _emit(state, "agent_done", {"agent": "Moderator", "result": {"decision": "VERDICT", "reason": "cycle limit"}})
        return state

    system = """You are a research moderator. Review the quant and qual analyses and decide:

1. VERDICT — Both analyses are thorough and consistent enough to write a report. Provide a synthesized verdict.
2. NEED_DATA — Critical data is missing. Specify exactly what's needed.
3. NEED_ANALYSIS — Analyses have gaps or conflicts. Specify what to re-examine.

Respond in JSON: {"decision": "VERDICT|NEED_DATA|NEED_ANALYSIS", "reason": "...", "request": "...", "verdict": "..."}
The "verdict" field is only needed for VERDICT decisions — synthesize both analyses into a clear conclusion."""

    user_prompt = f"""User Query: {state['user_query']}
Plan: {json.dumps(state['plan'])}

Quant Analysis:
{state.get('quant_analysis', 'Not yet available')}

Qual Analysis:
{state.get('qual_analysis', 'Not yet available')}

Cycle: {cycle}/{MAX_CYCLES}"""

    result = _call_claude(client, system, user_prompt, max_tokens=2000, model=MODEL_FAST)

    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        decision = json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        decision = {"decision": "VERDICT", "reason": "Parse error, proceeding", "verdict": result}

    state["moderator_decision"] = decision.get("decision", "VERDICT")
    state["moderator_request"] = decision.get("request", "")
    if decision.get("verdict"):
        state["moderator_verdict"] = decision["verdict"]

    _emit(state, "agent_done", {"agent": "Moderator", "result": {"decision": state["moderator_decision"], "cycle": cycle}})
    return state


def run_writer(client, state):
    """Produce the final markdown research report."""
    _emit(state, "agent_start", {"agent": "Writer", "description": "Writing research report..."})

    system = """You are a financial research writer. Produce a well-structured markdown report based ONLY on the analyses provided.

CRITICAL RULES:
- Every number you cite must come from the Quant or Qual analysis. No inventing data.
- If a section has no supporting data, write "Insufficient data for this section" and move on. Do NOT fill it with general knowledge.
- Keep it concise — quality over length. Skip empty sections entirely.
- Use parenthetical citations: (IQ Score: 85), (P/E: 25.3 per yfinance), (EWROS: 72)

Structure (skip sections with no data):
# [Company/Topic] Research Report

## Executive Summary
Key finding in 2-3 sentences.

## Key Metrics
Table or bullet list of actual numbers from data.

## Analysis
Combined quant + qual insights. Only data-backed claims.

## Strengths & Weaknesses
What the data shows is strong vs concerning.

## Risks
Specific risks identified in the data.

## Verdict
Clear buy/hold/avoid with conviction level (High/Medium/Low) and the key reason.

IMPORTANT: You MUST cover ALL tickers in the plan. If there are 10 tickers, all 10 must appear in the report. Do not skip any.

At the end, self-evaluate: output exactly SELF_EVAL:COMPLETE or SELF_EVAL:WEAK"""

    portfolio_context = ""
    if state.get("_portfolio_baskets"):
        basket_summary = "\n".join([f"  {name}: {', '.join(tickers)}" for name, tickers in state["_portfolio_baskets"].items()])
        portfolio_context = f"""

Portfolio Baskets:
{basket_summary}
Structure the report by basket/theme when analyzing portfolio positions."""

    user_prompt = f"""Query: {state['user_query']}
Plan: {json.dumps(state['plan'])}
{portfolio_context}

Moderator Verdict:
{state.get('moderator_verdict', 'No verdict available')}

Quant Analysis:
{state.get('quant_analysis', '')}

Qual Analysis:
{state.get('qual_analysis', '')}

Sources: {json.dumps(state.get('sources', []))}"""

    report = _call_claude(client, system, user_prompt, max_tokens=16000)

    # Extract self-evaluation
    if "SELF_EVAL:WEAK" in report:
        state["writer_verdict"] = "WEAK"
        report = report.replace("SELF_EVAL:WEAK", "").strip()
    else:
        state["writer_verdict"] = "COMPLETE"
        report = report.replace("SELF_EVAL:COMPLETE", "").strip()

    state["final_report"] = report
    _emit(state, "agent_done", {"agent": "Writer", "result": {"verdict": state["writer_verdict"]}})
    return state


def run_risk_analyst(client, state):
    """Stress-test the investment thesis."""
    _emit(state, "agent_start", {"agent": "Risk Analyst", "description": "Stress-testing the thesis..."})

    system = """You are an adversarial risk analyst. Stress-test the investment thesis using ONLY the data and report provided.

Rules:
- Only flag risks that are evidenced by the data (e.g., high P/E, declining revenue, insider selling)
- Do NOT invent macro scenarios or hypothetical risks without data support
- If the data shows a clear weakness (failed IQ criteria, low sub-score), flag it specifically
- Keep it short and sharp — 3-6 risk flags max, not a wall of text

Format each as: **[HIGH/MEDIUM/LOW]** Risk description (cite the data point)

Be adversarial but data-grounded."""

    user_prompt = f"""Query: {state['user_query']}
Report:
{state.get('final_report', '')}

Raw Data Available:
{json.dumps({k: v[:500] if isinstance(v, str) else v for k, v in state.get('research_data', {}).items()}, default=str)[:10000]}"""

    state["risk_flags"] = _call_claude(client, system, user_prompt, max_tokens=16000)
    _emit(state, "agent_done", {"agent": "Risk Analyst", "result": "Risk assessment complete"})
    return state


# ── Pipeline Orchestrator ──

def research(query, emit=None):
    """
    Run the full 7-agent research pipeline.

    Args:
        query: User's research question
        emit: Optional callback(event_type, data) for SSE streaming

    Returns:
        dict with final_report, risk_flags, plan, sources, etc.
    """
    api_key = _load_api_key()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment or .env file")

    client = anthropic.Anthropic(api_key=api_key)

    state = {
        "user_query": query,
        "plan": {},
        "research_data": {},
        "research_pass_count": 0,
        "quant_analysis": "",
        "qual_analysis": "",
        "moderator_decision": "",
        "moderator_request": "",
        "moderator_verdict": "",
        "cycle_count": 0,
        "writer_verdict": "",
        "final_report": "",
        "risk_flags": "",
        "sources": [],
        "_emit": emit,
    }

    try:
        # 0. Data Scout — determines which sources to fetch
        state = run_data_scout(client, state)
        if state.get("error"):
            return state

        # 1. Planner
        state = run_planner(client, state)

        # 2. Researcher (with possible loops)
        state = run_researcher(client, state)

        # Main analysis loop with moderator
        while True:
            # 3+4. Quant + Qual in PARALLEL (they don't depend on each other)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                quant_future = executor.submit(run_quant_analyst, client, dict(state))
                qual_future = executor.submit(run_qual_analyst, client, dict(state))
                quant_state = quant_future.result()
                qual_state = qual_future.result()
            state["quant_analysis"] = quant_state["quant_analysis"]
            state["qual_analysis"] = qual_state["qual_analysis"]

            # 5. Moderator
            state = run_moderator(client, state)

            decision = state["moderator_decision"]

            if decision == "NEED_DATA":
                # Loop back to researcher
                if state["research_pass_count"] < MAX_RESEARCH_PASSES:
                    state = run_researcher(client, state)
                else:
                    # Can't fetch more data, force forward
                    state["moderator_decision"] = "VERDICT"
                    state["moderator_verdict"] = state.get("moderator_verdict", "Proceeding with available data.")
                    break
            elif decision == "NEED_ANALYSIS":
                # Loop back to quant/qual (continue the while loop)
                continue
            else:
                # VERDICT — proceed to writer
                break

        # 6. Writer (with possible loop back to moderator)
        state = run_writer(client, state)

        if state["writer_verdict"] == "WEAK" and state["cycle_count"] < MAX_CYCLES:
            # One more moderator pass
            state = run_moderator(client, state)
            state = run_writer(client, state)

        # 7. Risk Analyst
        state = run_risk_analyst(client, state)

        _emit(state, "complete", {
            "report": state["final_report"],
            "risk_flags": state["risk_flags"],
            "tickers": state["plan"].get("tickers", []),
            "intents": state["plan"].get("intents", []),
            "sources": state.get("sources", []),
        })

    except Exception as e:
        _emit(state, "error", {"message": str(e), "traceback": traceback.format_exc()})
        state["error"] = str(e)

    return state

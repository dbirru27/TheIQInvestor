"""
Deep Research — Multi-agent stock research pipeline using Anthropic Claude.

7-agent pipeline: Planner → Researcher → Quant → Qual → Moderator → Writer → Risk
Uses yfinance for live market data and InvestIQ local data files for proprietary scores.
"""

import json
import os
import time
import traceback
from datetime import datetime

import anthropic
import yfinance as yf

# ── Constants ──
MODEL = "claude-sonnet-4-20250514"
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


def _load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        key = line.strip().split("=", 1)[1]
        except FileNotFoundError:
            pass
    return key


def _load_investiq_data(tickers):
    """Load InvestIQ scores, SEC fundamentals, and insider signals for given tickers."""
    result = {}

    # all_stocks.json
    try:
        with open(os.path.join(os.path.dirname(__file__), "data/all_stocks.json")) as f:
            all_stocks = json.load(f).get("stocks", {})
    except Exception:
        all_stocks = {}

    # sec_fundamentals.json
    try:
        with open(os.path.join(os.path.dirname(__file__), "data/sec_fundamentals.json")) as f:
            sec_data = json.load(f)
    except Exception:
        sec_data = {}

    # insider_universe.json
    try:
        with open(os.path.join(os.path.dirname(__file__), "data/insider_universe.json")) as f:
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


def _call_claude(client, system_prompt, user_prompt, max_tokens=4096):
    """Make a single Claude API call."""
    resp = client.messages.create(
        model=MODEL,
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

    system = """You are a financial research planner. Given a user query about stocks, extract:
1. tickers: list of stock ticker symbols mentioned or implied
2. intents: list from [outlook, comparison, catalyst, historical, recommendation, general]
3. timeframe: short-term, medium-term, or long-term

If no specific ticker is mentioned but a sector/theme is, suggest 2-3 relevant tickers.
Respond in JSON format only: {"tickers": [...], "intents": [...], "timeframe": "..."}"""

    result = _call_claude(client, system, state["user_query"], max_tokens=512)

    try:
        # Extract JSON from response
        start = result.find("{")
        end = result.rfind("}") + 1
        plan = json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        plan = {"tickers": [], "intents": ["general"], "timeframe": "medium-term"}

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

    # Fetch yfinance data for each ticker
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

    system = """You are a quantitative financial analyst. Analyze the numerical data provided and produce insights on:
- Valuation metrics (P/E, P/B, EV/EBITDA) relative to sector
- Revenue and earnings growth trends (quarter-over-quarter, year-over-year)
- Price performance and technical positioning
- InvestIQ proprietary scores interpretation (score 0-100, grade A-F, EWROS rotation momentum)
- SEC fundamental trends (revenue, EPS, cash flow trajectories)
- Insider trading patterns and what they signal
- Key financial ratios and their implications

Be data-driven. Cite specific numbers. Identify trends and inflection points."""

    user_prompt = f"""Query: {state['user_query']}
Plan: {json.dumps(plan)}
{focus}

Available Data:
{data_text[:30000]}"""

    state["quant_analysis"] = _call_claude(client, system, user_prompt, max_tokens=3000)
    _emit(state, "agent_done", {"agent": "Quant Analyst", "result": "Analysis complete"})
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

    system = """You are a qualitative financial analyst. Analyze the data and provide insights on:
- Competitive positioning and moat assessment
- Management quality signals (insider buying/selling patterns, alignment)
- Sector/industry tailwinds or headwinds
- Catalyst assessment (upcoming earnings, product launches, regulatory changes)
- Market sentiment and analyst consensus interpretation
- Quality of growth (organic vs acquired, sustainable vs one-time)
- InvestIQ criteria breakdown interpretation (what the scoring model rewards/penalizes)

Focus on narrative and context. Connect the dots between data points."""

    user_prompt = f"""Query: {state['user_query']}
Plan: {json.dumps(plan)}
{focus}

Available Data:
{data_text[:30000]}"""

    state["qual_analysis"] = _call_claude(client, system, user_prompt, max_tokens=3000)
    _emit(state, "agent_done", {"agent": "Qual Analyst", "result": "Analysis complete"})
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

    result = _call_claude(client, system, user_prompt, max_tokens=2000)

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

    system = """You are a financial research writer. Produce a comprehensive, well-structured markdown research report.

Structure:
# [Company/Topic] Research Report

## Executive Summary
Brief overview and key conclusion.

## Investment Thesis
Bull case and bear case.

## Quantitative Analysis
Key metrics, valuation, growth trends, InvestIQ scores breakdown.

## Qualitative Assessment
Competitive positioning, management, catalysts.

## Technical & Momentum
Price action, EWROS rotation score, trend alignment.

## Insider Activity
What insiders are doing and what it signals.

## Risks & Considerations
Key risk factors.

## Conclusion & Rating
Final assessment with conviction level (High/Medium/Low).

Use specific numbers. Be balanced but provide a clear conclusion.
At the end, self-evaluate: output exactly SELF_EVAL:COMPLETE or SELF_EVAL:WEAK"""

    user_prompt = f"""Query: {state['user_query']}
Plan: {json.dumps(state['plan'])}

Moderator Verdict:
{state.get('moderator_verdict', 'No verdict available')}

Quant Analysis:
{state.get('quant_analysis', '')}

Qual Analysis:
{state.get('qual_analysis', '')}

Sources: {json.dumps(state.get('sources', []))}"""

    report = _call_claude(client, system, user_prompt, max_tokens=6000)

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

    system = """You are an adversarial risk analyst. Your job is to stress-test the investment thesis.

Identify:
1. What could go wrong that the report doesn't adequately address
2. Hidden risks in the data (declining margins, insider selling, valuation stretch)
3. Macro risks relevant to this stock/sector
4. Scenarios where the thesis breaks down
5. InvestIQ score weaknesses (low sub-scores, failed criteria)

Output a list of risk flags, each with severity (HIGH/MEDIUM/LOW) and a brief explanation.
Format each as: **[SEVERITY]** Risk description

Be genuinely adversarial — don't just rubber-stamp the thesis."""

    user_prompt = f"""Query: {state['user_query']}
Report:
{state.get('final_report', '')}

Raw Data Available:
{json.dumps({k: v[:500] if isinstance(v, str) else v for k, v in state.get('research_data', {}).items()}, default=str)[:10000]}"""

    state["risk_flags"] = _call_claude(client, system, user_prompt, max_tokens=2000)
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
        # 1. Planner
        state = run_planner(client, state)

        # 2. Researcher (with possible loops)
        state = run_researcher(client, state)

        # Main analysis loop with moderator
        while True:
            # 3. Quant Analyst
            state = run_quant_analyst(client, state)

            # 4. Qual Analyst
            state = run_qual_analyst(client, state)

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

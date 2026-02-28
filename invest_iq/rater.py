#!/usr/bin/env python3
# ============================================================================
# DEPRECATED: This is the old v3.0 StockRater. 
# Use /workspace/rater.py (BreakoutRater v4.4) instead.
# Kept for backward compatibility. Will be removed in future cleanup.
# ============================================================================

import yfinance as yf
import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

@dataclass
class CriterionResult:
    name: str
    category: str
    passed: bool
    value: str
    threshold: str

import sys
import os
# Add workspace root to path to find market_data
sys.path.append(os.getcwd())
try:
    from market_data import MarketDB
except ImportError:
    MarketDB = None

@dataclass
class CriterionResult:
    name: str
    category: str
    passed: bool
    value: str
    threshold: str

class StockRater:
    def __init__(self, ticker: str, benchmark: str = "SPY"):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        self.spy = yf.Ticker(benchmark)
        self.results = []
        self.is_valid = True
        
        # Initialize DB Connection
        self.db = MarketDB() if MarketDB else None
        
        self._load_data()
    
    def _load_data(self):
        try:
            # 1. LOAD PRICE HISTORY (From DB if available, else download)
            if self.db:
                # Try fetching from DB
                self.hist = self.db.get_history(self.ticker)
                
                # If missing or stale (check last date), could trigger update here
                # For now, if DB has data, use it. If not, fallback to YF.
                if self.hist is None or self.hist.empty:
                    self.hist = self.stock.history(period="1y")
            else:
                self.hist = self.stock.history(period="1y")

            if self.hist.empty or len(self.hist) < 20:
                self.is_valid = False
                return

            # Load Benchmark (SPY) - optimize this later to be single-load
            self.spy_hist = self.spy.history(period="1y")
            
            # 2. LOAD FUNDAMENTALS (Check Cache)
            cached_fund = self.db.get_fundamentals(self.ticker) if self.db else None
            
            if cached_fund:
                self.info = cached_fund
                # Reconstruct estimate objects from cache if possible, or just skip for now
                # For simplicity, we just cache the 'info' dict. Estimates are complex.
                # If we need estimates, we might still need to hit YF or cache them separately.
                # Let's hit YF for estimates but use cached Info.
            else:
                self.info = self.stock.info
                if self.db and self.info:
                    self.db.save_fundamentals(self.ticker, self.info)

            self.calendar = self.stock.calendar
            # Load estimates for forecast
            try:
                self.earnings_est = self.stock.earnings_estimate
                self.revenue_est = self.stock.revenue_estimate
            except:
                self.earnings_est = pd.DataFrame()
                self.revenue_est = pd.DataFrame()
        except:
            self.is_valid = False

    # --- PILLAR 6: BREAKOUT SETUP (NEW v3.5) ---
    def c18_near_high(self):
        # LOGIC: 6-MONTH CONSOLIDATION BREAKOUT
        # User: "Must be a consolidation of at least 6 months."
        # We need to ensure the "Ceiling" (Resistance) has existed for ~6 months.
        # It shouldn't be a stair-step uptrend where the ceiling moves up every month.
        
        # 1. Get 6-Month Window (approx 130 trading days), excluding last week
        # Split into two halves to check for "Flat Top" vs "Rising Trend".
        window = self.hist.iloc[-130:-5]
        if len(window) < 100:
             return CriterionResult("Breakout Pattern", "Breakout", False, "Insufficient Data", "6mo History")
        
        midpoint = len(window) // 2
        first_half = window.iloc[:midpoint]  # Months 1-3
        second_half = window.iloc[midpoint:] # Months 4-6
        
        # 2. Identify the Ceiling in both halves
        high_1 = first_half['High'].max()
        high_2 = second_half['High'].max()
        
        # 3. Trend Check: Did the ceiling rise significantly?
        # If High_2 is > 10% above High_1, it's an uptrend, not a flat consolidation.
        # A valid base has a relatively flat resistance area (e.g. Cup and Handle rims).
        ceiling_drift = (high_2 - high_1) / high_1
        
        if ceiling_drift > 0.10:
             return CriterionResult("Breakout Pattern", "Breakout", False, f"Trend (+{ceiling_drift*100:.0f}%)", "Flat Resistance (<10% Rise)")

        # 4. Breakout Check: Are we at that ceiling NOW?
        # The consolidation ceiling is roughly max(high_1, high_2)
        base_ceiling = max(high_1, high_2)
        current = self.hist['Close'].iloc[-1]
        
        # We want to be breaking it or right under it (within 3%)
        dist = (base_ceiling - current) / base_ceiling
        
        # Negative dist means we are ABOVE the ceiling (True Breakout)
        # Positive dist < 0.03 means we are right below it.
        at_breakout_point = dist < 0.03
        
        if not at_breakout_point:
             return CriterionResult("Breakout Pattern", "Breakout", False, f"{dist*100:.1f}% below Base", "Near Base Resistance")
             
        return CriterionResult("Breakout Pattern", "Breakout", True, "Base Breakout!", "New High from Flat Base")

    def c19_tight_base(self):
        # LOGIC: 6-Month Base Structure
        # Ensure the price actually spent time consolidating, not just V-shaping.
        
        window = self.hist.iloc[-130:-5]
        
        # 1. Base Depth: (High - Low) / High
        # User implies we don't want massive volatility. 
        # But a "Consolidation" can be deep (30%). It just can't be a downtrend crash.
        period_high = window['High'].max()
        period_low = window['Low'].min()
        depth = (period_high - period_low) / period_high
        
        if depth > 0.40:
             return CriterionResult("Consolidation", "Breakout", False, f"Too Loose ({depth*100:.0f}%)", "Depth < 40%")
             
        # 2. Time in Base (Density)
        # Did we spend time in the bottom half? Or was it all near the top?
        # A true base repairs the stock. Price should have visited the lower range.
        # Check if Median price is somewhat centered, not hugging the high.
        median_price = window['Close'].median()
        rel_position = (median_price - period_low) / (period_high - period_low)
        
        # If median is > 0.85, we barely dipped. That's a "High Tight Flag" (rare) or a Trend.
        # We want a proper base (Saucer/Cup).
        
        is_proper_base = rel_position < 0.85
        
        return CriterionResult("Consolidation", "Breakout", is_proper_base, f"Depth {depth*100:.0f}%", "Valid 6mo Structure")

    def c19_tight_base(self):
        # LOGIC UPDATE: Base Depth & "Coiled Spring"
        # We need a period of consolidation (sideways action).
        
        # 1. Look at last 3 months (approx 63 days), excluding last 5 days (breakout week)
        base_period = self.hist['Close'].iloc[-68:-5] 
        
        if len(base_period) < 20:
             return CriterionResult("Base Structure", "Breakout", False, "No Data", "Consolidation")

        # 2. Calculate Depth (How deep did the correction go?)
        # A deep cup is okay (30%), a crash (50%) is not.
        base_high = base_period.max()
        base_low = base_period.min()
        depth = (base_high - base_low) / base_high
        
        # 3. The "Coil" Check (Volatility Contraction)
        # In the right side of the base (last 20 days of the base period), volatility should dry up.
        right_side = base_period.tail(20)
        volatility = right_side.std() / right_side.mean()
        
        # Criteria:
        # A) Depth must be reasonable (< 35%)
        # B) Right side must be tight (< 2% volatility) OR it's a very flat base (Depth < 15%)
        
        is_flat = depth < 0.15
        is_tight_right = volatility < 0.02
        
        passed = (depth < 0.35) and (is_flat or is_tight_right)
        
        val_str = f"Depth {depth*100:.0f}%, Vol {volatility*100:.1f}%"
        return CriterionResult("Base Structure", "Breakout", passed, val_str, "Depth<35% & Tight")


    def c20_vol_dryup(self):
        # Look for volume to be lower than the 50d average during the base
        last_5_vol = self.hist['Volume'].tail(5).mean()
        avg_50_vol = self.hist['Volume'].tail(50).mean()
        passed = last_5_vol < avg_50_vol
        return CriterionResult("Volume Dry-up", "Breakout", passed, f"Vol: {last_5_vol/avg_50_vol:.1f}x avg", "Vol < 1.0x Avg")

    def _calc_sma(self, prices, window):
        return float(prices.rolling(window=window).mean().iloc[-1])

    # --- PILLAR 1: MOMENTUM (25) ---
    def c1_trend(self):
        close = self.hist['Close']
        sma50, sma200 = self._calc_sma(close, 50), self._calc_sma(close, 200)
        passed = (close.iloc[-1] > sma50) and (sma50 > sma200)
        return CriterionResult("Trend Alignment", "Momentum", passed, f"${close.iloc[-1]:.2f}", "Price > SMA50 > SMA200")

    def c2_rs(self):
        # Use exact date offset (3 months ago) instead of fixed rows
        target_date = self.hist.index[-1] - timedelta(days=91)
        try:
            # Get data starting from 3 months ago
            subset = self.hist[self.hist.index >= target_date]
            spy_subset = self.spy_hist[self.spy_hist.index >= target_date]
            
            stock_start = subset['Close'].iloc[0]
            spy_start = spy_subset['Close'].iloc[0]
            
            s_ret = (self.hist['Close'].iloc[-1] / stock_start - 1) * 100
            spy_ret = (self.spy_hist['Close'].iloc[-1] / spy_start - 1) * 100
            
            passed = s_ret > spy_ret
            val_str = f"{s_ret:.1f}% vs SPY {spy_ret:.1f}%"
        except Exception as e:
            passed, val_str = False, f"Error"
            
        return CriterionResult("Relative Strength", "Momentum", passed, val_str, "Outperform SPY (3M)")

    def c3_vol(self):
        v20, v50 = self.hist['Volume'].tail(20).mean(), self.hist['Volume'].tail(50).mean()
        passed = v20 > v50
        return CriterionResult("Volume Footprint", "Momentum", passed, f"RVOL {v20/v50:.2f}x", "20d Vol > 50d Vol")

    # --- PILLAR 2: GROWTH & QUALITY (35) ---
    def c4_sales(self):
        val = self.info.get('revenueGrowth')
        passed = val is not None and val > 0.1
        return CriterionResult("Sales Growth", "Growth", passed, f"{val*100:.1f}%" if val else "N/A", "> 10% TTM")

    def c5_eps(self):
        val = self.info.get('earningsGrowth')
        passed = val is not None and val > 0.15
        return CriterionResult("Earnings Growth", "Growth", passed, f"{val*100:.1f}%" if val else "N/A", "> 15% Est")

    def c6_margin(self):
        val = self.info.get('operatingMargins')
        passed = val is not None and val > 0.1
        return CriterionResult("Operating Margin", "Quality", passed, f"{val*100:.1f}%" if val else "N/A", "> 10%")

    def c7_fcf(self):
        val = self.info.get('freeCashflow', 0) or 0
        return CriterionResult("FCF Quality", "Quality", val > 0, f"${val/1e9:.1f}B", "> $0")

    def c8_debt(self):
        val = self.info.get('debtToEquity')
        passed = val is not None and (val / 100) < 1.0
        return CriterionResult("Debt Safety", "Quality", passed, f"D/E {val/100:.2f}" if val else "N/A", "< 1.0")

    # --- PILLAR 3: CATALYST & INDUSTRY (25) ---
    def c9_industry(self):
        sector = self.info.get('sector')
        sector_etfs = {
            'Technology': 'XLK', 'Consumer Cyclical': 'XLY', 'Energy': 'XLE',
            'Basic Materials': 'XLB', 'Industrials': 'XLI', 'Healthcare': 'XLV',
            'Financial Services': 'XLF', 'Consumer Defensive': 'XLP',
            'Utilities': 'XLU', 'Real Estate': 'XLRE', 'Communication Services': 'XLC'
        }
        etf_ticker = sector_etfs.get(sector)
        if not etf_ticker:
            return CriterionResult("Industry Strength", "Context", False, str(sector), "Sector Alpha Required")
        
        try:
            etf = yf.Ticker(etf_ticker)
            etf_hist = etf.history(period="1y")
            # Check ETF 3-month performance vs SPY
            target_date = etf_hist.index[-1] - timedelta(days=91)
            etf_subset = etf_hist[etf_hist.index >= target_date]
            spy_subset = self.spy_hist[self.spy_hist.index >= target_date]
            
            etf_ret = (etf_hist['Close'].iloc[-1] / etf_subset['Close'].iloc[0] - 1) * 100
            spy_ret = (self.spy_hist['Close'].iloc[-1] / spy_subset['Close'].iloc[0] - 1) * 100
            
            passed = etf_ret > spy_ret
            val_str = f"{etf_ticker}: {etf_ret:.1f}% vs SPY {spy_ret:.1f}%"
        except:
            passed, val_str = False, f"{sector} (Data Error)"
            
        return CriterionResult("Industry Strength", "Context", passed, val_str, "Sector must outperform SPY")

    def c10_inst(self):
        val = self.info.get('heldPercentInstitutions')
        passed = val is not None and val > 0.5
        return CriterionResult("Institutional Stack", "Inst", passed, f"{val*100:.1f}%" if val else "N/A", "> 50%")

    def c11_acc(self):
        val = self.info.get('heldPercentInstitutions')
        passed = val is not None and val > 0.6
        return CriterionResult("Accumulation Signal", "Inst", passed, f"{val*100:.1f}%" if val else "N/A", "> 60%")

    def c12_short(self):
        val = self.info.get('shortPercentOfFloat')
        passed = val is not None and val < 0.05
        return CriterionResult("Short Interest", "Inst", passed, f"{val*100:.1f}%" if val else "N/A", "< 5% Float")

    def c13_catalyst(self):
        try:
            next_earn = self.calendar.get('Earnings Date', [None])[0]
            days = (next_earn - datetime.now().date()).days if next_earn else 99
            passed = 0 < days <= 30
            val = f"{days} days" if next_earn else "Unknown"
        except:
            passed, val = False, "Unknown"
        return CriterionResult("Upcoming Catalyst", "Context", passed, val, "Event < 30 days")

    # --- PILLAR 4: VALUE & RESILIENCE (15) ---
    def c14_val(self):
        val = self.info.get('priceToSalesTrailing12Months')
        passed = val is not None and val < 10
        return CriterionResult("Relative Value", "Value", passed, f"P/S {val:.2f}" if val else "N/A", "Sane Valuation")

    def c15_dd(self):
        c3m = self.hist['Close'].tail(63)
        dd = ((c3m - c3m.cummax()) / c3m.cummax() * 100).min()
        return CriterionResult("Drawdown Safety", "Value", dd > -20, f"{dd:.1f}%", "Max DD > -20%")

    # --- PILLAR 5: FORECASTS ---
    def c16_fwd_rev(self):
        try:
            val = self.revenue_est.loc['+1y', 'growth']
            passed = val is not None and val > 0.08 # 8% growth target
            return CriterionResult("Fwd Rev Growth", "Growth", passed, f"{val*100:.1f}%", "> 8% Next Yr")
        except:
            return CriterionResult("Fwd Rev Growth", "Growth", False, "N/A", "> 8% Next Yr")

    def c17_fwd_eps(self):
        try:
            val = self.earnings_est.loc['+1y', 'growth']
            passed = val is not None and val > 0.12 # 12% growth target
            return CriterionResult("Fwd EPS Growth", "Growth", passed, f"{val*100:.1f}%", "> 12% Next Yr")
        except:
            return CriterionResult("Fwd EPS Growth", "Growth", False, "N/A", "> 12% Next Yr")

    def run(self):
        # v3.0 Breakout Hunter Weights
        # Momentum & Setup (50 pts)
        m_weights = {
            "Trend Alignment": 5, 
            "Breakout Pattern": 20, # Renamed from "Near 52w High"
            "Consolidation": 10,    # Renamed from "Tight Base"
            "Volume Dry-up": 5,
            "Industry Strength": 10
        }
        # Quality & Growth (50 pts)
        q_weights = {
            "Sales Growth": 5, "Earnings Growth": 5, 
            "Fwd Rev Growth": 10, "Fwd EPS Growth": 10,
            "Operating Margin": 10, "FCF Quality": 5, 
            "Debt Safety": 5
        }
        
        all_weights = {**m_weights, **q_weights}

        if not self.is_valid:
            print(f"Error: Invalid ticker {self.ticker}")
            return
            
        self.results = [
            # Momentum
            self.c1_trend(), self.c18_near_high(), self.c19_tight_base(), 
            self.c20_vol_dryup(), self.c9_industry(),
            # Quality
            self.c4_sales(), self.c5_eps(), self.c16_fwd_rev(), self.c17_fwd_eps(),
            self.c6_margin(), self.c7_fcf(), self.c8_debt()
        ]
        
        score = sum(all_weights.get(r.name, 0) for r in self.results if r.passed)
        
        # Calculate sub-scores for detailed output
        m_score = sum(m_weights.get(r.name, 0) for r in self.results if r.passed and r.name in m_weights)
        q_score = sum(q_weights.get(r.name, 0) for r in self.results if r.passed and r.name in q_weights)

        print(f"\n[ INVESTIQ v3.0: {self.ticker} ]")
        print(f"MOMENTUM: {m_score}/50  |  QUALITY: {q_score}/50")
        print(f"TOTAL: {score}/100    |  GRADE: {'A' if score>=85 else 'B' if score>=70 else 'C' if score>=55 else 'D' if score>=40 else 'F'}")
        
        print("\n--- BREAKDOWN ---")
        for r in self.results:
            mark = "✅" if r.passed else "❌"
            pts = all_weights.get(r.name, 0)
            print(f"{mark} {r.name:<18} ({pts}pts): {r.value} (Target: {r.threshold})")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "GE"
    StockRater(ticker).run()

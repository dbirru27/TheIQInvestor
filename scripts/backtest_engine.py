#!/usr/bin/env python3
"""
Event-Driven Walk-Forward Backtest — Proper entry/exit signals.

Signals tested (all price/volume based — no fundamentals):
  1. EWROS Top 20 with breakout entry + conditional exits
  2. EWROS + Trend Alignment (Price > 50d > 200d)
  3. Volume Breakout (1.5x+ volume surge above base ceiling)
  4. Combined: EWROS ≥ 80 + Breakout + Trend

Entry Rules:
  - Signal-specific (see each strategy)
  - Max 20 positions at any time
  - Equal weight per position

Exit Rules (whichever triggers first):
  - Stop loss: -8% from entry price
  - EWROS drops below 50 (for EWROS strategies)
  - Price closes below 50-day MA
  - Max hold: 126 trading days (~6 months)

Metrics: Win rate, avg win, avg loss, profit factor, max drawdown

Usage:
    python3 scripts/backtest_engine.py
"""
import json
import os
import sys
import warnings
import pickle
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata

warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
CHARTS_DIR = os.path.join(ROOT, 'reports', 'charts')
OHLCV_FILE = os.path.join(DATA_DIR, 'historical_ohlcv.parquet')
OUTPUT_FILE = os.path.join(DATA_DIR, 'backtest_results.json')

os.makedirs(CHARTS_DIR, exist_ok=True)

plt.rcParams.update({
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.edgecolor': '#cbd5e1', 'axes.labelcolor': '#1a1a1a',
    'text.color': '#1a1a1a', 'xtick.color': '#333333', 'ytick.color': '#333333',
    'grid.color': '#e2e8f0', 'grid.alpha': 0.7, 'font.family': 'sans-serif', 'font.size': 10,
})

# Parameters
EWROS_LOOKBACK = 63
EWROS_LAMBDA = 0.03
MAX_POSITIONS = 20
STOP_LOSS = -0.08         # -8%
EWROS_EXIT_THRESHOLD = 50  # Exit when EWROS drops below this
MAX_HOLD_DAYS = 126        # ~6 months
BREAKOUT_VOL_MULT = 1.5    # Volume must be 1.5x 50d avg
BASE_MIN_DAYS = 20
BASE_MAX_DRIFT = 0.10      # 10% max range for base detection


def load_data():
    print('📊 Loading 5-year OHLCV data...')
    ohlcv = pd.read_parquet(OHLCV_FILE)
    ohlcv['date'] = pd.to_datetime(ohlcv['date'])
    
    close = ohlcv.pivot_table(index='date', columns='ticker', values='close')
    volume = ohlcv.pivot_table(index='date', columns='ticker', values='volume')
    high = ohlcv.pivot_table(index='date', columns='ticker', values='high')
    low = ohlcv.pivot_table(index='date', columns='ticker', values='low')
    
    if 'SPY' not in close.columns:
        print('   Downloading SPY...')
        import yfinance as yf
        spy = yf.download('SPY', start=close.index[0], end=close.index[-1] + timedelta(days=1), progress=False)
        close['SPY'] = spy['Close']
        volume['SPY'] = spy['Volume']
    
    print(f'   {len(close.columns)} tickers, {len(close)} days ({close.index[0].date()} to {close.index[-1].date()})')
    return close, volume, high, low


def compute_ewros_all(close, idx, lookback=EWROS_LOOKBACK, lam=EWROS_LAMBDA):
    """Compute EWROS for all stocks at index position idx."""
    if idx < lookback:
        return {}
    
    window = close.iloc[idx - lookback + 1:idx + 1]
    if 'SPY' not in window.columns:
        return {}
    
    spy_ret = window['SPY'].pct_change().iloc[1:]
    stock_rets = window.pct_change().iloc[1:]
    
    days_ago = np.arange(len(spy_ret) - 1, -1, -1)
    weights = np.exp(-lam * days_ago)
    
    raw_scores = {}
    for ticker in stock_rets.columns:
        if ticker == 'SPY':
            continue
        sr = stock_rets[ticker].values
        spy_r = spy_ret.values
        mask = ~(np.isnan(sr) | np.isnan(spy_r))
        if mask.sum() < lookback * 0.5:
            continue
        alpha = (sr[mask] - spy_r[mask]) * weights[mask]
        raw_scores[ticker] = alpha.sum()
    
    if not raw_scores:
        return {}
    
    tickers = list(raw_scores.keys())
    raw = np.array([raw_scores[t] for t in tickers])
    pctiles = rankdata(raw, method='average') / len(raw) * 99
    return {t: round(p, 1) for t, p in zip(tickers, pctiles)}


def detect_base_ceiling(prices, idx, min_days=BASE_MIN_DAYS, max_drift=BASE_MAX_DRIFT):
    """Detect if stock has formed a flat base — return ceiling price or None."""
    if idx < min_days + 10:
        return None
    
    # Look at last 20-60 days for base
    for base_len in [60, 40, 30, 20]:
        if idx < base_len:
            continue
        base = prices[idx - base_len:idx]
        valid = base[~np.isnan(base)]
        if len(valid) < min_days:
            continue
        
        ceiling = np.max(valid)
        floor = np.min(valid)
        if ceiling <= 0:
            continue
        
        drift = (ceiling - floor) / ceiling
        if drift <= max_drift:
            return ceiling
    
    return None


def is_breakout(close_prices, volume_series, idx, ticker):
    """Check if today is a volume breakout above base ceiling."""
    if idx < 60:
        return False, 0
    
    prices = close_prices[ticker].values
    vols = volume_series[ticker].values
    
    current_price = prices[idx]
    current_vol = vols[idx]
    
    if np.isnan(current_price) or np.isnan(current_vol) or current_price <= 0:
        return False, 0
    
    # Check for base ceiling
    ceiling = detect_base_ceiling(prices, idx)
    if ceiling is None:
        return False, 0
    
    # Price must close above ceiling
    if current_price <= ceiling:
        return False, 0
    
    # Volume must be 1.5x+ the 50-day average
    vol_window = vols[max(0, idx-50):idx]
    valid_vols = vol_window[~np.isnan(vol_window)]
    if len(valid_vols) < 20:
        return False, 0
    avg_vol = np.mean(valid_vols)
    if avg_vol <= 0:
        return False, 0
    
    vol_ratio = current_vol / avg_vol
    if vol_ratio < BREAKOUT_VOL_MULT:
        return False, 0
    
    return True, vol_ratio


def is_trend_aligned(close_prices, ticker, idx):
    """Check Price > 50d MA > 200d MA."""
    prices = close_prices[ticker].values
    current = prices[idx]
    if np.isnan(current) or idx < 200:
        return False
    
    p50 = prices[max(0,idx-49):idx+1]
    p200 = prices[max(0,idx-199):idx+1]
    ma50 = np.nanmean(p50)
    ma200 = np.nanmean(p200)
    
    return current > ma50 > ma200


def get_ma50(close_prices, ticker, idx):
    """Get 50-day MA value."""
    if idx < 50:
        return None
    prices = close_prices[ticker].values[idx-49:idx+1]
    valid = prices[~np.isnan(prices)]
    return np.mean(valid) if len(valid) >= 30 else None


class Trade:
    def __init__(self, ticker, entry_date, entry_price, entry_idx, vol_ratio=0, ewros_at_entry=0):
        self.ticker = ticker
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.entry_idx = entry_idx
        self.vol_ratio = vol_ratio
        self.ewros_at_entry = ewros_at_entry
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl_pct = None
        self.hold_days = 0


def run_strategy(close, volume, high, low, name, entry_fn, use_ewros_exit=True):
    """
    Run event-driven backtest with given entry function.
    
    entry_fn(idx, ewros, close, volume) -> list of (ticker, vol_ratio, ewros_score)
    """
    print(f'\n🔬 Strategy: {name}')
    print(f'   Max positions: {MAX_POSITIONS}, Stop: {STOP_LOSS*100}%, Max hold: {MAX_HOLD_DAYS}d')
    
    open_trades = []
    closed_trades = []
    
    # Daily scan starting from day 200 (need enough history)
    start_idx = 200
    dates = close.index
    
    # Pre-compute EWROS weekly (every 5 days) to save time
    ewros_cache = {}
    print(f'   Pre-computing EWROS...', end=' ', flush=True)
    for idx in range(start_idx, len(dates), 5):
        ewros_cache[idx] = compute_ewros_all(close, idx)
    print(f'{len(ewros_cache)} snapshots')
    
    def get_ewros(idx):
        """Get nearest pre-computed EWROS."""
        nearest = max(k for k in ewros_cache if k <= idx)
        return ewros_cache.get(nearest, {})
    
    equity = [100.0]
    equity_dates = [dates[start_idx]]
    
    for idx in range(start_idx, len(dates)):
        current_date = dates[idx]
        
        # ---- CHECK EXITS ----
        still_open = []
        for trade in open_trades:
            current_price = close[trade.ticker].iloc[idx]
            days_held = idx - trade.entry_idx
            
            if np.isnan(current_price):
                still_open.append(trade)
                continue
            
            pnl = (current_price / trade.entry_price) - 1
            exit_reason = None
            
            # Stop loss
            if pnl <= STOP_LOSS:
                exit_reason = 'stop_loss'
            
            # Max hold
            elif days_held >= MAX_HOLD_DAYS:
                exit_reason = 'max_hold'
            
            # Price below 50d MA
            elif days_held >= 5:  # Give at least 5 days before MA exit
                ma50 = get_ma50(close, trade.ticker, idx)
                if ma50 is not None and current_price < ma50:
                    exit_reason = 'below_ma50'
            
            # EWROS exit
            if use_ewros_exit and exit_reason is None and days_held >= 10:
                ewros = get_ewros(idx)
                ticker_ewros = ewros.get(trade.ticker, 50)
                if ticker_ewros < EWROS_EXIT_THRESHOLD:
                    exit_reason = 'ewros_drop'
            
            if exit_reason:
                trade.exit_date = current_date
                trade.exit_price = current_price
                trade.exit_reason = exit_reason
                trade.pnl_pct = round(pnl * 100, 2)
                trade.hold_days = days_held
                closed_trades.append(trade)
            else:
                still_open.append(trade)
        
        open_trades = still_open
        
        # ---- CHECK ENTRIES (only check every trading day) ----
        if len(open_trades) < MAX_POSITIONS:
            ewros = get_ewros(idx)
            candidates = entry_fn(idx, ewros, close, volume)
            
            # Filter out already-held tickers
            held_tickers = {t.ticker for t in open_trades}
            candidates = [(t, vr, es) for t, vr, es in candidates if t not in held_tickers]
            
            # Take up to remaining capacity
            slots = MAX_POSITIONS - len(open_trades)
            for ticker, vol_ratio, ewros_score in candidates[:slots]:
                price = close[ticker].iloc[idx]
                if not np.isnan(price) and price > 0:
                    trade = Trade(ticker, current_date, price, idx, vol_ratio, ewros_score)
                    open_trades.append(trade)
        
        # Track equity (simplified: equal weight, mark to market)
        if closed_trades or open_trades:
            # Rough equity tracking
            total_pnl = 0
            n_trades = 0
            for t in open_trades:
                cp = close[t.ticker].iloc[idx]
                if not np.isnan(cp):
                    total_pnl += (cp / t.entry_price - 1)
                    n_trades += 1
            if n_trades > 0:
                avg_pnl = total_pnl / max(n_trades, 1)
                equity.append(equity[-1] * (1 + avg_pnl / MAX_POSITIONS))
            else:
                equity.append(equity[-1])
            equity_dates.append(current_date)
    
    # Close any remaining open trades at last price
    for trade in open_trades:
        last_price = close[trade.ticker].iloc[-1]
        if not np.isnan(last_price):
            trade.exit_date = dates[-1]
            trade.exit_price = last_price
            trade.exit_reason = 'end_of_data'
            trade.pnl_pct = round((last_price / trade.entry_price - 1) * 100, 2)
            trade.hold_days = len(dates) - 1 - trade.entry_idx
            closed_trades.append(trade)
    
    return closed_trades, equity, equity_dates


def analyze_trades(trades, name):
    """Compute trade statistics."""
    if not trades:
        return {'name': name, 'total_trades': 0}
    
    pnls = [t.pnl_pct for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    hold_days = [t.hold_days for t in trades]
    
    # Exit reason breakdown
    reasons = defaultdict(int)
    for t in trades:
        reasons[t.exit_reason] += 1
    
    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Win streaks
    streak = 0
    max_win_streak = 0
    max_lose_streak = 0
    lose_streak = 0
    for p in pnls:
        if p > 0:
            streak += 1
            lose_streak = 0
            max_win_streak = max(max_win_streak, streak)
        else:
            lose_streak += 1
            streak = 0
            max_lose_streak = max(max_lose_streak, lose_streak)
    
    # Expectancy
    win_rate = len(wins) / len(pnls) if pnls else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
    
    stats = {
        'name': name,
        'total_trades': len(trades),
        'winners': len(wins),
        'losers': len(losses),
        'win_rate': round(win_rate * 100, 1),
        'avg_gain': round(np.mean(pnls), 2),
        'median_gain': round(np.median(pnls), 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'best_trade': round(max(pnls), 2),
        'worst_trade': round(min(pnls), 2),
        'profit_factor': round(profit_factor, 2),
        'expectancy_per_trade': round(expectancy, 2),
        'total_return': round(sum(pnls), 1),
        'avg_hold_days': round(np.mean(hold_days), 1),
        'median_hold_days': round(np.median(hold_days), 1),
        'max_win_streak': max_win_streak,
        'max_lose_streak': max_lose_streak,
        'exit_reasons': dict(reasons),
    }
    
    return stats


def print_stats(stats):
    """Pretty-print strategy stats."""
    if stats['total_trades'] == 0:
        print('   No trades generated.')
        return
    
    print(f'   Trades: {stats["total_trades"]} ({stats["winners"]}W / {stats["losers"]}L)')
    print(f'   Win Rate: {stats["win_rate"]}%')
    print(f'   Avg Gain: {stats["avg_gain"]}% | Median: {stats["median_gain"]}%')
    print(f'   Avg Win: +{stats["avg_win"]}% | Avg Loss: {stats["avg_loss"]}%')
    print(f'   Best: +{stats["best_trade"]}% | Worst: {stats["worst_trade"]}%')
    print(f'   Profit Factor: {stats["profit_factor"]}')
    print(f'   Expectancy: {stats["expectancy_per_trade"]}% per trade')
    print(f'   Avg Hold: {stats["avg_hold_days"]}d | Median: {stats["median_hold_days"]}d')
    print(f'   Exit Reasons: {stats["exit_reasons"]}')


# ===== STRATEGY DEFINITIONS =====

def strategy_ewros_breakout(idx, ewros, close, volume):
    """EWROS ≥ 80 + volume breakout above base + trend aligned."""
    if not ewros:
        return []
    
    # Get top 20 EWROS stocks
    top = sorted(ewros.items(), key=lambda x: -x[1])[:40]  # Check top 40 for breakout
    candidates = []
    
    for ticker, score in top:
        if score < 80:
            continue
        if not is_trend_aligned(close, ticker, idx):
            continue
        
        broke_out, vol_ratio = is_breakout(close, volume, idx, ticker)
        if broke_out:
            candidates.append((ticker, vol_ratio, score))
    
    # Sort by EWROS score, take top 20
    candidates.sort(key=lambda x: -x[2])
    return candidates[:MAX_POSITIONS]


def strategy_ewros_trend(idx, ewros, close, volume):
    """EWROS ≥ 80 + trend aligned (no breakout required)."""
    if not ewros:
        return []
    
    top = sorted(ewros.items(), key=lambda x: -x[1])[:30]
    candidates = []
    
    for ticker, score in top:
        if score < 80:
            continue
        if not is_trend_aligned(close, ticker, idx):
            continue
        candidates.append((ticker, 0, score))
    
    candidates.sort(key=lambda x: -x[2])
    return candidates[:MAX_POSITIONS]


def strategy_volume_breakout(idx, ewros, close, volume):
    """Pure volume breakout: 1.5x+ volume above base ceiling, trend aligned."""
    candidates = []
    
    for ticker in close.columns:
        if ticker == 'SPY':
            continue
        if not is_trend_aligned(close, ticker, idx):
            continue
        broke_out, vol_ratio = is_breakout(close, volume, idx, ticker)
        if broke_out:
            candidates.append((ticker, vol_ratio, ewros.get(ticker, 50)))
    
    # Sort by volume ratio (strongest breakouts first)
    candidates.sort(key=lambda x: -x[1])
    return candidates[:MAX_POSITIONS]


def strategy_combined(idx, ewros, close, volume):
    """EWROS ≥ 80 + volume breakout + trend aligned (strictest filter)."""
    return strategy_ewros_breakout(idx, ewros, close, volume)  # Same logic


def strategy_ewros_top20(idx, ewros, close, volume):
    """Simple: buy top 20 EWROS stocks (with trend filter). No breakout required.
    Re-enter only when a slot opens (not monthly dump-and-rebuy)."""
    if not ewros:
        return []
    
    top = sorted(ewros.items(), key=lambda x: -x[1])[:20]
    candidates = []
    
    for ticker, score in top:
        if not is_trend_aligned(close, ticker, idx):
            continue
        candidates.append((ticker, 0, score))
    
    return candidates[:MAX_POSITIONS]


def plot_results(all_results, all_equity, all_equity_dates):
    """Generate charts."""
    
    # 1. Win rate + profit factor comparison
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    
    names = [r['name'] for r in all_results if r['total_trades'] > 0]
    win_rates = [r['win_rate'] for r in all_results if r['total_trades'] > 0]
    profit_factors = [r['profit_factor'] for r in all_results if r['total_trades'] > 0]
    expectancies = [r['expectancy_per_trade'] for r in all_results if r['total_trades'] > 0]
    total_trades = [r['total_trades'] for r in all_results if r['total_trades'] > 0]
    
    # Short names for display
    short_names = [n.replace('EWROS ', '').replace('Volume ', 'Vol ') for n in names]
    
    colors_list = ['#0ea5e9', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444']
    
    # Win rate
    x = np.arange(len(short_names))
    bars = axes[0].bar(x, win_rates, color=colors_list[:len(short_names)], alpha=0.85)
    axes[0].set_ylabel('Win Rate (%)')
    axes[0].set_title('Win Rate', fontweight='bold')
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(short_names, fontsize=7, rotation=15)
    axes[0].axhline(y=50, color='#94a3b8', linestyle='--', linewidth=0.8)
    for i, (bar, wr, nt) in enumerate(zip(bars, win_rates, total_trades)):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                     f'{wr}%\n({nt})', ha='center', fontsize=7)
    axes[0].grid(True, axis='y')
    
    # Profit factor
    bars = axes[1].bar(x, profit_factors, color=colors_list[:len(short_names)], alpha=0.85)
    axes[1].set_ylabel('Profit Factor')
    axes[1].set_title('Profit Factor (>1 = profitable)', fontweight='bold')
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(short_names, fontsize=7, rotation=15)
    axes[1].axhline(y=1.0, color='#ef4444', linestyle='--', linewidth=0.8)
    for bar, pf in zip(bars, profit_factors):
        axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                     f'{pf}', ha='center', fontsize=8, fontweight='bold')
    axes[1].grid(True, axis='y')
    
    # Expectancy
    bar_colors = ['#10b981' if e > 0 else '#ef4444' for e in expectancies]
    bars = axes[2].bar(x, expectancies, color=bar_colors, alpha=0.85)
    axes[2].set_ylabel('Expectancy (% per trade)')
    axes[2].set_title('Expectancy Per Trade', fontweight='bold')
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(short_names, fontsize=7, rotation=15)
    axes[2].axhline(y=0, color='#94a3b8', linestyle='--', linewidth=0.8)
    for bar, e in zip(bars, expectancies):
        axes[2].text(bar.get_x() + bar.get_width()/2, 
                     bar.get_height() + (0.1 if e >= 0 else -0.3),
                     f'{e}%', ha='center', fontsize=8, fontweight='bold')
    axes[2].grid(True, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'strategy_comparison.png'), dpi=150)
    plt.close()
    
    # 2. Equity curves
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (name, eq, eq_dates) in enumerate(zip(names, all_equity, all_equity_dates)):
        if eq and eq_dates:
            ax.plot(eq_dates, eq, label=name, color=colors_list[i % len(colors_list)], linewidth=1.5)
    
    # Add SPY
    # We'll compute SPY equity from the data
    ax.axhline(y=100, color='#94a3b8', linestyle='--', linewidth=0.5)
    ax.set_title('Equity Curves (Growth of $100)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Portfolio Value ($)')
    ax.legend(fontsize=8)
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'equity_curves.png'), dpi=150)
    plt.close()
    
    # 3. Exit reason breakdown
    fig, axes = plt.subplots(1, len(all_results), figsize=(3.5*len(all_results), 4))
    if len(all_results) == 1:
        axes = [axes]
    
    for ax, result in zip(axes, all_results):
        if result['total_trades'] == 0:
            continue
        reasons = result['exit_reasons']
        labels = list(reasons.keys())
        sizes = list(reasons.values())
        reason_colors = {
            'stop_loss': '#ef4444', 'below_ma50': '#f59e0b', 'ewros_drop': '#8b5cf6',
            'max_hold': '#0ea5e9', 'end_of_data': '#94a3b8'
        }
        colors_pie = [reason_colors.get(l, '#64748b') for l in labels]
        ax.pie(sizes, labels=[f'{l}\n({s})' for l, s in zip(labels, sizes)],
               colors=colors_pie, autopct='%1.0f%%', textprops={'fontsize': 7})
        ax.set_title(result['name'].replace('EWROS ', '').replace('Volume ', 'Vol '), fontsize=9, fontweight='bold')
    
    plt.suptitle('Exit Reason Breakdown', fontweight='bold', fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'exit_reasons.png'), dpi=150)
    plt.close()
    
    # 4. Trade P&L distribution
    fig, axes = plt.subplots(1, len(all_results), figsize=(3.5*len(all_results), 4))
    if len(all_results) == 1:
        axes = [axes]
    
    for ax, (result, trades) in zip(axes, [(r, t) for r, t in zip(all_results, all_trades_list)]):
        if not trades:
            continue
        pnls = [t.pnl_pct for t in trades]
        colors_hist = ['#10b981' if p > 0 else '#ef4444' for p in pnls]
        ax.hist(pnls, bins=30, color='#0ea5e9', alpha=0.7, edgecolor='#1e3a5f')
        ax.axvline(x=0, color='#ef4444', linestyle='--', linewidth=1)
        ax.axvline(x=np.mean(pnls), color='#10b981', linestyle='-', linewidth=1.5, label=f'Avg: {np.mean(pnls):.1f}%')
        ax.set_title(result['name'].replace('EWROS ', '').replace('Volume ', 'Vol '), fontsize=9, fontweight='bold')
        ax.set_xlabel('P&L (%)')
        ax.legend(fontsize=7)
    
    plt.suptitle('Trade P&L Distribution', fontweight='bold', fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'pnl_distribution.png'), dpi=150)
    plt.close()
    
    # 5. Summary bar chart
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(names))
    width = 0.25
    
    avg_wins = [r['avg_win'] for r in all_results if r['total_trades'] > 0]
    avg_losses = [abs(r['avg_loss']) for r in all_results if r['total_trades'] > 0]
    
    ax.bar(x - width/2, avg_wins, width, label='Avg Win (%)', color='#10b981', alpha=0.85)
    ax.bar(x + width/2, avg_losses, width, label='Avg Loss (%)', color='#ef4444', alpha=0.85)
    
    for i, (w, l) in enumerate(zip(avg_wins, avg_losses)):
        ax.text(i - width/2, w + 0.2, f'+{w}%', ha='center', fontsize=8)
        ax.text(i + width/2, l + 0.2, f'-{l}%', ha='center', fontsize=8)
    
    ax.set_title('Average Win vs Average Loss by Strategy', fontweight='bold', fontsize=12)
    ax.set_ylabel('Percentage')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=8)
    ax.legend()
    ax.grid(True, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'win_vs_loss.png'), dpi=150)
    plt.close()


def main():
    print('🚀 IQ Investor Event-Driven Backtest')
    print(f'   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'   Entry/exit signals, max {MAX_POSITIONS} positions, -8% stop, 50d MA exit, 6mo max hold\n')
    
    close, volume, high, low = load_data()
    
    strategies = [
        ('EWROS Top 20 + Trend', strategy_ewros_top20, True),
        ('EWROS ≥80 + Trend', strategy_ewros_trend, True),
        ('EWROS + Breakout', strategy_ewros_breakout, True),
        ('Volume Breakout', strategy_volume_breakout, False),
    ]
    
    global all_trades_list
    all_results = []
    all_equity = []
    all_equity_dates = []
    all_trades_list = []
    
    for name, entry_fn, use_ewros_exit in strategies:
        trades, equity, eq_dates = run_strategy(close, volume, high, low, name, entry_fn, use_ewros_exit)
        stats = analyze_trades(trades, name)
        print_stats(stats)
        all_results.append(stats)
        all_equity.append(equity)
        all_equity_dates.append(eq_dates)
        all_trades_list.append(trades)
        
        # Print some sample trades
        if trades:
            winners = sorted([t for t in trades if t.pnl_pct > 0], key=lambda x: -x.pnl_pct)
            losers = sorted([t for t in trades if t.pnl_pct <= 0], key=lambda x: x.pnl_pct)
            print(f'   Top 5 winners:')
            for t in winners[:5]:
                print(f'      {t.ticker}: +{t.pnl_pct}% ({t.entry_date.strftime("%Y-%m-%d")} → {t.exit_date.strftime("%Y-%m-%d")}, {t.hold_days}d, exit: {t.exit_reason})')
            print(f'   Top 5 losers:')
            for t in losers[:5]:
                print(f'      {t.ticker}: {t.pnl_pct}% ({t.entry_date.strftime("%Y-%m-%d")} → {t.exit_date.strftime("%Y-%m-%d")}, {t.hold_days}d, exit: {t.exit_reason})')
    
    # Generate charts
    print('\n📊 Generating charts...')
    plot_results(all_results, all_equity, all_equity_dates)
    
    # Save results
    output = {
        'generated_at': datetime.now().isoformat(),
        'method': 'Event-driven: daily scan for entry signals, conditional exits (stop loss, MA50, EWROS drop, max hold)',
        'data_range': f'{close.index[0].date()} to {close.index[-1].date()}',
        'parameters': {
            'max_positions': MAX_POSITIONS,
            'stop_loss': f'{STOP_LOSS*100}%',
            'ewros_exit_threshold': EWROS_EXIT_THRESHOLD,
            'max_hold_days': MAX_HOLD_DAYS,
            'breakout_volume_multiplier': BREAKOUT_VOL_MULT,
            'base_max_drift': f'{BASE_MAX_DRIFT*100}%',
            'ewros_lookback': EWROS_LOOKBACK,
            'ewros_lambda': EWROS_LAMBDA,
        },
        'strategies': {r['name']: r for r in all_results},
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f'\n✅ Backtest complete!')
    print(f'   Results: {OUTPUT_FILE}')
    print(f'   Charts: {CHARTS_DIR}/')
    for f_name in sorted(os.listdir(CHARTS_DIR)):
        if f_name.endswith('.png'):
            print(f'      {f_name}')


if __name__ == '__main__':
    main()

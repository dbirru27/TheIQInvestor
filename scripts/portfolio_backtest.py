#!/usr/bin/env python3
"""
Portfolio Backtest — $10K starting capital with realistic position sizing.

Simulates actual trading:
  - Start with $10,000 cash
  - Equal-weight positions (capital / max_positions per trade)
  - Track cash + invested value daily
  - Compare vs SPY buy-and-hold
  - No margin, no leverage

Runs all strategies from the OOS backtest (Sep 2023 – Mar 2026)
and the full-period EWROS backtest.
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
MODEL_DIR = os.path.join(ROOT, 'models')
OHLCV_FILE = os.path.join(DATA_DIR, 'historical_ohlcv.parquet')
EVENTS_FILE = os.path.join(DATA_DIR, 'breakout_events.parquet')
OUTPUT_FILE = os.path.join(DATA_DIR, 'backtest_results.json')

os.makedirs(CHARTS_DIR, exist_ok=True)

plt.rcParams.update({
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.edgecolor': '#cbd5e1', 'axes.labelcolor': '#1a1a1a',
    'text.color': '#1a1a1a', 'xtick.color': '#333333', 'ytick.color': '#333333',
    'grid.color': '#e2e8f0', 'grid.alpha': 0.7, 'font.family': 'sans-serif', 'font.size': 10,
})

STARTING_CAPITAL = 10_000
MAX_POSITIONS = 20
POSITION_SIZE = STARTING_CAPITAL / MAX_POSITIONS  # $500 per slot
STOP_LOSS = -0.08
MAX_HOLD_DAYS = 126
EWROS_LOOKBACK = 63
EWROS_LAMBDA = 0.03
EWROS_EXIT = 50
BREAKOUT_VOL_MULT = 1.5
BASE_MAX_DRIFT = 0.10

FEATURE_COLS = [
    'close_to_ma20', 'close_to_ma50', 'close_to_ma200',
    'trend_aligned', 'atr_14', 'vol_dryup_ratio', 'vol_compression',
    'proximity_52w', 'return_3mo', 'up_days_pct', 'vol_trend_in_base',
    'base_length', 'base_range', 'breakout_vol_ratio'
]


def load_ohlcv():
    print('📊 Loading OHLCV data...')
    ohlcv = pd.read_parquet(OHLCV_FILE)
    ohlcv['date'] = pd.to_datetime(ohlcv['date'])
    close = ohlcv.pivot_table(index='date', columns='ticker', values='close')
    volume = ohlcv.pivot_table(index='date', columns='ticker', values='volume')
    high = ohlcv.pivot_table(index='date', columns='ticker', values='high')
    low = ohlcv.pivot_table(index='date', columns='ticker', values='low')
    
    if 'SPY' not in close.columns:
        import yfinance as yf
        spy = yf.download('SPY', start=close.index[0], end=close.index[-1] + timedelta(days=1), progress=False)
        close['SPY'] = spy['Close']
        volume['SPY'] = spy['Volume']
    
    print(f'   {len(close.columns)} tickers, {len(close)} days ({close.index[0].date()} to {close.index[-1].date()})')
    return close, volume, high, low


def compute_ewros_at_idx(close, idx):
    if idx < EWROS_LOOKBACK:
        return {}
    window = close.iloc[idx - EWROS_LOOKBACK + 1:idx + 1]
    if 'SPY' not in window.columns:
        return {}
    spy_ret = window['SPY'].pct_change().iloc[1:]
    stock_rets = window.pct_change().iloc[1:]
    days_ago = np.arange(len(spy_ret) - 1, -1, -1)
    weights = np.exp(-EWROS_LAMBDA * days_ago)
    raw = {}
    for t in stock_rets.columns:
        if t == 'SPY': continue
        sr = stock_rets[t].values
        sp = spy_ret.values
        m = ~(np.isnan(sr) | np.isnan(sp))
        if m.sum() < EWROS_LOOKBACK * 0.5: continue
        raw[t] = ((sr[m] - sp[m]) * weights[m]).sum()
    if not raw: return {}
    tickers = list(raw.keys())
    vals = np.array([raw[t] for t in tickers])
    pct = rankdata(vals, method='average') / len(vals) * 99
    return {t: round(p, 1) for t, p in zip(tickers, pct)}


def compute_iq_edge_at_idx(close, volume, high, low, idx, model):
    if model is None: return {}
    scores = {}
    for ticker in close.columns:
        if ticker == 'SPY': continue
        prices = close[ticker].iloc[max(0, idx-252):idx+1].dropna()
        vols = volume[ticker].iloc[max(0, idx-252):idx+1].dropna()
        highs = high[ticker].iloc[max(0, idx-252):idx+1].dropna()
        lows = low[ticker].iloc[max(0, idx-252):idx+1].dropna()
        if len(prices) < 60: continue
        try:
            c = prices.iloc[-1]
            ma20 = prices.iloc[-20:].mean() if len(prices) >= 20 else c
            ma50 = prices.iloc[-50:].mean() if len(prices) >= 50 else c
            ma200 = prices.iloc[-200:].mean() if len(prices) >= 200 else prices.mean()
            ta = 1.0 if (c > ma50 > ma200) else 0.0
            if len(highs) >= 15 and len(lows) >= 15 and len(prices) >= 15:
                tr = np.maximum(highs.iloc[-15:].values - lows.iloc[-15:].values,
                    np.maximum(abs(highs.iloc[-15:].values - prices.iloc[-16:-1].values),
                               abs(lows.iloc[-15:].values - prices.iloc[-16:-1].values)))
                atr = np.mean(tr[-14:]) / c if c > 0 else 0
            else: atr = 0.02
            if len(vols) >= 50:
                vd = vols.iloc[-10:].mean() / vols.iloc[-50:-10].mean()
                bv = vols.iloc[-1] / vols.iloc[-50:].mean()
                vd = vd if np.isfinite(vd) else 1
                bv = bv if np.isfinite(bv) else 1
            else: vd, bv = 1, 1
            if len(prices) >= 40:
                vc = prices.iloc[-10:].pct_change().std() / prices.iloc[-40:].pct_change().std()
                vc = vc if np.isfinite(vc) else 1
            else: vc = 1
            p52 = c / prices.max() if prices.max() > 0 else 0
            r3m = (c / prices.iloc[-63] - 1) if len(prices) >= 63 else 0
            ch = prices.pct_change().dropna()
            up = (ch > 0).mean() if len(ch) > 0 else 0.5
            bp = prices.iloc[-40:]
            bl = len(bp) / 120
            br = (bp.max() - bp.min()) / bp.mean() if bp.mean() > 0 else 0
            if len(vols) >= 40:
                vt = vols.iloc[-20:].mean() / vols.iloc[-40:-20].mean() - 1
                vt = vt if np.isfinite(vt) else 0
            else: vt = 0
            feats = np.nan_to_num(np.array([[c/ma20-1, c/ma50-1, c/ma200-1, ta, atr, vd, vc, p52, r3m, up, vt, bl, br, bv]]))
            scores[ticker] = model.predict_proba(feats)[0][1]
        except: continue
    if not scores: return {}
    tickers = list(scores.keys())
    vals = np.array([scores[t] for t in tickers])
    pct = rankdata(vals, method='average') / len(vals) * 99
    return {t: {'pctile': round(p, 1), 'prob': round(scores[t], 4)} for t, p in zip(tickers, pct)}


def is_trend_aligned(close, ticker, idx):
    p = close[ticker].values
    c = p[idx]
    if np.isnan(c) or idx < 200: return False
    return c > np.nanmean(p[max(0,idx-49):idx+1]) > np.nanmean(p[max(0,idx-199):idx+1])


def get_ma50(close, ticker, idx):
    if idx < 50: return None
    v = close[ticker].values[idx-49:idx+1]
    v = v[~np.isnan(v)]
    return np.mean(v) if len(v) >= 30 else None


class Position:
    def __init__(self, ticker, shares, entry_price, entry_idx, entry_date, cost_basis, iq_edge=0, ewros=0):
        self.ticker = ticker
        self.shares = shares
        self.entry_price = entry_price
        self.entry_idx = entry_idx
        self.entry_date = entry_date
        self.cost_basis = cost_basis
        self.iq_edge = iq_edge
        self.ewros = ewros


class ClosedTrade:
    def __init__(self, ticker, shares, entry_price, exit_price, entry_date, exit_date, 
                 hold_days, pnl_dollar, pnl_pct, exit_reason, iq_edge=0, ewros=0):
        self.ticker = ticker
        self.shares = shares
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.entry_date = entry_date
        self.exit_date = exit_date
        self.hold_days = hold_days
        self.pnl_dollar = pnl_dollar
        self.pnl_pct = pnl_pct
        self.exit_reason = exit_reason
        self.iq_edge = iq_edge
        self.ewros = ewros


def run_portfolio(close, volume, high, low, model, name, entry_fn, start_idx):
    """Simulate portfolio with real $ tracking."""
    print(f'\n💰 {name}')
    print(f'   Starting capital: ${STARTING_CAPITAL:,.0f}')
    
    cash = float(STARTING_CAPITAL)
    positions = []
    closed = []
    dates = close.index
    
    # Pre-compute signals weekly
    ewros_cache = {}
    iq_cache = {}
    print(f'   Pre-computing signals...', end=' ', flush=True)
    for idx in range(start_idx, len(dates), 5):
        ewros_cache[idx] = compute_ewros_at_idx(close, idx)
        if model:
            iq_cache[idx] = compute_iq_edge_at_idx(close, volume, high, low, idx, model)
    print(f'done')
    
    def get_nearest(cache, idx):
        keys = [k for k in cache if k <= idx]
        return cache[max(keys)] if keys else {}
    
    # Daily tracking
    daily_values = []
    daily_dates = []
    
    for idx in range(start_idx, len(dates)):
        date = dates[idx]
        
        # Mark to market
        invested_value = 0
        for pos in positions:
            cp = close[pos.ticker].iloc[idx]
            if not np.isnan(cp):
                invested_value += pos.shares * cp
        total_value = cash + invested_value
        daily_values.append(total_value)
        daily_dates.append(date)
        
        # Current position size based on current portfolio value
        slot_size = total_value / MAX_POSITIONS
        
        # Check exits
        still_open = []
        for pos in positions:
            cp = close[pos.ticker].iloc[idx]
            days_held = idx - pos.entry_idx
            
            if np.isnan(cp):
                still_open.append(pos)
                continue
            
            pnl_pct = (cp / pos.entry_price) - 1
            exit_reason = None
            
            if pnl_pct <= STOP_LOSS:
                exit_reason = 'stop_loss'
            elif days_held >= MAX_HOLD_DAYS:
                exit_reason = 'max_hold'
            elif days_held >= 5:
                ma50 = get_ma50(close, pos.ticker, idx)
                if ma50 is not None and cp < ma50:
                    exit_reason = 'below_ma50'
            
            if exit_reason is None and days_held >= 10:
                ewros = get_nearest(ewros_cache, idx)
                if ewros.get(pos.ticker, 50) < EWROS_EXIT:
                    exit_reason = 'ewros_drop'
            
            if exit_reason:
                proceeds = pos.shares * cp
                pnl_dollar = proceeds - pos.cost_basis
                cash += proceeds
                closed.append(ClosedTrade(
                    pos.ticker, pos.shares, pos.entry_price, cp,
                    pos.entry_date, date, days_held,
                    round(pnl_dollar, 2), round(pnl_pct * 100, 2),
                    exit_reason, pos.iq_edge, pos.ewros
                ))
            else:
                still_open.append(pos)
        
        positions = still_open
        
        # Check entries
        if len(positions) < MAX_POSITIONS:
            ewros = get_nearest(ewros_cache, idx)
            iq_edge = get_nearest(iq_cache, idx) if iq_cache else {}
            candidates = entry_fn(idx, ewros, iq_edge, close, volume)
            
            held = {p.ticker for p in positions}
            candidates = [c for c in candidates if c[0] not in held]
            
            slots = MAX_POSITIONS - len(positions)
            for ticker, iq_score, ewros_score in candidates[:slots]:
                price = close[ticker].iloc[idx]
                if np.isnan(price) or price <= 0:
                    continue
                if cash < slot_size * 0.5:  # Need at least half a slot
                    break
                
                invest = min(slot_size, cash)
                shares = invest / price
                positions.append(Position(ticker, shares, price, idx, date, invest, iq_score, ewros_score))
                cash -= invest
    
    # Close remaining at last price
    for pos in positions:
        lp = close[pos.ticker].iloc[-1]
        if not np.isnan(lp):
            proceeds = pos.shares * lp
            pnl_dollar = proceeds - pos.cost_basis
            pnl_pct = (lp / pos.entry_price) - 1
            cash += proceeds
            closed.append(ClosedTrade(
                pos.ticker, pos.shares, pos.entry_price, lp,
                pos.entry_date, dates[-1], len(dates) - 1 - pos.entry_idx,
                round(pnl_dollar, 2), round(pnl_pct * 100, 2),
                'end_of_data', pos.iq_edge, pos.ewros
            ))
    
    final_value = daily_values[-1] if daily_values else STARTING_CAPITAL
    
    return closed, daily_values, daily_dates, final_value


def analyze(trades, name, final_value):
    if not trades:
        return {'name': name, 'total_trades': 0}
    
    pnls_pct = [t.pnl_pct for t in trades]
    pnls_dollar = [t.pnl_dollar for t in trades]
    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]
    
    reasons = defaultdict(int)
    for t in trades:
        reasons[t.exit_reason] += 1
    
    gross_profit = sum(t.pnl_dollar for t in wins)
    gross_loss = abs(sum(t.pnl_dollar for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    wr = len(wins) / len(trades)
    avg_win_pct = np.mean([t.pnl_pct for t in wins]) if wins else 0
    avg_loss_pct = np.mean([t.pnl_pct for t in losses]) if losses else 0
    expectancy = (wr * avg_win_pct) + ((1 - wr) * avg_loss_pct)
    
    total_return = (final_value / STARTING_CAPITAL - 1) * 100
    
    return {
        'name': name,
        'starting_capital': STARTING_CAPITAL,
        'final_value': round(final_value, 2),
        'total_return_pct': round(total_return, 1),
        'total_pnl': round(final_value - STARTING_CAPITAL, 2),
        'total_trades': len(trades),
        'winners': len(wins), 'losers': len(losses),
        'win_rate': round(wr * 100, 1),
        'avg_win_pct': round(avg_win_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        'avg_win_dollar': round(np.mean([t.pnl_dollar for t in wins]), 2) if wins else 0,
        'avg_loss_dollar': round(np.mean([t.pnl_dollar for t in losses]), 2) if losses else 0,
        'best_trade': round(max(pnls_pct), 2),
        'worst_trade': round(min(pnls_pct), 2),
        'profit_factor': round(pf, 2),
        'expectancy_pct': round(expectancy, 2),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'avg_hold_days': round(np.mean([t.hold_days for t in trades]), 1),
        'exit_reasons': dict(reasons),
    }


def print_results(s):
    if s['total_trades'] == 0:
        print('   No trades.'); return
    print(f'   ${s["starting_capital"]:,.0f} → ${s["final_value"]:,.0f} ({s["total_return_pct"]:+.1f}%)')
    print(f'   P&L: ${s["total_pnl"]:+,.0f}')
    print(f'   Trades: {s["total_trades"]} ({s["winners"]}W / {s["losers"]}L) · Win Rate: {s["win_rate"]}%')
    print(f'   Avg Win: +{s["avg_win_pct"]}% (${s["avg_win_dollar"]:+,.0f}) · Avg Loss: {s["avg_loss_pct"]}% (${s["avg_loss_dollar"]:,.0f})')
    print(f'   Best: +{s["best_trade"]}% · Worst: {s["worst_trade"]}%')
    print(f'   Profit Factor: {s["profit_factor"]} · Expectancy: {s["expectancy_pct"]}%/trade')
    print(f'   Avg Hold: {s["avg_hold_days"]}d')
    print(f'   Exits: {s["exit_reasons"]}')


# ===== STRATEGIES =====

def strat_iq_top20(idx, ewros, iq_edge, close, volume):
    if not iq_edge: return []
    top = sorted(iq_edge.items(), key=lambda x: -x[1]['pctile'])[:20]
    return [(t, d['pctile'], ewros.get(t, 50)) for t, d in top if is_trend_aligned(close, t, idx)]

def strat_iq_ewros(idx, ewros, iq_edge, close, volume):
    if not iq_edge or not ewros: return []
    cands = []
    for t, d in iq_edge.items():
        if d['pctile'] < 80 or ewros.get(t, 0) < 80: continue
        if not is_trend_aligned(close, t, idx): continue
        cands.append((t, (d['pctile'] + ewros[t]) / 2, ewros[t]))
    cands.sort(key=lambda x: -x[1])
    return cands[:MAX_POSITIONS]

def strat_ewros_top20(idx, ewros, iq_edge, close, volume):
    if not ewros: return []
    top = sorted(ewros.items(), key=lambda x: -x[1])[:20]
    return [(t, s, s) for t, s in top if is_trend_aligned(close, t, idx)]


def main():
    print('🚀 Portfolio Backtest — $10,000 Starting Capital')
    print(f'   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    
    close, volume, high, low = load_ohlcv()
    
    # Load OOS model
    model_path = os.path.join(MODEL_DIR, 'breakout_xgb_oos.pkl')
    if os.path.exists(model_path):
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        print(f'   Loaded OOS model: {model_path}')
    else:
        print('   ⚠️  No OOS model found, running without IQ Edge')
        model = None
    
    # Test period: Sep 2023 onward (model trained on pre-Sep 2023)
    train_end = pd.Timestamp('2023-09-01')
    start_idx = close.index.get_indexer([train_end], method='ffill')[0]
    test_start = close.index[start_idx]
    test_end = close.index[-1]
    print(f'   Test period: {test_start.date()} to {test_end.date()} ({len(close) - start_idx} trading days)')
    
    # SPY buy-and-hold benchmark
    spy_start = close['SPY'].iloc[start_idx]
    spy_end = close['SPY'].iloc[-1]
    spy_return = (spy_end / spy_start - 1) * 100
    spy_final = STARTING_CAPITAL * (spy_end / spy_start)
    spy_values = [(STARTING_CAPITAL * close['SPY'].iloc[i] / spy_start) for i in range(start_idx, len(close))]
    spy_dates = close.index[start_idx:]
    
    print(f'\n📈 SPY Buy & Hold: ${STARTING_CAPITAL:,.0f} → ${spy_final:,.0f} ({spy_return:+.1f}%)')
    
    strategies = [
        ('IQ Edge Top 20 + Trend', strat_iq_top20),
        ('IQ Edge + EWROS ≥80', strat_iq_ewros),
        ('EWROS Top 20 + Trend', strat_ewros_top20),
    ]
    
    all_results = []
    all_values = []
    all_dates = []
    all_trades = []
    
    for name, entry_fn in strategies:
        trades, values, dates_list, final = run_portfolio(
            close, volume, high, low, model, name, entry_fn, start_idx)
        stats = analyze(trades, name, final)
        print_results(stats)
        all_results.append(stats)
        all_values.append(values)
        all_dates.append(dates_list)
        all_trades.append(trades)
        
        # Top trades
        if trades:
            best = sorted(trades, key=lambda x: -x.pnl_dollar)[:3]
            worst = sorted(trades, key=lambda x: x.pnl_dollar)[:3]
            print(f'   💰 Biggest $ winners:')
            for t in best:
                print(f'      {t.ticker}: ${t.pnl_dollar:+,.0f} (+{t.pnl_pct}%, {t.hold_days}d)')
            print(f'   💸 Biggest $ losers:')
            for t in worst:
                print(f'      {t.ticker}: ${t.pnl_dollar:+,.0f} ({t.pnl_pct}%, {t.hold_days}d)')
    
    # ===== CHARTS =====
    print('\n📊 Generating charts...')
    
    # 1. Main equity chart: all strategies vs SPY
    fig, ax = plt.subplots(figsize=(11, 5.5))
    colors = ['#8b5cf6', '#6366f1', '#0ea5e9']
    
    for i, (stats, vals, d) in enumerate(zip(all_results, all_values, all_dates)):
        if vals:
            ax.plot(d, vals, label=f'{stats["name"]} → ${stats["final_value"]:,.0f} ({stats["total_return_pct"]:+.1f}%)',
                    color=colors[i], linewidth=1.8)
    
    # SPY
    ax.plot(spy_dates, spy_values, label=f'SPY Buy & Hold → ${spy_final:,.0f} ({spy_return:+.1f}%)',
            color='#94a3b8', linewidth=1.5, linestyle='--')
    
    ax.axhline(y=STARTING_CAPITAL, color='#64748b', linewidth=0.5, linestyle=':')
    ax.set_title(f'$10,000 Portfolio: Strategies vs SPY Buy & Hold ({test_start.strftime("%b %Y")} – {test_end.strftime("%b %Y")})',
                 fontweight='bold', fontsize=13)
    ax.set_ylabel('Portfolio Value ($)')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True)
    
    # Format y-axis as currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'portfolio_10k.png'), dpi=150)
    plt.close()
    
    # 2. Summary comparison table chart
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    
    names_short = [s['name'].replace('IQ Edge ', 'IQ ').replace(' + Trend', '').replace('EWROS Top 20', 'EWROS Top20') for s in all_results]
    names_short.append('SPY B&H')
    
    # Final value
    finals = [s['final_value'] for s in all_results] + [round(spy_final, 2)]
    bar_colors = ['#8b5cf6', '#6366f1', '#0ea5e9', '#94a3b8']
    x = np.arange(len(names_short))
    axes[0].bar(x, finals, color=bar_colors, alpha=0.85)
    axes[0].set_title('Final Value ($)', fontweight='bold')
    axes[0].set_xticks(x); axes[0].set_xticklabels(names_short, fontsize=7, rotation=15)
    for i, v in enumerate(finals):
        axes[0].text(i, v + 100, f'${v:,.0f}', ha='center', fontsize=7, fontweight='bold')
    axes[0].axhline(y=STARTING_CAPITAL, color='#ef4444', linestyle='--', linewidth=0.8)
    axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    axes[0].grid(True, axis='y')
    
    # Return %
    returns = [s['total_return_pct'] for s in all_results] + [round(spy_return, 1)]
    ret_colors = ['#10b981' if r > 0 else '#ef4444' for r in returns]
    axes[1].bar(x, returns, color=ret_colors, alpha=0.85)
    axes[1].set_title('Total Return (%)', fontweight='bold')
    axes[1].set_xticks(x); axes[1].set_xticklabels(names_short, fontsize=7, rotation=15)
    for i, v in enumerate(returns):
        axes[1].text(i, v + (1 if v >= 0 else -2), f'{v:+.1f}%', ha='center', fontsize=7, fontweight='bold')
    axes[1].axhline(y=0, color='#94a3b8', linestyle='--')
    axes[1].grid(True, axis='y')
    
    # Win rate (strategies only)
    names_strat = names_short[:-1]
    x2 = np.arange(len(names_strat))
    wr = [s['win_rate'] for s in all_results]
    axes[2].bar(x2, wr, color=bar_colors[:len(all_results)], alpha=0.85)
    axes[2].set_title('Win Rate (%)', fontweight='bold')
    axes[2].set_xticks(x2); axes[2].set_xticklabels(names_strat, fontsize=7, rotation=15)
    axes[2].axhline(y=50, color='#94a3b8', linestyle='--')
    for i, v in enumerate(wr):
        axes[2].text(i, v + 0.5, f'{v}%', ha='center', fontsize=7)
    axes[2].grid(True, axis='y')
    
    # Profit factor
    pf = [s['profit_factor'] for s in all_results]
    axes[3].bar(x2, pf, color=bar_colors[:len(all_results)], alpha=0.85)
    axes[3].set_title('Profit Factor', fontweight='bold')
    axes[3].set_xticks(x2); axes[3].set_xticklabels(names_strat, fontsize=7, rotation=15)
    axes[3].axhline(y=1.0, color='#ef4444', linestyle='--')
    for i, v in enumerate(pf):
        axes[3].text(i, v + 0.02, f'{v}', ha='center', fontsize=7, fontweight='bold')
    axes[3].grid(True, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'portfolio_comparison.png'), dpi=150)
    plt.close()
    
    # 3. Drawdown chart
    fig, ax = plt.subplots(figsize=(11, 4))
    for i, (stats, vals, d) in enumerate(zip(all_results, all_values, all_dates)):
        if vals:
            peak = np.maximum.accumulate(vals)
            dd = [(v / p - 1) * 100 for v, p in zip(vals, peak)]
            ax.plot(d, dd, label=stats['name'], color=colors[i], linewidth=1.2)
    # SPY drawdown
    spy_peak = np.maximum.accumulate(spy_values)
    spy_dd = [(v / p - 1) * 100 for v, p in zip(spy_values, spy_peak)]
    ax.plot(spy_dates, spy_dd, label='SPY', color='#94a3b8', linewidth=1, linestyle='--')
    
    ax.set_title('Drawdown from Peak (%)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Drawdown (%)')
    ax.legend(fontsize=8)
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'portfolio_drawdown.png'), dpi=150)
    plt.close()
    
    # Save results
    output = {
        'generated_at': datetime.now().isoformat(),
        'method': 'Portfolio simulation with $10K starting capital, position-sized entries, conditional exits',
        'starting_capital': STARTING_CAPITAL,
        'test_period': f'{test_start.date()} to {test_end.date()}',
        'spy_buy_hold': {
            'final_value': round(spy_final, 2),
            'total_return_pct': round(spy_return, 1),
        },
        'strategies': {s['name']: s for s in all_results},
    }
    
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)
        existing['portfolio_10k'] = output
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(existing, f, indent=2, default=str)
    else:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump({'portfolio_10k': output}, f, indent=2, default=str)
    
    print(f'\n✅ Portfolio backtest complete!')
    print(f'   Results: {OUTPUT_FILE}')
    
    # Final summary
    print(f'\n{"="*55}')
    print(f'   FINAL SCORECARD ($10,000 invested {test_start.strftime("%b %Y")})')
    print(f'{"="*55}')
    for s in all_results:
        print(f'   {s["name"]:30s} → ${s["final_value"]:>10,.0f} ({s["total_return_pct"]:+.1f}%)')
    print(f'   {"SPY Buy & Hold":30s} → ${spy_final:>10,.0f} ({spy_return:+.1f}%)')
    print(f'{"="*55}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
IQ Edge Honest Backtest — Train on first 2.5 years, test on last 2.5 years.

1. Retrain XGBoost using ONLY data before Sep 2023
2. Score stocks daily using the frozen model
3. Run event-driven backtest on Oct 2023 – Mar 2026 (unseen data)
4. Same entry/exit rules as EWROS strategies for fair comparison

Usage:
    python3 scripts/iq_edge_backtest.py
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

# Parameters
MAX_POSITIONS = 20
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

# Train/test split: first 2.5 years train, last 2.5 years test
TRAIN_END = pd.Timestamp('2023-09-01')


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
    
    print(f'   {len(close.columns)} tickers, {len(close)} days')
    return close, volume, high, low


def retrain_model():
    """Retrain XGBoost using ONLY events before TRAIN_END."""
    import xgboost as xgb
    
    print(f'\n🧠 Retraining XGBoost (train < {TRAIN_END.date()}, test ≥ {TRAIN_END.date()})...')
    df = pd.read_parquet(EVENTS_FILE)
    df = df.sort_values('date').reset_index(drop=True)
    df['target'] = (df['label'] == 'double').astype(int)
    
    train_mask = df['date'] < TRAIN_END
    test_mask = df['date'] >= TRAIN_END
    
    X_train = df.loc[train_mask, FEATURE_COLS].values
    y_train = df.loc[train_mask, 'target'].values
    X_test = df.loc[test_mask, FEATURE_COLS].values
    y_test = df.loc[test_mask, 'target'].values
    
    print(f'   Train: {len(X_train)} events ({y_train.sum()} doubles, {y_train.mean()*100:.1f}%)')
    print(f'   Test:  {len(X_test)} events ({y_test.sum()} doubles, {y_test.mean()*100:.1f}%)')
    
    # Handle imbalance
    scale_pos_weight = (len(y_train) - y_train.sum()) / max(y_train.sum(), 1)
    
    # Use a portion of train for early stopping
    val_split = int(len(X_train) * 0.85)
    X_tr, X_val = X_train[:val_split], X_train[val_split:]
    y_tr, y_val = y_train[:val_split], y_train[val_split:]
    
    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        eval_metric='aucpr',
        early_stopping_rounds=50,
        random_state=42,
        use_label_encoder=False
    )
    
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    
    from sklearn.metrics import roc_auc_score, precision_score, recall_score
    
    for name, X, y in [('Train', X_train, y_train), ('Test (OOS)', X_test, y_test)]:
        probs = model.predict_proba(X)[:, 1]
        preds = (probs >= 0.5).astype(int)
        auc = roc_auc_score(y, probs) if len(np.unique(y)) > 1 else 0
        
        top_n = max(1, len(probs) // 10)
        top_idx = np.argsort(probs)[-top_n:]
        top_prec = y[top_idx].mean()
        
        print(f'   {name}: AUC={auc:.3f}, Top-10% precision={top_prec:.3f} ({int(y[top_idx].sum())}/{len(top_idx)})')
    
    # Feature importance
    importance = sorted(zip(FEATURE_COLS, model.feature_importances_), key=lambda x: -x[1])
    print(f'\n   Feature Importance (top 5):')
    for feat, imp in importance[:5]:
        print(f'      {feat}: {imp:.3f}')
    
    # Save
    model_path = os.path.join(MODEL_DIR, 'breakout_xgb_oos.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f'   Saved: {model_path}')
    
    return model


def compute_iq_edge_at_idx(close, volume, high, low, idx, model):
    """Score all stocks with IQ Edge at a given index."""
    scores = {}
    for ticker in close.columns:
        if ticker == 'SPY':
            continue
        
        prices = close[ticker].iloc[max(0, idx-252):idx+1].dropna()
        vols = volume[ticker].iloc[max(0, idx-252):idx+1].dropna()
        highs = high[ticker].iloc[max(0, idx-252):idx+1].dropna()
        lows = low[ticker].iloc[max(0, idx-252):idx+1].dropna()
        
        if len(prices) < 60:
            continue
        
        try:
            current = prices.iloc[-1]
            ma20 = prices.iloc[-20:].mean() if len(prices) >= 20 else current
            ma50 = prices.iloc[-50:].mean() if len(prices) >= 50 else current
            ma200 = prices.iloc[-200:].mean() if len(prices) >= 200 else prices.mean()
            
            close_to_ma20 = current / ma20 - 1
            close_to_ma50 = current / ma50 - 1
            close_to_ma200 = current / ma200 - 1
            trend_aligned = 1.0 if (current > ma50 > ma200) else 0.0
            
            if len(highs) >= 15 and len(lows) >= 15 and len(prices) >= 15:
                tr = np.maximum(
                    highs.iloc[-15:].values - lows.iloc[-15:].values,
                    np.maximum(
                        abs(highs.iloc[-15:].values - prices.iloc[-16:-1].values),
                        abs(lows.iloc[-15:].values - prices.iloc[-16:-1].values)))
                atr_14 = np.mean(tr[-14:]) / current if current > 0 else 0
            else:
                atr_14 = 0.02
            
            if len(vols) >= 50:
                recent_vol = vols.iloc[-10:].mean()
                base_vol = vols.iloc[-50:-10].mean()
                vol_dryup = recent_vol / base_vol if base_vol > 0 else 1
                breakout_vol = vols.iloc[-1] / vols.iloc[-50:].mean() if vols.iloc[-50:].mean() > 0 else 1
            else:
                vol_dryup = 1
                breakout_vol = 1
            
            if len(prices) >= 40:
                vol_compression = prices.iloc[-10:].pct_change().std() / prices.iloc[-40:].pct_change().std()
                vol_compression = vol_compression if np.isfinite(vol_compression) else 1
            else:
                vol_compression = 1
            
            proximity_52w = current / prices.max() if prices.max() > 0 else 0
            return_3mo = (current / prices.iloc[-63] - 1) if len(prices) >= 63 else 0
            
            changes = prices.pct_change().dropna()
            up_days_pct = (changes > 0).mean() if len(changes) > 0 else 0.5
            
            base_prices = prices.iloc[-40:]
            base_length = len(base_prices) / 120
            base_range = (base_prices.max() - base_prices.min()) / base_prices.mean() if base_prices.mean() > 0 else 0
            
            if len(vols) >= 40:
                vol_trend = vols.iloc[-20:].mean() / vols.iloc[-40:-20].mean() - 1
                vol_trend = vol_trend if np.isfinite(vol_trend) else 0
            else:
                vol_trend = 0
            
            features = np.array([[
                close_to_ma20, close_to_ma50, close_to_ma200,
                trend_aligned, atr_14, vol_dryup, vol_compression,
                proximity_52w, return_3mo, up_days_pct,
                vol_trend, base_length, base_range, breakout_vol
            ]])
            
            # Replace nan/inf
            features = np.nan_to_num(features, nan=0, posinf=1, neginf=-1)
            
            prob = model.predict_proba(features)[0][1]
            scores[ticker] = prob
        except Exception:
            continue
    
    if not scores:
        return {}
    
    tickers = list(scores.keys())
    raw = np.array([scores[t] for t in tickers])
    pctiles = rankdata(raw, method='average') / len(raw) * 99
    return {t: {'pctile': round(p, 1), 'prob': round(scores[t], 4)} for t, p in zip(tickers, pctiles)}


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
    
    raw_scores = {}
    for ticker in stock_rets.columns:
        if ticker == 'SPY':
            continue
        sr = stock_rets[ticker].values
        spy_r = spy_ret.values
        mask = ~(np.isnan(sr) | np.isnan(spy_r))
        if mask.sum() < EWROS_LOOKBACK * 0.5:
            continue
        raw_scores[ticker] = ((sr[mask] - spy_r[mask]) * weights[mask]).sum()
    
    if not raw_scores:
        return {}
    tickers = list(raw_scores.keys())
    raw = np.array([raw_scores[t] for t in tickers])
    pctiles = rankdata(raw, method='average') / len(raw) * 99
    return {t: round(p, 1) for t, p in zip(tickers, pctiles)}


def is_trend_aligned(close, ticker, idx):
    prices = close[ticker].values
    current = prices[idx]
    if np.isnan(current) or idx < 200:
        return False
    ma50 = np.nanmean(prices[max(0,idx-49):idx+1])
    ma200 = np.nanmean(prices[max(0,idx-199):idx+1])
    return current > ma50 > ma200


def get_ma50(close, ticker, idx):
    if idx < 50:
        return None
    prices = close[ticker].values[idx-49:idx+1]
    valid = prices[~np.isnan(prices)]
    return np.mean(valid) if len(valid) >= 30 else None


class Trade:
    def __init__(self, ticker, entry_date, entry_price, entry_idx, iq_edge=0, ewros=0):
        self.ticker = ticker
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.entry_idx = entry_idx
        self.iq_edge = iq_edge
        self.ewros = ewros
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl_pct = None
        self.hold_days = 0


def run_strategy(close, volume, high, low, model, name, entry_fn, test_start_idx):
    """Run event-driven backtest starting from test_start_idx."""
    print(f'\n🔬 Strategy: {name}')
    
    open_trades = []
    closed_trades = []
    dates = close.index
    
    # Pre-compute EWROS + IQ Edge weekly
    ewros_cache = {}
    iq_cache = {}
    print(f'   Pre-computing signals (EWROS + IQ Edge)...', end=' ', flush=True)
    for idx in range(test_start_idx, len(dates), 5):
        ewros_cache[idx] = compute_ewros_at_idx(close, idx)
        iq_cache[idx] = compute_iq_edge_at_idx(close, volume, high, low, idx, model)
    print(f'{len(ewros_cache)} snapshots')
    
    def get_nearest(cache, idx):
        keys = [k for k in cache if k <= idx]
        return cache[max(keys)] if keys else {}
    
    equity = [100.0]
    equity_dates = [dates[test_start_idx]]
    
    for idx in range(test_start_idx, len(dates)):
        current_date = dates[idx]
        
        # Check exits
        still_open = []
        for trade in open_trades:
            cp = close[trade.ticker].iloc[idx]
            days_held = idx - trade.entry_idx
            
            if np.isnan(cp):
                still_open.append(trade)
                continue
            
            pnl = (cp / trade.entry_price) - 1
            exit_reason = None
            
            if pnl <= STOP_LOSS:
                exit_reason = 'stop_loss'
            elif days_held >= MAX_HOLD_DAYS:
                exit_reason = 'max_hold'
            elif days_held >= 5:
                ma50 = get_ma50(close, trade.ticker, idx)
                if ma50 is not None and cp < ma50:
                    exit_reason = 'below_ma50'
            
            # EWROS exit
            if exit_reason is None and days_held >= 10:
                ewros = get_nearest(ewros_cache, idx)
                if ewros.get(trade.ticker, 50) < EWROS_EXIT:
                    exit_reason = 'ewros_drop'
            
            if exit_reason:
                trade.exit_date = current_date
                trade.exit_price = cp
                trade.exit_reason = exit_reason
                trade.pnl_pct = round(pnl * 100, 2)
                trade.hold_days = days_held
                closed_trades.append(trade)
            else:
                still_open.append(trade)
        
        open_trades = still_open
        
        # Check entries
        if len(open_trades) < MAX_POSITIONS:
            ewros = get_nearest(ewros_cache, idx)
            iq_edge = get_nearest(iq_cache, idx)
            candidates = entry_fn(idx, ewros, iq_edge, close, volume)
            
            held = {t.ticker for t in open_trades}
            candidates = [c for c in candidates if c[0] not in held]
            
            slots = MAX_POSITIONS - len(open_trades)
            for ticker, iq_score, ewros_score in candidates[:slots]:
                price = close[ticker].iloc[idx]
                if not np.isnan(price) and price > 0:
                    open_trades.append(Trade(ticker, current_date, price, idx, iq_score, ewros_score))
        
        # Equity tracking
        total_pnl = sum((close[t.ticker].iloc[idx] / t.entry_price - 1) 
                        for t in open_trades if not np.isnan(close[t.ticker].iloc[idx]))
        n = len(open_trades)
        if n > 0:
            equity.append(equity[-1] * (1 + total_pnl / MAX_POSITIONS / max(n, 1) * n))
        else:
            equity.append(equity[-1])
        equity_dates.append(current_date)
    
    # Close remaining
    for trade in open_trades:
        lp = close[trade.ticker].iloc[-1]
        if not np.isnan(lp):
            trade.exit_date = dates[-1]
            trade.exit_price = lp
            trade.exit_reason = 'end_of_data'
            trade.pnl_pct = round((lp / trade.entry_price - 1) * 100, 2)
            trade.hold_days = len(dates) - 1 - trade.entry_idx
            closed_trades.append(trade)
    
    return closed_trades, equity, equity_dates


def analyze_trades(trades, name):
    if not trades:
        return {'name': name, 'total_trades': 0}
    
    pnls = [t.pnl_pct for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    reasons = defaultdict(int)
    for t in trades:
        reasons[t.exit_reason] += 1
    
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    win_rate = len(wins) / len(pnls)
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
    
    return {
        'name': name,
        'total_trades': len(trades),
        'winners': len(wins), 'losers': len(losses),
        'win_rate': round(win_rate * 100, 1),
        'avg_gain': round(np.mean(pnls), 2),
        'median_gain': round(np.median(pnls), 2),
        'avg_win': round(avg_win, 2), 'avg_loss': round(avg_loss, 2),
        'best_trade': round(max(pnls), 2), 'worst_trade': round(min(pnls), 2),
        'profit_factor': round(profit_factor, 2),
        'expectancy': round(expectancy, 2),
        'total_return': round(sum(pnls), 1),
        'avg_hold_days': round(np.mean([t.hold_days for t in trades]), 1),
        'exit_reasons': dict(reasons),
    }


def print_stats(stats):
    if stats['total_trades'] == 0:
        print('   No trades.')
        return
    print(f'   Trades: {stats["total_trades"]} ({stats["winners"]}W / {stats["losers"]}L)')
    print(f'   Win Rate: {stats["win_rate"]}%')
    print(f'   Avg Gain: {stats["avg_gain"]}% | Median: {stats["median_gain"]}%')
    print(f'   Avg Win: +{stats["avg_win"]}% | Avg Loss: {stats["avg_loss"]}%')
    print(f'   Best: +{stats["best_trade"]}% | Worst: {stats["worst_trade"]}%')
    print(f'   Profit Factor: {stats["profit_factor"]}')
    print(f'   Expectancy: {stats["expectancy"]}% per trade')
    print(f'   Avg Hold: {stats["avg_hold_days"]}d')
    print(f'   Exits: {stats["exit_reasons"]}')


# ===== STRATEGY DEFINITIONS =====

def strategy_iq_edge_top20(idx, ewros, iq_edge, close, volume):
    """Top 20 IQ Edge + trend aligned."""
    if not iq_edge:
        return []
    sorted_iq = sorted(iq_edge.items(), key=lambda x: -x[1]['pctile'])[:20]
    candidates = []
    for ticker, data in sorted_iq:
        if not is_trend_aligned(close, ticker, idx):
            continue
        candidates.append((ticker, data['pctile'], ewros.get(ticker, 50)))
    return candidates


def strategy_iq_edge_80_trend(idx, ewros, iq_edge, close, volume):
    """IQ Edge ≥ 80 + trend aligned."""
    if not iq_edge:
        return []
    candidates = []
    for ticker, data in iq_edge.items():
        if data['pctile'] < 80:
            continue
        if not is_trend_aligned(close, ticker, idx):
            continue
        candidates.append((ticker, data['pctile'], ewros.get(ticker, 50)))
    candidates.sort(key=lambda x: -x[1])
    return candidates[:MAX_POSITIONS]


def strategy_iq_plus_ewros(idx, ewros, iq_edge, close, volume):
    """IQ Edge ≥ 80 + EWROS ≥ 80 + trend aligned (combined signal)."""
    if not iq_edge or not ewros:
        return []
    candidates = []
    for ticker, data in iq_edge.items():
        if data['pctile'] < 80:
            continue
        if ewros.get(ticker, 0) < 80:
            continue
        if not is_trend_aligned(close, ticker, idx):
            continue
        # Score by average of both signals
        combined = (data['pctile'] + ewros[ticker]) / 2
        candidates.append((ticker, combined, ewros[ticker]))
    candidates.sort(key=lambda x: -x[1])
    return candidates[:MAX_POSITIONS]


def strategy_ewros_top20_benchmark(idx, ewros, iq_edge, close, volume):
    """EWROS Top 20 + trend (benchmark for comparison)."""
    if not ewros:
        return []
    sorted_ewros = sorted(ewros.items(), key=lambda x: -x[1])[:20]
    candidates = []
    for ticker, score in sorted_ewros:
        if not is_trend_aligned(close, ticker, idx):
            continue
        candidates.append((ticker, score, score))
    return candidates


def main():
    print('🚀 IQ Edge Honest Backtest — Train/Test Split')
    print(f'   Train: before {TRAIN_END.date()} | Test: {TRAIN_END.date()} onward')
    print(f'   Same entry/exit rules as EWROS strategies\n')
    
    close, volume, high, low = load_ohlcv()
    
    # Step 1: Retrain model on first 2.5 years only
    model = retrain_model()
    
    # Find test start index
    test_start_idx = close.index.get_indexer([TRAIN_END], method='ffill')[0]
    print(f'\n   Test period: {close.index[test_start_idx].date()} to {close.index[-1].date()}')
    print(f'   Test days: {len(close) - test_start_idx}')
    
    # Step 2: Run strategies on test period only
    strategies = [
        ('IQ Edge Top 20 + Trend', strategy_iq_edge_top20),
        ('IQ Edge ≥80 + Trend', strategy_iq_edge_80_trend),
        ('IQ Edge + EWROS ≥80', strategy_iq_plus_ewros),
        ('EWROS Top 20 (benchmark)', strategy_ewros_top20_benchmark),
    ]
    
    all_results = []
    all_equity = []
    all_equity_dates = []
    all_trades = []
    
    for name, entry_fn in strategies:
        trades, equity, eq_dates = run_strategy(close, volume, high, low, model, name, entry_fn, test_start_idx)
        stats = analyze_trades(trades, name)
        print_stats(stats)
        all_results.append(stats)
        all_equity.append(equity)
        all_equity_dates.append(eq_dates)
        all_trades.append(trades)
        
        if trades:
            winners = sorted([t for t in trades if t.pnl_pct > 0], key=lambda x: -x.pnl_pct)
            losers = sorted([t for t in trades if t.pnl_pct <= 0], key=lambda x: x.pnl_pct)
            print(f'   Top 3 winners:')
            for t in winners[:3]:
                print(f'      {t.ticker}: +{t.pnl_pct}% (IQ={t.iq_edge:.0f}, EWROS={t.ewros:.0f}, {t.hold_days}d, {t.exit_reason})')
            print(f'   Top 3 losers:')
            for t in losers[:3]:
                print(f'      {t.ticker}: {t.pnl_pct}% (IQ={t.iq_edge:.0f}, EWROS={t.ewros:.0f}, {t.hold_days}d, {t.exit_reason})')
    
    # Charts
    print('\n📊 Generating charts...')
    
    # Equity curves
    fig, ax = plt.subplots(figsize=(10, 5))
    colors_list = ['#8b5cf6', '#a855f7', '#6366f1', '#0ea5e9']
    for i, (stats, eq, eq_dates) in enumerate(zip(all_results, all_equity, all_equity_dates)):
        if eq and eq_dates and stats['total_trades'] > 0:
            ax.plot(eq_dates, eq, label=f'{stats["name"]} (PF={stats["profit_factor"]})', 
                    color=colors_list[i], linewidth=1.5)
    ax.axhline(y=100, color='#94a3b8', linestyle='--', linewidth=0.5)
    ax.set_title(f'IQ Edge Backtest: Out-of-Sample ({TRAIN_END.date()} onward)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Growth of $100')
    ax.legend(fontsize=8)
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'iq_edge_oos_equity.png'), dpi=150)
    plt.close()
    
    # Comparison bar chart
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    valid = [r for r in all_results if r['total_trades'] > 0]
    names = [r['name'].replace('IQ Edge ', 'IQ ').replace('EWROS Top 20 (benchmark)', 'EWROS Top20') for r in valid]
    x = np.arange(len(names))
    
    # Win rate
    wr = [r['win_rate'] for r in valid]
    axes[0].bar(x, wr, color=colors_list[:len(valid)], alpha=0.85)
    axes[0].set_title('Win Rate (%)', fontweight='bold')
    axes[0].set_xticks(x); axes[0].set_xticklabels(names, fontsize=7, rotation=15)
    axes[0].axhline(y=50, color='#94a3b8', linestyle='--')
    for i, v in enumerate(wr):
        axes[0].text(i, v+0.5, f'{v}%', ha='center', fontsize=8)
    axes[0].grid(True, axis='y')
    
    # Profit factor
    pf = [r['profit_factor'] for r in valid]
    axes[1].bar(x, pf, color=colors_list[:len(valid)], alpha=0.85)
    axes[1].set_title('Profit Factor (>1 = profitable)', fontweight='bold')
    axes[1].set_xticks(x); axes[1].set_xticklabels(names, fontsize=7, rotation=15)
    axes[1].axhline(y=1.0, color='#ef4444', linestyle='--')
    for i, v in enumerate(pf):
        axes[1].text(i, v+0.02, f'{v}', ha='center', fontsize=8, fontweight='bold')
    axes[1].grid(True, axis='y')
    
    # Expectancy
    exp = [r['expectancy'] for r in valid]
    bar_colors = ['#10b981' if e > 0 else '#ef4444' for e in exp]
    axes[2].bar(x, exp, color=bar_colors, alpha=0.85)
    axes[2].set_title('Expectancy (% per trade)', fontweight='bold')
    axes[2].set_xticks(x); axes[2].set_xticklabels(names, fontsize=7, rotation=15)
    axes[2].axhline(y=0, color='#94a3b8', linestyle='--')
    for i, v in enumerate(exp):
        axes[2].text(i, v + (0.1 if v >= 0 else -0.3), f'{v}%', ha='center', fontsize=8, fontweight='bold')
    axes[2].grid(True, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'iq_edge_oos_comparison.png'), dpi=150)
    plt.close()
    
    # Save results
    output = {
        'generated_at': datetime.now().isoformat(),
        'method': f'Event-driven, XGBoost trained on data before {TRAIN_END.date()}, tested on {TRAIN_END.date()} onward',
        'train_end': str(TRAIN_END.date()),
        'test_start': str(close.index[test_start_idx].date()),
        'test_end': str(close.index[-1].date()),
        'test_days': len(close) - test_start_idx,
        'parameters': {
            'max_positions': MAX_POSITIONS, 'stop_loss': f'{STOP_LOSS*100}%',
            'ewros_exit': EWROS_EXIT, 'max_hold_days': MAX_HOLD_DAYS,
        },
        'strategies': {r['name']: r for r in all_results},
    }
    
    # Merge with existing results if present
    existing_file = OUTPUT_FILE
    if os.path.exists(existing_file):
        with open(existing_file) as f:
            existing = json.load(f)
        existing['iq_edge_oos'] = output
        with open(existing_file, 'w') as f:
            json.dump(existing, f, indent=2, default=str)
    else:
        with open(existing_file, 'w') as f:
            json.dump({'iq_edge_oos': output}, f, indent=2, default=str)
    
    print(f'\n✅ IQ Edge OOS backtest complete!')
    print(f'   Results merged into: {OUTPUT_FILE}')


if __name__ == '__main__':
    main()

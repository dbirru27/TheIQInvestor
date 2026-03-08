#!/usr/bin/env python3
"""
Walk-Forward Backtest Engine — Proper out-of-sample testing.

For each rebalance date (monthly):
  1. Compute scores using ONLY data available up to that date
  2. Rank stocks, form portfolios
  3. Measure FORWARD returns (next 1/3/6 months)
  4. Aggregate across all periods

No look-ahead bias. No circular reasoning.

Signals tested:
  1. Quality Score (simplified: trend + MA + revenue proxy)
  2. EWROS (recomputed monthly with trailing 63 days)
  3. Rotation Score (proxy: volume + trend + momentum signals)
  4. IQ Edge (XGBoost model applied at each rebalance)
  5. Power Matrix (EWROS × Rotation combined)

Usage:
    python3 scripts/backtest_engine.py
"""
import json
import os
import sys
import warnings
import pickle
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy.stats import rankdata

warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
CHARTS_DIR = os.path.join(ROOT, 'reports', 'charts')
OHLCV_FILE = os.path.join(DATA_DIR, 'historical_ohlcv.parquet')
MODEL_FILE = os.path.join(ROOT, 'models', 'breakout_xgb_double.pkl')
OUTPUT_FILE = os.path.join(DATA_DIR, 'backtest_results.json')

os.makedirs(CHARTS_DIR, exist_ok=True)

# Print-friendly chart styling
plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#cbd5e1',
    'axes.labelcolor': '#1a1a1a',
    'text.color': '#1a1a1a',
    'xtick.color': '#333333',
    'ytick.color': '#333333',
    'grid.color': '#e2e8f0',
    'grid.alpha': 0.7,
    'font.family': 'sans-serif',
    'font.size': 10,
})

# EWROS params
EWROS_LOOKBACK = 63
EWROS_LAMBDA = 0.03

# IQ Edge features (must match iq_edge_predict.py)
FEATURE_COLS = [
    'close_to_ma20', 'close_to_ma50', 'close_to_ma200',
    'trend_aligned', 'atr_14', 'vol_dryup_ratio', 'vol_compression',
    'proximity_52w', 'return_3mo', 'up_days_pct',
    'vol_trend_in_base', 'base_length', 'base_range', 'breakout_vol_ratio'
]


def load_data():
    """Load OHLCV and pivot to price/volume matrices."""
    print('📊 Loading 5-year OHLCV data...')
    ohlcv = pd.read_parquet(OHLCV_FILE)
    ohlcv['date'] = pd.to_datetime(ohlcv['date'])
    
    close = ohlcv.pivot_table(index='date', columns='ticker', values='close')
    volume = ohlcv.pivot_table(index='date', columns='ticker', values='volume')
    high = ohlcv.pivot_table(index='date', columns='ticker', values='high')
    low = ohlcv.pivot_table(index='date', columns='ticker', values='low')
    
    # Need SPY as benchmark
    if 'SPY' not in close.columns:
        print('⚠️  SPY not in data — downloading...')
        import yfinance as yf
        spy = yf.download('SPY', start=close.index[0], end=close.index[-1] + timedelta(days=1), progress=False)
        close['SPY'] = spy['Close']
        volume['SPY'] = spy['Volume']
    
    print(f'   {len(close.columns)} tickers, {len(close)} days ({close.index[0].date()} to {close.index[-1].date()})')
    return close, volume, high, low


def compute_ewros_at_date(close, date, spy_col='SPY', lookback=EWROS_LOOKBACK, lam=EWROS_LAMBDA):
    """Compute EWROS for all stocks using only data up to `date`."""
    idx = close.index.get_indexer([date], method='ffill')[0]
    if idx < lookback:
        return {}
    
    window = close.iloc[idx - lookback + 1:idx + 1]
    if 'SPY' not in window.columns:
        return {}
    
    spy_ret = window['SPY'].pct_change().iloc[1:]
    stock_rets = window.pct_change().iloc[1:]
    
    days_ago = np.arange(len(spy_ret) - 1, -1, -1)
    weights = np.exp(-lam * days_ago)
    
    scores = {}
    for ticker in stock_rets.columns:
        if ticker == 'SPY':
            continue
        sr = stock_rets[ticker].values
        spy_r = spy_ret.values
        mask = ~(np.isnan(sr) | np.isnan(spy_r))
        if mask.sum() < lookback * 0.5:
            continue
        alpha = (sr[mask] - spy_r[mask]) * weights[mask]
        scores[ticker] = alpha.sum()
    
    if not scores:
        return {}
    
    # Rank to percentile
    tickers = list(scores.keys())
    raw = np.array([scores[t] for t in tickers])
    pctiles = rankdata(raw, method='average') / len(raw) * 99
    return {t: round(p, 1) for t, p in zip(tickers, pctiles)}


def compute_quality_proxy_at_date(close, volume, date, lookback=200):
    """
    Compute a quality proxy score using only price/volume data up to `date`.
    
    Components (all observable from price/volume):
      - Trend alignment: price > MA50 > MA200 (0 or 1)
      - Proximity to 52W high (0-1)
      - 6-month return vs SPY (relative momentum)
      - Volume trend (recent vs older — accumulation signal)
      - Base tightness (low volatility in recent 20 days)
    """
    idx = close.index.get_indexer([date], method='ffill')[0]
    if idx < lookback:
        return {}
    
    window = close.iloc[max(0, idx - 252):idx + 1]
    vol_window = volume.iloc[max(0, idx - 252):idx + 1]
    
    spy_ret_6m = 0
    if 'SPY' in window.columns and len(window) > 126:
        spy_6m = window['SPY'].iloc[-126:]
        spy_ret_6m = (spy_6m.iloc[-1] / spy_6m.iloc[0]) - 1
    
    scores = {}
    for ticker in close.columns:
        if ticker == 'SPY':
            continue
        prices = window[ticker].dropna()
        if len(prices) < 60:
            continue
        
        current = prices.iloc[-1]
        
        # Trend alignment
        ma50 = prices.iloc[-50:].mean() if len(prices) >= 50 else current
        ma200 = prices.iloc[-200:].mean() if len(prices) >= 200 else prices.mean()
        trend = 1.0 if (current > ma50 > ma200) else 0.0
        
        # 52W proximity
        high_52w = prices.max()
        prox = current / high_52w if high_52w > 0 else 0
        
        # 6-month relative return
        if len(prices) > 126:
            ret_6m = (current / prices.iloc[-126]) - 1
            rel_return = ret_6m - spy_ret_6m
        else:
            rel_return = 0
        
        # Volume accumulation (recent 20d vs prior 40d)
        vols = vol_window[ticker].dropna()
        if len(vols) > 60:
            recent_vol = vols.iloc[-20:].mean()
            prior_vol = vols.iloc[-60:-20].mean()
            vol_ratio = recent_vol / prior_vol if prior_vol > 0 else 1
        else:
            vol_ratio = 1
        
        # Base tightness (lower ATR = tighter base = better)
        if len(prices) >= 20:
            daily_range = prices.iloc[-20:].pct_change().std()
            tightness = max(0, 1 - daily_range * 15)  # Normalize
        else:
            tightness = 0.5
        
        # Composite score: 0-100
        score = (
            trend * 25 +              # Trend alignment
            prox * 25 +               # Near highs
            min(max(rel_return * 50 + 25, 0), 25) +  # Relative momentum
            min(max(vol_ratio - 0.5, 0), 1) * 15 +   # Volume accumulation
            tightness * 10            # Base tightness
        )
        scores[ticker] = round(min(max(score, 0), 100), 1)
    
    return scores


def compute_rotation_proxy_at_date(close, volume, date):
    """
    Compute rotation score proxy using only price/volume up to `date`.
    
    Signals:
      - RS divergence: stock up while SPY down in recent 10 days
      - Stage breakout: price breaks above 50d high
      - Volume surge: recent 5d volume vs 50d average
      - Short-term momentum: 1-month return
      - Trend change: crossing above MA50
    """
    idx = close.index.get_indexer([date], method='ffill')[0]
    if idx < 60:
        return {}
    
    scores = {}
    spy_prices = close['SPY'].iloc[max(0, idx - 60):idx + 1] if 'SPY' in close.columns else None
    
    for ticker in close.columns:
        if ticker == 'SPY':
            continue
        prices = close[ticker].iloc[max(0, idx - 60):idx + 1].dropna()
        vols = volume[ticker].iloc[max(0, idx - 60):idx + 1].dropna()
        if len(prices) < 30 or len(vols) < 30:
            continue
        
        current = prices.iloc[-1]
        
        # RS divergence (stock up while SPY down over last 10 days)
        rs_div = 0
        if spy_prices is not None and len(spy_prices) >= 10:
            stock_10d = (current / prices.iloc[-10]) - 1
            spy_10d = (spy_prices.iloc[-1] / spy_prices.iloc[-10]) - 1
            if stock_10d > 0 and spy_10d < 0:
                rs_div = 1
            elif stock_10d > spy_10d:
                rs_div = 0.5
        
        # Stage breakout: price above 50d high
        if len(prices) >= 50:
            high_50d = prices.iloc[-50:-1].max()
            breakout = 1.0 if current > high_50d else 0.0
        else:
            breakout = 0
        
        # Volume surge
        if len(vols) >= 50:
            recent_vol = vols.iloc[-5:].mean()
            avg_vol = vols.iloc[-50:].mean()
            vol_surge = min(recent_vol / avg_vol, 3) / 3 if avg_vol > 0 else 0
        else:
            vol_surge = 0
        
        # 1-month momentum
        if len(prices) >= 21:
            mom = (current / prices.iloc[-21]) - 1
            mom_score = min(max(mom * 5 + 0.5, 0), 1)
        else:
            mom_score = 0.5
        
        # MA50 cross
        if len(prices) >= 50:
            ma50 = prices.iloc[-50:].mean()
            ma_cross = 1 if current > ma50 else 0
        else:
            ma_cross = 0
        
        # Composite: 0-100
        score = (rs_div * 25 + breakout * 25 + vol_surge * 20 + mom_score * 15 + ma_cross * 15)
        scores[ticker] = round(min(max(score, 0), 100), 1)
    
    return scores


def compute_iq_edge_at_date(close, volume, high, low, date, model):
    """Compute IQ Edge features for all stocks at `date` and predict with XGBoost."""
    idx = close.index.get_indexer([date], method='ffill')[0]
    if idx < 200:
        return {}
    
    scores = {}
    for ticker in close.columns:
        if ticker == 'SPY':
            continue
        
        prices = close[ticker].iloc[max(0, idx - 252):idx + 1].dropna()
        vols = volume[ticker].iloc[max(0, idx - 252):idx + 1].dropna()
        highs = high[ticker].iloc[max(0, idx - 252):idx + 1].dropna()
        lows = low[ticker].iloc[max(0, idx - 252):idx + 1].dropna()
        
        if len(prices) < 60:
            continue
        
        try:
            current = prices.iloc[-1]
            
            # MAs
            ma20 = prices.iloc[-20:].mean() if len(prices) >= 20 else current
            ma50 = prices.iloc[-50:].mean() if len(prices) >= 50 else current
            ma200 = prices.iloc[-200:].mean() if len(prices) >= 200 else prices.mean()
            
            close_to_ma20 = current / ma20 - 1 if ma20 > 0 else 0
            close_to_ma50 = current / ma50 - 1 if ma50 > 0 else 0
            close_to_ma200 = current / ma200 - 1 if ma200 > 0 else 0
            trend_aligned = 1.0 if (current > ma50 > ma200) else 0.0
            
            # ATR 14
            if len(highs) >= 15 and len(lows) >= 15 and len(prices) >= 15:
                tr = np.maximum(
                    highs.iloc[-15:].values - lows.iloc[-15:].values,
                    np.maximum(
                        abs(highs.iloc[-15:].values - prices.iloc[-16:-1].values),
                        abs(lows.iloc[-15:].values - prices.iloc[-16:-1].values)
                    )
                )
                atr_14 = np.mean(tr[-14:]) / current if current > 0 else 0
            else:
                atr_14 = 0.02
            
            # Volume features
            if len(vols) >= 50:
                recent_vol = vols.iloc[-10:].mean()
                base_vol = vols.iloc[-50:-10].mean()
                vol_dryup = recent_vol / base_vol if base_vol > 0 else 1
                breakout_vol = vols.iloc[-1] / vols.iloc[-50:].mean() if vols.iloc[-50:].mean() > 0 else 1
            else:
                vol_dryup = 1
                breakout_vol = 1
            
            # Volatility compression
            if len(prices) >= 40:
                recent_std = prices.iloc[-10:].pct_change().std()
                longer_std = prices.iloc[-40:].pct_change().std()
                vol_compression = recent_std / longer_std if longer_std > 0 else 1
            else:
                vol_compression = 1
            
            # 52W proximity
            high_52w = prices.max()
            proximity_52w = current / high_52w if high_52w > 0 else 0
            
            # 3-month return
            if len(prices) >= 63:
                return_3mo = (current / prices.iloc[-63]) - 1
            else:
                return_3mo = 0
            
            # Up days
            changes = prices.pct_change().dropna()
            up_days_pct = (changes > 0).mean() if len(changes) > 0 else 0.5
            
            # Base features (last 40 days as proxy)
            base_prices = prices.iloc[-40:]
            base_length = len(base_prices) / 120  # Normalized
            base_range = (base_prices.max() - base_prices.min()) / base_prices.mean() if base_prices.mean() > 0 else 0
            
            # Volume trend in base
            if len(vols) >= 40:
                first_half = vols.iloc[-40:-20].mean()
                second_half = vols.iloc[-20:].mean()
                vol_trend = second_half / first_half - 1 if first_half > 0 else 0
            else:
                vol_trend = 0
            
            features = np.array([[
                close_to_ma20, close_to_ma50, close_to_ma200,
                trend_aligned, atr_14, vol_dryup, vol_compression,
                proximity_52w, return_3mo, up_days_pct,
                vol_trend, base_length, base_range, breakout_vol
            ]])
            
            prob = model.predict_proba(features)[0][1]
            scores[ticker] = prob
            
        except Exception:
            continue
    
    if not scores:
        return {}
    
    # Convert to percentiles
    tickers = list(scores.keys())
    raw = np.array([scores[t] for t in tickers])
    pctiles = rankdata(raw, method='average') / len(raw) * 99
    return {t: {'pctile': round(p, 1), 'prob': round(scores[t], 4)} for t, p in zip(tickers, pctiles)}


def get_rebalance_dates(close, start_year=2022):
    """Get month-end trading dates for rebalancing."""
    dates = close.index[close.index.year >= start_year]
    # Group by year-month, take last trading day
    monthly = dates.to_series().groupby([dates.year, dates.month]).last()
    # Drop last month (need forward returns)
    return monthly.values[:-1]


def measure_forward_returns(close, date, tickers, periods=[21, 63, 126]):
    """Measure forward returns from date for each ticker."""
    idx = close.index.get_indexer([date], method='ffill')[0]
    results = {}
    for days in periods:
        end_idx = min(idx + days, len(close) - 1)
        if end_idx <= idx:
            continue
        rets = []
        for t in tickers:
            if t in close.columns:
                start_price = close[t].iloc[idx]
                end_price = close[t].iloc[end_idx]
                if pd.notna(start_price) and pd.notna(end_price) and start_price > 0:
                    rets.append((end_price / start_price) - 1)
        if rets:
            results[f'{days}d'] = {
                'mean': round(np.mean(rets) * 100, 2),
                'median': round(np.median(rets) * 100, 2),
                'win_rate': round((np.array(rets) > 0).mean() * 100, 1),
                'n': len(rets)
            }
    return results


def run_walk_forward(close, volume, high, low):
    """Main walk-forward backtest loop."""
    
    # Load IQ Edge model
    model = None
    if os.path.exists(MODEL_FILE):
        with open(MODEL_FILE, 'rb') as f:
            model = pickle.load(f)
        print(f'   Loaded IQ Edge model from {MODEL_FILE}')
    
    rebal_dates = get_rebalance_dates(close, start_year=2022)
    print(f'   {len(rebal_dates)} rebalance dates ({rebal_dates[0].astype("datetime64[D]")} to {rebal_dates[-1].astype("datetime64[D]")})')
    
    # Storage for all periods
    ewros_results = {'top': [], 'bottom': [], 'spy': []}
    quality_results = {'top': [], 'bottom': []}
    rotation_results = {'high': [], 'low': []}
    iq_edge_results = {'top': [], 'bottom': []}
    power_zone_results = {'power': [], 'avoid': []}
    
    # For cumulative equity curves
    equity_curves = {
        'ewros_top': [], 'ewros_bottom': [], 'spy': [],
        'quality_top': [], 'quality_bottom': [],
        'power_zone': [], 'avoid_zone': [],
        'iq_edge_top': [], 'iq_edge_bottom': [],
        'dates': []
    }
    
    for i, date in enumerate(rebal_dates):
        date_str = str(date.astype('datetime64[D]'))
        pdate = pd.Timestamp(date)
        print(f'\r   Rebalancing {i+1}/{len(rebal_dates)}: {date_str}', end='', flush=True)
        
        # Compute all scores at this date
        ewros = compute_ewros_at_date(close, pdate)
        quality = compute_quality_proxy_at_date(close, volume, pdate)
        rotation = compute_rotation_proxy_at_date(close, volume, pdate)
        iq_edge = compute_iq_edge_at_date(close, volume, high, low, pdate, model) if model else {}
        
        if not ewros:
            continue
        
        # ---- EWROS portfolios ----
        sorted_ewros = sorted(ewros.items(), key=lambda x: -x[1])
        n = len(sorted_ewros)
        top_tickers = [t for t, _ in sorted_ewros[:n//10]]
        bottom_tickers = [t for t, _ in sorted_ewros[-n//10:]]
        
        top_fwd = measure_forward_returns(close, pdate, top_tickers)
        bottom_fwd = measure_forward_returns(close, pdate, bottom_tickers)
        spy_fwd = measure_forward_returns(close, pdate, ['SPY'])
        
        if '21d' in top_fwd:
            ewros_results['top'].append(top_fwd['21d']['mean'])
            ewros_results['bottom'].append(bottom_fwd.get('21d', {}).get('mean', 0))
            ewros_results['spy'].append(spy_fwd.get('21d', {}).get('mean', 0))
            equity_curves['ewros_top'].append(top_fwd['21d']['mean'])
            equity_curves['ewros_bottom'].append(bottom_fwd.get('21d', {}).get('mean', 0))
            equity_curves['spy'].append(spy_fwd.get('21d', {}).get('mean', 0))
            equity_curves['dates'].append(date_str)
        
        # ---- Quality portfolios ----
        if quality:
            sorted_quality = sorted(quality.items(), key=lambda x: -x[1])
            nq = len(sorted_quality)
            qtop = [t for t, _ in sorted_quality[:nq//10]]
            qbottom = [t for t, _ in sorted_quality[-nq//10:]]
            qtop_fwd = measure_forward_returns(close, pdate, qtop)
            qbottom_fwd = measure_forward_returns(close, pdate, qbottom)
            if '21d' in qtop_fwd:
                quality_results['top'].append(qtop_fwd['21d']['mean'])
                quality_results['bottom'].append(qbottom_fwd.get('21d', {}).get('mean', 0))
                equity_curves['quality_top'].append(qtop_fwd['21d']['mean'])
                equity_curves['quality_bottom'].append(qbottom_fwd.get('21d', {}).get('mean', 0))
        
        # ---- Rotation portfolios ----
        if rotation:
            high_rot = [t for t, s in rotation.items() if s >= 60]
            low_rot = [t for t, s in rotation.items() if s < 30]
            if high_rot and low_rot:
                hfwd = measure_forward_returns(close, pdate, high_rot)
                lfwd = measure_forward_returns(close, pdate, low_rot)
                if '21d' in hfwd:
                    rotation_results['high'].append(hfwd['21d']['mean'])
                    rotation_results['low'].append(lfwd.get('21d', {}).get('mean', 0))
        
        # ---- IQ Edge portfolios ----
        if iq_edge:
            sorted_iq = sorted(iq_edge.items(), key=lambda x: -x[1]['pctile'])
            ni = len(sorted_iq)
            itop = [t for t, _ in sorted_iq[:ni//10]]
            ibottom = [t for t, _ in sorted_iq[-ni//10:]]
            itop_fwd = measure_forward_returns(close, pdate, itop)
            ibottom_fwd = measure_forward_returns(close, pdate, ibottom)
            if '21d' in itop_fwd:
                iq_edge_results['top'].append(itop_fwd['21d']['mean'])
                iq_edge_results['bottom'].append(ibottom_fwd.get('21d', {}).get('mean', 0))
                equity_curves['iq_edge_top'].append(itop_fwd['21d']['mean'])
                equity_curves['iq_edge_bottom'].append(ibottom_fwd.get('21d', {}).get('mean', 0))
        
        # ---- Power Matrix ----
        if ewros and rotation:
            power = [t for t in ewros if ewros.get(t, 0) >= 70 and rotation.get(t, 0) >= 60]
            avoid = [t for t in ewros if ewros.get(t, 0) < 30 and rotation.get(t, 0) < 30]
            if power and avoid:
                pfwd = measure_forward_returns(close, pdate, power)
                afwd = measure_forward_returns(close, pdate, avoid)
                if '21d' in pfwd:
                    power_zone_results['power'].append(pfwd['21d']['mean'])
                    power_zone_results['avoid'].append(afwd.get('21d', {}).get('mean', 0))
                    equity_curves['power_zone'].append(pfwd['21d']['mean'])
                    equity_curves['avoid_zone'].append(afwd.get('21d', {}).get('mean', 0))
    
    print('\n')
    return ewros_results, quality_results, rotation_results, iq_edge_results, power_zone_results, equity_curves


def compute_stats(returns_list, label):
    """Compute aggregate stats from a list of period returns."""
    if not returns_list:
        return {'avg': 0, 'median': 0, 'win_rate': 0, 'n': 0, 'total': 0}
    arr = np.array(returns_list)
    return {
        'avg_monthly': round(np.mean(arr), 2),
        'median_monthly': round(np.median(arr), 2),
        'win_rate': round((arr > 0).mean() * 100, 1),
        'n_periods': len(arr),
        'cumulative': round(np.prod(1 + arr/100) * 100 - 100, 1),  # Compounded
        'best_month': round(np.max(arr), 2),
        'worst_month': round(np.min(arr), 2),
        'std': round(np.std(arr), 2),
    }


def plot_equity_curves(equity_curves):
    """Plot cumulative equity curves for main strategies."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    
    strategies = [
        ('EWROS: Top 10% vs Bottom 10% vs SPY', 
         [('ewros_top', 'Top 10%', '#0ea5e9'), ('ewros_bottom', 'Bottom 10%', '#ef4444'), ('spy', 'SPY', '#94a3b8')]),
        ('Quality: Top 10% vs Bottom 10%',
         [('quality_top', 'Top 10%', '#0ea5e9'), ('quality_bottom', 'Bottom 10%', '#ef4444')]),
        ('IQ Edge: Top 10% vs Bottom 10%',
         [('iq_edge_top', 'Top 10%', '#8b5cf6'), ('iq_edge_bottom', 'Bottom 10%', '#ef4444')]),
        ('Power Zone vs Avoid Zone',
         [('power_zone', 'Power Zone', '#10b981'), ('avoid_zone', 'Avoid', '#ef4444')]),
    ]
    
    for ax, (title, series_list) in zip(axes.flat, strategies):
        for key, label, color in series_list:
            data = equity_curves.get(key, [])
            if data:
                cumulative = np.cumprod(1 + np.array(data) / 100) * 100
                ax.plot(range(len(cumulative)), cumulative, label=label, color=color, linewidth=1.5)
        
        ax.set_title(title, fontweight='bold', fontsize=10)
        ax.set_ylabel('Growth of $100')
        ax.set_xlabel('Months')
        ax.legend(fontsize=8)
        ax.grid(True)
        ax.axhline(y=100, color='#94a3b8', linewidth=0.5, linestyle='--')
    
    plt.suptitle('Walk-Forward Backtest: Monthly Rebalanced Portfolios (2022-2026)', 
                 fontweight='bold', fontsize=13, y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'walk_forward_equity.png'), dpi=150, bbox_inches='tight')
    plt.close()


def plot_monthly_spreads(ewros_results, quality_results, iq_edge_results, power_zone_results):
    """Plot the monthly return spread (top minus bottom)."""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    strategies = [
        ('EWROS', ewros_results['top'], ewros_results['bottom'], '#0ea5e9'),
        ('Quality', quality_results['top'], quality_results['bottom'], '#10b981'),
        ('IQ Edge', iq_edge_results['top'], iq_edge_results['bottom'], '#8b5cf6'),
        ('Power Matrix', power_zone_results['power'], power_zone_results['avoid'], '#f59e0b'),
    ]
    
    spread_data = []
    labels = []
    colors_list = []
    
    for name, top, bottom, color in strategies:
        if top and bottom:
            min_len = min(len(top), len(bottom))
            spreads = [t - b for t, b in zip(top[:min_len], bottom[:min_len])]
            spread_data.append(spreads)
            labels.append(f'{name}\n(avg: {np.mean(spreads):.1f}%)')
            colors_list.append(color)
    
    bp = ax.boxplot(spread_data, labels=labels, patch_artist=True, widths=0.6)
    for patch, color in zip(bp['boxes'], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.3)
        patch.set_edgecolor(color)
    for median in bp['medians']:
        median.set_color('#1a1a1a')
        median.set_linewidth(2)
    
    ax.axhline(y=0, color='#ef4444', linewidth=1, linestyle='--', alpha=0.7)
    ax.set_ylabel('Monthly Spread: Top - Bottom (%)')
    ax.set_title('Signal Spread Distribution (Monthly, Walk-Forward)', fontweight='bold', fontsize=12)
    ax.grid(True, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'signal_spreads.png'), dpi=150)
    plt.close()


def plot_signal_summary(all_stats):
    """Bar chart of average monthly returns by strategy group."""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    groups = []
    top_vals = []
    bottom_vals = []
    spy_vals = []
    
    for name, stats in all_stats.items():
        if 'top' in stats and 'bottom' in stats:
            groups.append(name)
            top_vals.append(stats['top']['avg_monthly'])
            bottom_vals.append(stats['bottom']['avg_monthly'])
    
    x = np.arange(len(groups))
    width = 0.35
    
    ax.bar(x - width/2, top_vals, width, label='Top Decile / Power Zone', color='#0ea5e9', alpha=0.85)
    ax.bar(x + width/2, bottom_vals, width, label='Bottom Decile / Avoid', color='#ef4444', alpha=0.85)
    
    ax.set_ylabel('Avg Monthly Forward Return (%)')
    ax.set_title('Walk-Forward Results: Average Monthly Returns by Signal', fontweight='bold', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.legend()
    ax.grid(True, axis='y')
    ax.axhline(y=0, color='#94a3b8', linewidth=0.5)
    
    # Add value labels
    for i, (t, b) in enumerate(zip(top_vals, bottom_vals)):
        ax.text(i - width/2, t + 0.1, f'{t:.1f}%', ha='center', fontsize=8, fontweight='bold')
        ax.text(i + width/2, b - 0.3 if b < 0 else b + 0.1, f'{b:.1f}%', ha='center', fontsize=8, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'signal_summary.png'), dpi=150)
    plt.close()


def main():
    print('🚀 IQ Investor Walk-Forward Backtest')
    print(f'   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'   Method: Monthly rebalance, compute scores at each date, measure FORWARD returns\n')
    
    close, volume, high, low = load_data()
    
    ewros_res, quality_res, rotation_res, iq_edge_res, power_res, equity_curves = run_walk_forward(close, volume, high, low)
    
    # Compute stats
    all_stats = {}
    
    print('📈 EWROS Walk-Forward Results:')
    ewros_stats = {
        'top': compute_stats(ewros_res['top'], 'EWROS Top 10%'),
        'bottom': compute_stats(ewros_res['bottom'], 'EWROS Bottom 10%'),
        'spy': compute_stats(ewros_res['spy'], 'SPY'),
    }
    all_stats['EWROS'] = ewros_stats
    for k, v in ewros_stats.items():
        print(f'   {k}: avg={v["avg_monthly"]}%/mo, cumulative={v.get("cumulative", 0)}%, win={v["win_rate"]}%, n={v["n_periods"]}')
    
    print('\n📊 Quality Score Walk-Forward Results:')
    quality_stats = {
        'top': compute_stats(quality_res['top'], 'Quality Top 10%'),
        'bottom': compute_stats(quality_res['bottom'], 'Quality Bottom 10%'),
    }
    all_stats['Quality'] = quality_stats
    for k, v in quality_stats.items():
        print(f'   {k}: avg={v["avg_monthly"]}%/mo, cumulative={v.get("cumulative", 0)}%, win={v["win_rate"]}%')
    
    print('\n🔄 Rotation Walk-Forward Results:')
    rotation_stats = {
        'high': compute_stats(rotation_res['high'], 'High Rotation'),
        'low': compute_stats(rotation_res['low'], 'Low Rotation'),
    }
    all_stats['Rotation'] = {'top': rotation_stats['high'], 'bottom': rotation_stats['low']}
    for k, v in rotation_stats.items():
        print(f'   {k}: avg={v["avg_monthly"]}%/mo, cumulative={v.get("cumulative", 0)}%, win={v["win_rate"]}%')
    
    print('\n🧠 IQ Edge Walk-Forward Results:')
    iq_stats = {
        'top': compute_stats(iq_edge_res['top'], 'IQ Edge Top 10%'),
        'bottom': compute_stats(iq_edge_res['bottom'], 'IQ Edge Bottom 10%'),
    }
    all_stats['IQ Edge'] = iq_stats
    for k, v in iq_stats.items():
        print(f'   {k}: avg={v["avg_monthly"]}%/mo, cumulative={v.get("cumulative", 0)}%, win={v["win_rate"]}%')
    
    print('\n🎯 Power Matrix Walk-Forward Results:')
    power_stats = {
        'top': compute_stats(power_res['power'], 'Power Zone'),
        'bottom': compute_stats(power_res['avoid'], 'Avoid Zone'),
    }
    all_stats['Power Matrix'] = power_stats
    for k, v in power_stats.items():
        print(f'   {k}: avg={v["avg_monthly"]}%/mo, cumulative={v.get("cumulative", 0)}%, win={v["win_rate"]}%')
    
    # Generate charts
    print('\n📊 Generating charts...')
    plot_equity_curves(equity_curves)
    plot_monthly_spreads(ewros_res, quality_res, iq_edge_res, power_res)
    plot_signal_summary(all_stats)
    
    # Save results
    output = {
        'generated_at': datetime.now().isoformat(),
        'method': 'Walk-forward: monthly rebalance, scores computed at each date using only prior data, forward returns measured',
        'data_range': f'{close.index[0].date()} to {close.index[-1].date()}',
        'backtest_range': f'{equity_curves["dates"][0] if equity_curves["dates"] else "N/A"} to {equity_curves["dates"][-1] if equity_curves["dates"] else "N/A"}',
        'rebalance_periods': len(equity_curves['dates']),
        'total_stocks': len(close.columns),
        'stats': {},
    }
    
    for name, stats in all_stats.items():
        output['stats'][name] = stats
    
    output['equity_curves'] = equity_curves
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f'\n✅ Walk-forward backtest complete!')
    print(f'   Results: {OUTPUT_FILE}')
    print(f'   Charts: {CHARTS_DIR}/')


if __name__ == '__main__':
    main()

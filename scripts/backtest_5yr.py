#!/usr/bin/env python3
"""
5-Year OOS Backtest — Train 2016-2020, Test 2021-2026
All signals are pure price + volume. No look-ahead bias.

Step 1: Precompute EWROS + IQ Edge scores weekly (cached to disk)
Step 2: Run portfolio simulation using cached signals
"""
import pickle, os, json, warnings, numpy as np, pandas as pd
from scipy.stats import rankdata
from datetime import timedelta
from collections import defaultdict, namedtuple
warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
MODEL_DIR = os.path.join(ROOT, 'models')

# ── Parameters ──────────────────────────────────────────────────────────────
MAX_POSITIONS   = 10
STOP_LOSS       = -0.08
MAX_HOLD_DAYS   = 126
EWROS_LOOKBACK  = 63
EWROS_LAMBDA    = 0.03
EWROS_EXIT      = 50
SIGNAL_FREQ     = 5        # recompute signals every N trading days
OOS_START       = pd.Timestamp('2021-06-15')

FEATURE_COLS = [
    'close_to_ma20','close_to_ma50','close_to_ma200','trend_aligned',
    'atr_14','vol_dryup_ratio','vol_compression','proximity_52w',
    'return_3mo','up_days_pct','vol_trend_in_base','base_length',
    'base_range','breakout_vol_ratio'
]

# ── Data ─────────────────────────────────────────────────────────────────────
print('📊 Loading 10yr OHLCV...')
ohlcv = pd.read_parquet(os.path.join(DATA_DIR, 'historical_ohlcv_10yr.parquet'))
ohlcv['date'] = pd.to_datetime(ohlcv['date'])
close  = ohlcv.pivot_table(index='date', columns='ticker', values='close')
volume = ohlcv.pivot_table(index='date', columns='ticker', values='volume')
high   = ohlcv.pivot_table(index='date', columns='ticker', values='high')
low    = ohlcv.pivot_table(index='date', columns='ticker', values='low')
print(f'   {close.shape[1]} tickers, {close.shape[0]} days ({close.index[0].date()} → {close.index[-1].date()})')

with open(os.path.join(MODEL_DIR, 'breakout_xgb_10yr.pkl'), 'rb') as f:
    model = pickle.load(f)
print('   Loaded model: breakout_xgb_10yr.pkl (trained on 2016-2020)')

spy = close['SPY']
non_spy = [c for c in close.columns if c != 'SPY']

# Index range for OOS test
oos_start_idx = close.index.get_indexer([OOS_START], method='ffill')[0]
oos_dates     = close.index[oos_start_idx:]
total_days    = len(oos_dates)

# ── Step 1: Precompute signals ────────────────────────────────────────────────
CACHE_FILE = os.path.join(DATA_DIR, 'signals_5yr_cache.pkl')

if os.path.exists(CACHE_FILE):
    print(f'\n⚡ Loading cached signals from {CACHE_FILE}...')
    with open(CACHE_FILE, 'rb') as f:
        signal_cache = pickle.load(f)
    print(f'   {len(signal_cache)} signal snapshots loaded')
else:
    print(f'\n🔢 Precomputing signals every {SIGNAL_FREQ} days over {total_days} OOS days...')
    signal_cache = {}   # date_idx → {'ewros': {ticker: score}, 'iq': {ticker: pctile}}

    stock_rets = close.pct_change()
    spy_ret    = stock_rets['SPY']

    signal_dates = range(oos_start_idx, len(close), SIGNAL_FREQ)
    for i, idx in enumerate(signal_dates):
        date = close.index[idx]
        if (i+1) % 20 == 0:
            print(f'   {i+1}/{len(list(signal_dates))} — {date.date()}')

        # ── EWROS ──
        lo = max(0, idx - EWROS_LOOKBACK)
        w  = np.array([np.exp(-EWROS_LAMBDA * j)
                       for j in range(idx - lo, -1, -1)], dtype=float)
        raw_ewros = {}
        for t in non_spy:
            sr = stock_rets[t].values[lo:idx+1]
            sp = spy_ret.values[lo:idx+1]
            m  = ~(np.isnan(sr) | np.isnan(sp))
            wm = w[m] if len(w) == len(sr) else w[:m.sum()]
            if m.sum() < EWROS_LOOKBACK * 0.5: continue
            sr_m, sp_m, wm = sr[m], sp[m], w[m] if len(w) == len(sr) else w[:m.sum()]
            # recompute aligned weights
            valid_w = np.array([np.exp(-EWROS_LAMBDA * j)
                                for j in range(m.sum()-1, -1, -1)], dtype=float)
            raw_ewros[t] = ((sr_m - sp_m) * valid_w).sum()

        if raw_ewros:
            tks = list(raw_ewros.keys())
            vals = np.array([raw_ewros[t] for t in tks])
            pcts = rankdata(vals, method='average') / len(vals) * 99
            ewros_scores = {t: round(p, 1) for t, p in zip(tks, pcts)}
        else:
            ewros_scores = {}

        # ── IQ Edge ──
        iq_scores = {}
        for t in non_spy:
            prices = close[t].iloc[max(0, idx-252):idx+1].dropna()
            vols   = volume[t].iloc[max(0, idx-252):idx+1].dropna()
            highs  = high[t].iloc[max(0, idx-252):idx+1].dropna()
            lows   = low[t].iloc[max(0, idx-252):idx+1].dropna()
            if len(prices) < 60 or len(vols) < 50: continue
            try:
                c    = prices.iloc[-1]
                ma20 = prices.iloc[-20:].mean()
                ma50 = prices.iloc[-50:].mean()
                ma200= prices.mean() if len(prices)<200 else prices.iloc[-200:].mean()
                ta   = 1.0 if (c > ma50 > ma200) else 0.0
                if len(highs)>=15 and len(lows)>=15:
                    tr = np.maximum(highs.iloc[-15:].values - lows.iloc[-15:].values,
                         np.maximum(abs(highs.iloc[-15:].values - prices.iloc[-16:-1].values),
                                    abs(lows.iloc[-15:].values  - prices.iloc[-16:-1].values)))
                    atr = np.mean(tr[-14:]) / c if c > 0 else 0.02
                else: atr = 0.02
                vd  = vols.iloc[-10:].mean() / vols.iloc[-50:-10].mean()
                bv  = vols.iloc[-1]           / vols.iloc[-50:].mean()
                vc  = prices.iloc[-10:].pct_change().std() / prices.iloc[-40:].pct_change().std() if len(prices)>=40 else 1
                p52 = c / prices.max()
                r3m = (c / prices.iloc[-63] - 1) if len(prices)>=63 else 0
                up  = (prices.pct_change().dropna() > 0).mean()
                bp  = prices.iloc[-40:]
                bl  = len(bp) / 120
                br  = (bp.max()-bp.min())/bp.mean() if bp.mean()>0 else 0
                vt  = vols.iloc[-20:].mean() / vols.iloc[-40:-20].mean() - 1 if len(vols)>=40 else 0
                feats = np.nan_to_num([[c/ma20-1, c/ma50-1, c/ma200-1, ta, atr,
                                        vd, vc, p52, r3m, up, vt, bl, br, bv]])
                iq_scores[t] = model.predict_proba(feats)[0][1]
            except: continue

        if iq_scores:
            tks  = list(iq_scores.keys())
            vals = np.array([iq_scores[t] for t in tks])
            pcts = rankdata(vals, method='average') / len(vals) * 99
            iq_pct = {t: {'pctile': round(p,1), 'prob': round(iq_scores[t],4)}
                      for t, p in zip(tks, pcts)}
        else:
            iq_pct = {}

        signal_cache[idx] = {'ewros': ewros_scores, 'iq': iq_pct, 'date': date}

    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(signal_cache, f)
    print(f'   ✅ Cached {len(signal_cache)} snapshots → {CACHE_FILE}')

# ── Step 2: Portfolio simulation ──────────────────────────────────────────────
print(f'\n🚀 Running portfolio simulation...')

def get_signals(idx):
    """Get nearest cached signal at or before idx"""
    # Find closest cache entry ≤ idx
    keys = [k for k in signal_cache if k <= idx]
    if not keys: return {}, {}
    best = max(keys)
    snap = signal_cache[best]
    return snap['ewros'], snap['iq']

def is_trend_aligned(idx, ticker):
    if idx < 200: return False
    p = close[ticker].values[max(0,idx-199):idx+1]
    p = p[~np.isnan(p)]
    if len(p) < 50: return False
    c = p[-1]; ma50 = p[-50:].mean(); ma200 = p.mean()
    return c > ma50 > ma200

def get_ma50(idx, ticker):
    p = close[ticker].values[max(0,idx-49):idx+1]
    p = p[~np.isnan(p)]
    return p.mean() if len(p) >= 30 else None

Position = namedtuple('Position', ['ticker','shares','entry_price','entry_idx','entry_date','cost_basis'])

def run_strategy(name, entry_fn):
    cash       = 10_000.0
    positions  = {}   # ticker → Position
    closed     = []
    slot_size  = 10_000.0 / MAX_POSITIONS

    port_values = []
    port_dates  = []

    print(f'\n  ▶ {name}')

    for day_offset in range(total_days):
        idx  = oos_start_idx + day_offset
        date = close.index[idx]
        ewros, iq = get_signals(idx)

        # ── Exit checks ──
        to_close = []
        for ticker, pos in positions.items():
            price = close[ticker].values[idx]
            if np.isnan(price): continue
            ret       = price / pos.entry_price - 1
            hold_days = (date - pos.entry_date).days
            ma50      = get_ma50(idx, ticker)
            ew        = ewros.get(ticker, 99)

            exit_r = None
            if ret <= STOP_LOSS:                                     exit_r = 'stop_loss'
            elif hold_days >= 5 and ma50 and price < ma50:          exit_r = 'below_ma50'
            elif hold_days >= 10 and ew < EWROS_EXIT:               exit_r = 'ewros_drop'
            elif hold_days >= MAX_HOLD_DAYS:                        exit_r = 'max_hold'

            if exit_r:
                proceeds = pos.shares * price
                pnl_pct  = round(ret * 100, 2)
                pnl_usd  = proceeds - pos.cost_basis
                cash    += proceeds
                closed.append({
                    'ticker': ticker, 'entry_date': pos.entry_date, 'exit_date': date,
                    'hold_days': hold_days, 'pnl_pct': pnl_pct, 'pnl_dollar': pnl_usd,
                    'exit': exit_r
                })
                to_close.append(ticker)

        for t in to_close:
            del positions[t]

        # ── Entry signals (only on signal days) ──
        if idx in signal_cache:
            candidates = entry_fn(idx, ewros, iq)
            for ticker, score, ew in candidates:
                if len(positions) >= MAX_POSITIONS: break
                if ticker in positions: continue
                price = close[ticker].values[idx]
                if np.isnan(price) or price <= 0: continue
                if cash < slot_size * 0.5: break
                invest = min(slot_size, cash)
                shares = invest / price
                cash  -= invest
                positions[ticker] = Position(ticker, shares, price, idx, date, invest)

        # ── Portfolio value ──
        invested = sum(
            pos.shares * (close[ticker].values[idx] if not np.isnan(close[ticker].values[idx]) else pos.entry_price)
            for ticker, pos in positions.items()
        )
        port_values.append(cash + invested)
        port_dates.append(date)

    # Close remaining
    final_idx = oos_start_idx + total_days - 1
    final_date = close.index[final_idx]
    for ticker, pos in positions.items():
        price = close[ticker].values[final_idx]
        if np.isnan(price): price = pos.entry_price
        proceeds = pos.shares * price
        pnl_usd = proceeds - pos.cost_basis
        cash += proceeds
        closed.append({'ticker': ticker, 'entry_date': pos.entry_date, 'exit_date': final_date,
                       'hold_days': (final_date - pos.entry_date).days,
                       'pnl_pct': round((price/pos.entry_price-1)*100, 2),
                       'pnl_dollar': pnl_usd, 'exit': 'end_of_data'})

    final_val = cash
    total_pnl = final_val - 10_000
    wins  = [t for t in closed if t['pnl_pct'] > 0]
    loss  = [t for t in closed if t['pnl_pct'] <= 0]
    gp    = sum(t['pnl_dollar'] for t in wins)
    gl    = abs(sum(t['pnl_dollar'] for t in loss))
    pf    = gp / gl if gl > 0 else 99
    wr    = len(wins) / len(closed) * 100 if closed else 0
    exp   = np.mean([t['pnl_pct'] for t in closed]) if closed else 0

    print(f'     ${10000:,.0f} → ${final_val:,.0f} ({total_pnl/10000*100:+.1f}%)')
    print(f'     Trades: {len(closed)} ({len(wins)}W/{len(loss)}L) · WR {wr:.0f}% · PF {pf:.2f} · Exp {exp:+.1f}%')
    if wins:  print(f'     Avg win:  +{np.mean([t["pnl_pct"] for t in wins]):.1f}%')
    if loss:  print(f'     Avg loss:  {np.mean([t["pnl_pct"] for t in loss]):.1f}%')

    # Yearly
    by_year = defaultdict(list)
    for t in closed: by_year[t['entry_date'].year].append(t)
    print(f'     YEARLY:')
    for yr in sorted(by_year.keys()):
        tyr  = by_year[yr]
        w    = sum(1 for t in tyr if t['pnl_pct'] > 0)
        pnl  = sum(t['pnl_dollar'] for t in tyr)
        print(f'       {yr}: {len(tyr):3d} trades · WR {w/len(tyr)*100:.0f}% · P&L ${pnl:+,.0f}')

    # Concentration
    sorted_t = sorted(closed, key=lambda x: -x['pnl_dollar'])
    top5_pnl = sum(t['pnl_dollar'] for t in sorted_t[:5])
    rest_pnl = total_pnl - top5_pnl
    print(f'     Top 5 trades: ${top5_pnl:+,.0f} ({top5_pnl/total_pnl*100:.0f}%)  Rest: ${rest_pnl:+,.0f} {"✅" if rest_pnl > 0 else "❌"}')

    # vs SPY monthly beat rate
    spy_s = spy.iloc[oos_start_idx]
    beat  = sum(1 for v, d in zip(port_values, port_dates)
                if v > 10000 * spy.iloc[close.index.get_indexer([d], method='ffill')[0]] / spy_s)
    print(f'     Beat SPY: {beat}/{total_days} days ({beat/total_days*100:.0f}%)')

    return final_val, port_values, port_dates, closed


# ── Strategy definitions ──────────────────────────────────────────────────────
def strat_ewros(idx, ewros, iq):
    top = sorted(ewros.items(), key=lambda x: -x[1])[:MAX_POSITIONS]
    return [(t, s, s) for t, s in top if is_trend_aligned(idx, t)]

def strat_combo(idx, ewros, iq):
    cands = []
    for t, d in iq.items():
        if d['pctile'] < 80: continue
        if ewros.get(t, 0) < 80: continue
        if not is_trend_aligned(idx, t): continue
        cands.append((t, (d['pctile'] + ewros[t]) / 2, ewros[t]))
    cands.sort(key=lambda x: -x[1])
    return cands[:MAX_POSITIONS]


spy_final = 10000 * spy.iloc[-1] / spy.iloc[oos_start_idx]

print(f'\n{"="*65}')
print(f'  5-YEAR OOS: Jun 2021 → Mar 2026  (model trained 2016-2020)')
print(f'  SPY Buy & Hold: $10,000 → ${spy_final:,.0f} ({(spy_final/10000-1)*100:+.1f}%)')
print(f'{"="*65}')

final_ewros, _, _, _  = run_strategy('EWROS Top 10 + Trend', strat_ewros)
final_combo, _, _, _  = run_strategy('IQ Edge + EWROS ≥80', strat_combo)

print(f'\n{"="*65}')
print(f'  FINAL SCORECARD ($10K, Jun 2021 → Mar 2026)')
print(f'{"="*65}')
print(f'  IQ Edge + EWROS ≥80   → ${final_combo:>9,.0f} ({(final_combo/10000-1)*100:+.1f}%)')
print(f'  EWROS Top 10 + Trend  → ${final_ewros:>9,.0f} ({(final_ewros/10000-1)*100:+.1f}%)')
print(f'  SPY Buy & Hold        → ${spy_final:>9,.0f} ({(spy_final/10000-1)*100:+.1f}%)')

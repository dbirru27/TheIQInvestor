#!/usr/bin/env python3
import sys
sys.path.append('.')
from rater import BreakoutRater
import yfinance as yf

rater = BreakoutRater()

# GE Style Watchlist - Quality Industrials, Defense, Financials, Materials
ge_style_stocks = [
    'GE', 'GEV', 'PWR', 'VRT', 'CAT', 'DE', 'URI', 'LHX', 'LMT', 'NOC', 'RTX', 'GD',
    'JPM', 'GS', 'MS', 'BLK', 'BX', 'KKR', 'TROW', 'MSCI', 'SPGI',
    'MLM', 'VMC', 'NUE', 'STLD', 'FCX', 'LIN', 'SHW',
    'O', 'PLD', 'UNH', 'LLY'
]

holdings = ['PANW','ISRG','ORCL','CRM','PLTR','NOW','AMZN','TSLA','GE','CRWD','MSFT','TMUS','JPM','NFLX','UNH','UBER','BRK-B','HD','MRVL','ANET','WDC','AMD','MU','AVGO','TSM','STX','ASML','META','LRCX','AMAT','NVDA','CAT','GOOGL','LLY','V']

print('='*60)
print('GE STYLE SCAN - Quality Growth / Industrial Leaders')
print('Benchmark: GE Aerospace | Time: Feb 6, 2026 5:00 AM PT')
print('='*60)

results = []
for ticker in ge_style_stocks[:15]:
    try:
        data = rater.rate_stock(ticker)
        if 'error' not in data and data['score'] > 0:
            results.append(data)
    except Exception as e:
        pass

# Sort by score
results.sort(key=lambda x: x['score'], reverse=True)

print()
print('TOP 5 GE STYLE PICKS:')
print('-'*60)
for i, r in enumerate(results[:5]):
    in_pf = '★ HOLDING' if r['ticker'] in holdings else ''
    print(f"{i+1}. {r['ticker']:<6} {r['grade']:<3} ({r['score']}/100)  {r['name'][:35]:<35} {in_pf}")

# Top pick detailed report
if results:
    top = results[0]
    print()
    print('='*60)
    print(f"TERMINAL REPORT: {top['ticker']} - {top['name']}")
    print('='*60)
    
    stock = yf.Ticker(top['ticker'])
    hist = stock.history(period='3mo')
    info = stock.info
    
    current = hist['Close'].iloc[-1]
    sma50 = hist['Close'].rolling(50).mean().iloc[-1]
    high52 = hist['High'].rolling(252).max() if len(hist) >= 100 else hist['High'].max()
    
    vol5 = hist['Volume'].tail(5).mean()
    vol20 = hist['Volume'].tail(20).mean()
    rvol = vol5 / vol20 if vol20 > 0 else 0
    
    print(f"[PRICE ACTION]")
    print(f"  Price:      ${current:.2f}")
    print(f"  50d MA:     ${sma50:.2f} ({((current/sma50-1)*100):+.1f}%)")
    print(f"  vs 52W Hi:  {((current/high52.iloc[-1]-1)*100):+.1f}%" if hasattr(high52, 'iloc') else f"  vs 52W Hi:  {((current/high52-1)*100):+.1f}%")
    print(f"  RVOL:       {rvol:.2f}x avg")
    print()
    print(f"[FUNDAMENTALS]")
    pe = info.get('forwardPE', 'N/A')
    peg = info.get('pegRatio', 'N/A')  
    rev = info.get('revenueGrowth')
    opm = info.get('operatingMargins')
    print(f"  Forward P/E:  {pe:.1f}" if isinstance(pe, (int, float)) else f"  Forward P/E:  {pe}")
    print(f"  PEG Ratio:    {peg:.2f}" if isinstance(peg, (int, float)) else f"  PEG Ratio:    {peg}")
    print(f"  Rev Growth:   {rev*100:.1f}%" if rev else '  Rev Growth:   N/A')
    print(f"  Op Margin:    {opm*100:.1f}%" if opm else '  Op Margin:    N/A')
    print()
    print(f"[ANALYST CONSENSUS]")
    print(f"  Rating:       {str(info.get('recommendationKey', 'N/A')).replace('_', ' ').title()}")
    tgt = info.get('targetMeanPrice')
    print(f"  Price Target: ${tgt:.2f}" if tgt else '  Price Target: N/A')
    print(f"  Analysts:     {info.get('numberOfAnalystOpinions', 'N/A')}")
    print()
    print(f"[CRITERIA SCORECARD - {top['ticker']}]")
    for c in top['results']:
        status = '✓' if c['passed'] else '✗'
        pts = c['points'] if c['passed'] else 0
        print(f"  {status} {c['name']:<18} {c['value']:<16} (+{pts} pts)")

#!/usr/bin/env python3
"""
InvestIQ Distribution Scanner v1.0
Detects institutional selling (distribution) patterns:
1. Churn (High Vol, Low Progress)
2. Heavy Selling Days (Big Red Bars on Volume)
3. Upthrusts (Bull Traps)
4. Weak Rallies (Low Volume Buying)
"""
import yfinance as yf
import pandas as pd
import sys
import datetime
import config
from utils.logger import get_logger

logger = get_logger('distribution_scan')

# Configuration
LOOKBACK_DAYS = 30  # Analyze last 30 trading days
DISTRIBUTION_THRESHOLD = 3  # Alert if >= 3 signals in window

# Tickers to Scan - use config for portfolio and indices
TICKERS = config.MARKET_INDICES + config.PORTFOLIO_TICKERS + config.CORE_ETFS

def analyze_distribution(ticker_symbol):
    try:
        # Fetch data
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="3mo") # Get enough data for averages
        
        if len(hist) < 50:
            return None

        # Calculate metrics
        hist['PriceChangePct'] = (hist['Close'] - hist['Open']) / hist['Open'] * 100
        hist['DailyRange'] = hist['High'] - hist['Low']
        hist['CloseLoc'] = (hist['Close'] - hist['Low']) / hist['DailyRange']
        hist['VolAvg20'] = hist['Volume'].rolling(20).mean()
        
        # Analyze last N days
        recent = hist.tail(LOOKBACK_DAYS).copy()
        signals = []
        
        churn_days = 0
        heavy_sell_days = 0
        upthrust_days = 0
        weak_rally_days = 0
        
        for date, row in recent.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            vol_ratio = row['Volume'] / row['VolAvg20'] if row['VolAvg20'] > 0 else 0
            
            # 1. Churn (High Vol, Low Progress)
            # Vol > 1.5x avg AND Price Move < 0.5% (absolute)
            if vol_ratio > 1.5 and abs(row['PriceChangePct']) < 0.5:
                churn_days += 1
                signals.append(f"⚠️ {date_str}: Churn (Vol {vol_ratio:.1f}x, Move {row['PriceChangePct']:.2f}%)")
                
            # 2. Heavy Selling (Institutional Exit)
            # Drop > 1.5% on > 1.2x Vol
            if row['PriceChangePct'] < -1.5 and vol_ratio > 1.2:
                heavy_sell_days += 1
                signals.append(f"🔴 {date_str}: Heavy Selling (Drop {row['PriceChangePct']:.1f}%, Vol {vol_ratio:.1f}x)")
                
            # 3. Upthrust (Bull Trap)
            # Intraday High > Prev High (approx check) but Close in bottom 40% of range
            if row['CloseLoc'] < 0.4 and row['PriceChangePct'] > 0 and vol_ratio > 1.0:
                 # Simplified check: Green open-to-close but finished low in range on volume
                 upthrust_days += 1
                 signals.append(f"🪤 {date_str}: Upthrust/Trap (Closed Low {row['CloseLoc']:.2f}, Vol {vol_ratio:.1f}x)")

            # 4. Weak Rally (No Demand)
            # Price Up > 1% on < 0.8x Vol
            if row['PriceChangePct'] > 1.0 and vol_ratio < 0.8:
                weak_rally_days += 1
                signals.append(f"☁️ {date_str}: Weak Rally (Up {row['PriceChangePct']:.1f}%, Vol {vol_ratio:.1f}x)")

        total_signals = churn_days + heavy_sell_days + upthrust_days
        
        return {
            'ticker': ticker_symbol,
            'signals': signals,
            'counts': {
                'churn': churn_days,
                'heavy_sell': heavy_sell_days,
                'upthrust': upthrust_days,
                'weak_rally': weak_rally_days,
                'total_distribution': total_signals
            },
            'price': recent['Close'].iloc[-1]
        }

    except Exception as e:
        return None

def main():
    logger.info(f"🔎 InvestIQ Distribution Scanner")
    logger.info(f"   Analyzing last {LOOKBACK_DAYS} days for institutional selling...")
    logger.info("-" * 60)
    
    alerts = []
    
    for ticker in TICKERS:
        logger.debug(f"Scanning {ticker}...")
        
        result = analyze_distribution(ticker)
        if result and result['counts']['total_distribution'] >= DISTRIBUTION_THRESHOLD:
            alerts.append(result)
            
    logger.info(f"Scanning Complete.")
    
    if not alerts:
        print("✅ No significant distribution detected in monitored list.")
        return

    print(f"🚨 DISTRIBUTION ALERT: {len(alerts)} Tickers Showing Institutional Selling\n")
    
    # Sort by total distribution signals (descending)
    alerts.sort(key=lambda x: x['counts']['total_distribution'], reverse=True)
    
    for a in alerts:
        counts = a['counts']
        print(f"█ {a['ticker']} (${a['price']:.2f}) - {counts['total_distribution']} Signals")
        print(f"   🔴 Heavy Sell: {counts['heavy_sell']} | ⚠️ Churn: {counts['churn']} | 🪤 Traps: {counts['upthrust']}")
        
        # Show last 3 signals detail
        print("   Recent Activity:")
        for sig in a['signals'][-3:]:
            print(f"     {sig}")
        print("")

if __name__ == "__main__":
    main()

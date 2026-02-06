import sys
import os
from market_data import MarketDB

# Add path for existing logic
sys.path.append(os.getcwd())
try:
    from invest_iq.app import InvestIQEngine
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), "invest_iq"))
    from app import InvestIQEngine

# Define Baskets manually for grouping
BASKETS = {
    "🛡️ DEFENSE": ["LHX", "LMT", "NOC", "GE"],
    "⚡ GRID-TO-CHIP": ["PWR", "VRT", "GEV"],
    "🤖 TECH / TOP VOO": ["MSFT", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "NVDA", "AMD", "AVGO", "LRCX", "AMAT", "PLTR", "CRM", "NOW", "ORCL", "UBER", "PANW", "CRWD", "CDNS", "SNPS", "ANET", "MRVL", "TSM", "ASML", "WDC"],
    "🏥 HEALTH / CONSUMER": ["LLY", "UNH", "ISRG", "DXCM", "V", "MA", "HD", "MCD", "NFLX", "TMUS", "JPM", "BRK-B", "COST", "CAT"]
}

def rate_fundamentals():
    # Flatten list for rating
    all_tickers = []
    for t_list in BASKETS.values():
        all_tickers.extend(t_list)
    all_tickers = list(set(all_tickers)) # Dedupe

    results = {}
    print(f"Analyzing Fundamentals for {len(all_tickers)} stocks...")
    
    for t in all_tickers:
        try:
            data = InvestIQEngine.get_rating(t)
            # Scale Quality to 100 (Quality is normally out of 50)
            q_score = data['quality_score'] * 2 
            results[t] = q_score
        except:
            results[t] = 0

    print("\n[ 📊 FUNDAMENTAL QUALITY RANKINGS ]")
    print("(Based on Margins, FCF, Debt, and Earnings/Sales Growth)")
    
    for basket, tickers in BASKETS.items():
        print(f"\n{basket}")
        print(f"{'TICKER':<8} {'QUAL':<6} {'STATUS'}")
        print("─────────────────────────────")
        
        # Sort tickers in this basket by score
        basket_res = [(t, results.get(t, 0)) for t in tickers if t in results]
        basket_res.sort(key=lambda x: x[1], reverse=True)
        
        for t, score in basket_res:
            status = "💎 Elite" if score >= 90 else \
                     "✅ Strong" if score >= 70 else \
                     "⚠️ Mixed" if score >= 50 else \
                     "❌ Weak"
            print(f"{t:<8} {score:<6} {status}")

if __name__ == "__main__":
    rate_fundamentals()

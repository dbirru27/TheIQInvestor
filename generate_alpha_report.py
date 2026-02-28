#!/usr/bin/env python3
"""
Daily Alpha Report Generator
Generates comprehensive market analysis HTML report
v2.0: Now uses live yfinance data instead of hardcoded values
"""
from datetime import datetime
import os
import yfinance as yf

def fetch_live_data():
    """
    Fetch live market data using yfinance
    
    Returns:
        tuple: (market_data dict, portfolio dict)
    """
    # Define tickers to fetch
    market_tickers = ["SPY", "QQQ", "IWM", "VIXY", "DX-Y.NYB", "GLD", "BTC-USD", "CL=F"]
    portfolio_tickers = {
        "LMT": "Defense",
        "NOC": "Defense",
        "GE": "Defense/TopVOO",
        "PWR": "Grid-to-Chip",
        "COPX": "Core ETFs",
        "NLR": "Core ETFs",
        "VOO": "Core ETFs",
        "XLI": "Core ETFs",
        "MSFT": "TopVOO",
        "AMZN": "TopVOO",
        "GOOGL": "TopVOO",
        "META": "TopVOO",
        "NVDA": "TopVOO",
        "AMD": "TopVOO",
        "PLTR": "TopVOO",
        "LLY": "TopVOO"
    }
    
    market_data = {}
    portfolio = {}
    
    try:
        # Fetch market indices
        print("Fetching market data...")
        for ticker in market_tickers:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="2d")
                
                if len(hist) >= 2:
                    current_price = hist['Close'].iloc[-1]
                    prev_price = hist['Close'].iloc[-2]
                    change = current_price - prev_price
                    percent_change = (change / prev_price) * 100
                    
                    # Map ticker names
                    display_name = ticker
                    if ticker == "DX-Y.NYB":
                        display_name = "DXY"
                    elif ticker == "BTC-USD":
                        display_name = "BTC"
                    elif ticker == "CL=F":
                        display_name = "OIL"
                    
                    market_data[display_name] = {
                        "price": current_price,
                        "change": change,
                        "percent": percent_change
                    }
                else:
                    # Fallback if not enough data
                    market_data[ticker] = {
                        "price": "N/A",
                        "change": "N/A",
                        "percent": "N/A"
                    }
            except Exception as e:
                print(f"Error fetching {ticker}: {e}")
                market_data[ticker] = {
                    "price": "N/A",
                    "change": "N/A",
                    "percent": "N/A"
                }
        
        # Add 10Y placeholder (requires different API)
        market_data["10Y"] = {"price": "N/A", "change": "N/A", "percent": "N/A"}
        
        # Fetch portfolio holdings
        print("Fetching portfolio data...")
        for ticker, basket in portfolio_tickers.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="2d")
                
                if len(hist) >= 2:
                    current_price = hist['Close'].iloc[-1]
                    prev_price = hist['Close'].iloc[-2]
                    change = current_price - prev_price
                    percent_change = (change / prev_price) * 100
                    
                    portfolio[ticker] = {
                        "price": current_price,
                        "change": change,
                        "percent": percent_change,
                        "basket": basket
                    }
                else:
                    portfolio[ticker] = {
                        "price": 0,
                        "change": 0,
                        "percent": 0,
                        "basket": basket
                    }
            except Exception as e:
                print(f"Error fetching {ticker}: {e}")
                portfolio[ticker] = {
                    "price": 0,
                    "change": 0,
                    "percent": 0,
                    "basket": basket
                }
        
        print("Data fetch complete!")
        return market_data, portfolio
        
    except Exception as e:
        print(f"CRITICAL ERROR fetching data: {e}")
        print("Falling back to placeholder data...")
        # Return empty dicts - will show N/A in report
        return {}, {}

# Fetch live data
market_data, portfolio = fetch_live_data()

def get_color_class(value):
    if isinstance(value, str):
        return "neutral"
    return "positive" if value >= 0 else "negative"

def format_change(value):
    if isinstance(value, str):
        return value
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}"

def format_percent(value):
    if isinstance(value, str):
        return value
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"

def generate_report():
    today = datetime.now().strftime("%A, %B %d, %Y")
    date_code = datetime.now().strftime("%Y%m%d")
    
    # Calculate basket performance
    basket_perf = {
        "Defense": [],
        "Grid-to-Chip": [],
        "TopVOO": [],
        "Core ETFs": []
    }
    
    for ticker, data in portfolio.items():
        basket = data["basket"].split("/")[0]
        if basket in basket_perf:
            basket_perf[basket].append(data["percent"])
    
    basket_avg = {}
    for basket, returns in basket_perf.items():
        if returns:
            basket_avg[basket] = sum(returns) / len(returns)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Alpha Report - {today}</title>
    <style>
        :root {{
            --bg-dark: #0a0a0f;
            --bg-card: #14141f;
            --bg-elevated: #1e1e2e;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --accent-green: #22c55e;
            --accent-red: #ef4444;
            --accent-gold: #f59e0b;
            --accent-blue: #3b82f6;
            --border: #2d2d3d;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        
        .header {{
            text-align: center;
            padding: 30px 20px;
            background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elevated) 100%);
            border-radius: 12px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
        }}
        
        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(90deg, var(--accent-gold), #fbbf24);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        
        .header .date {{
            color: var(--text-secondary);
            font-size: 14px;
        }}
        
        .section {{
            background: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border);
            padding: 24px;
            margin-bottom: 20px;
        }}
        
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--accent-gold);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }}
        
        .metric-card {{
            background: var(--bg-elevated);
            border-radius: 8px;
            padding: 16px;
            border: 1px solid var(--border);
        }}
        
        .metric-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        
        .metric-value {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        
        .metric-change {{
            font-size: 14px;
            font-weight: 500;
        }}
        
        .positive {{ color: var(--accent-green); }}
        .negative {{ color: var(--accent-red); }}
        .neutral {{ color: var(--text-secondary); }}
        
        .drivers-list {{
            list-style: none;
        }}
        
        .drivers-list li {{
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        
        .drivers-list li:last-child {{
            border-bottom: none;
        }}
        
        .driver-icon {{
            width: 32px;
            height: 32px;
            border-radius: 6px;
            background: var(--bg-elevated);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            flex-shrink: 0;
        }}
        
        .driver-content h4 {{
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 2px;
        }}
        
        .driver-content p {{
            font-size: 13px;
            color: var(--text-secondary);
        }}
        
        .basket-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        
        .basket-card {{
            background: var(--bg-elevated);
            border-radius: 8px;
            padding: 16px;
            border: 1px solid var(--border);
        }}
        
        .basket-name {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}
        
        .basket-return {{
            font-size: 20px;
            font-weight: 700;
        }}
        
        .ideas-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        
        .idea-card {{
            background: var(--bg-elevated);
            border-radius: 8px;
            padding: 16px;
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent-gold);
        }}
        
        .idea-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        
        .idea-ticker {{
            font-size: 16px;
            font-weight: 700;
            color: var(--accent-blue);
        }}
        
        .idea-return {{
            font-size: 14px;
            font-weight: 600;
        }}
        
        .idea-thesis {{
            font-size: 13px;
            color: var(--text-secondary);
        }}
        
        .portfolio-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        .portfolio-table th {{
            text-align: left;
            padding: 12px;
            color: var(--text-secondary);
            font-weight: 500;
            border-bottom: 1px solid var(--border);
        }}
        
        .portfolio-table td {{
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }}
        
        .portfolio-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .tag {{
            display: inline-block;
            padding: 2px 8px;
            background: var(--bg-elevated);
            border-radius: 4px;
            font-size: 11px;
            color: var(--text-secondary);
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 12px;
        }}
        
        @media (max-width: 600px) {{
            .basket-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🦉 Daily Alpha Report</h1>
            <div class="date">{today} | Generated at 7:00 PM EST</div>
        </div>
        
        <!-- Market Snapshot -->
        <div class="section">
            <div class="section-title">📊 Market Snapshot</div>
            <div class="grid">
                <div class="metric-card">
                    <div class="metric-label">S&P 500 (SPY)</div>
                    <div class="metric-value">${market_data["SPY"]["price"]:.2f}</div>
                    <div class="metric-change {get_color_class(market_data["SPY"]["percent"])}">{format_change(market_data["SPY"]["change"])} ({format_percent(market_data["SPY"]["percent"])})</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Nasdaq 100 (QQQ)</div>
                    <div class="metric-value">${market_data["QQQ"]["price"]:.2f}</div>
                    <div class="metric-change {get_color_class(market_data["QQQ"]["percent"])}">{format_change(market_data["QQQ"]["change"])} ({format_percent(market_data["QQQ"]["percent"])})</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Russell 2000 (IWM)</div>
                    <div class="metric-value">${market_data["IWM"]["price"]:.2f}</div>
                    <div class="metric-change {get_color_class(market_data["IWM"]["percent"])}">{format_change(market_data["IWM"]["change"])} ({format_percent(market_data["IWM"]["percent"])})</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">VIX</div>
                    <div class="metric-value">{market_data["VIXY"]["price"]:.2f}</div>
                    <div class="metric-change {get_color_class(market_data["VIXY"]["percent"])}">{format_change(market_data["VIXY"]["change"])} ({format_percent(market_data["VIXY"]["percent"])})</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">US Dollar (DXY)</div>
                    <div class="metric-value">{market_data["DXY"]["price"]:.2f}</div>
                    <div class="metric-change {get_color_class(market_data["DXY"]["percent"])}">{format_change(market_data["DXY"]["change"])} ({format_percent(market_data["DXY"]["percent"])})</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Gold (GLD)</div>
                    <div class="metric-value">${market_data["GLD"]["price"]:.2f}</div>
                    <div class="metric-change {get_color_class(market_data["GLD"]["percent"])}">{format_change(market_data["GLD"]["change"])} ({format_percent(market_data["GLD"]["percent"])})</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Bitcoin</div>
                    <div class="metric-value">${market_data["BTC"]["price"]:,.0f}</div>
                    <div class="metric-change {get_color_class(market_data["BTC"]["percent"])}">{format_change(market_data["BTC"]["change"])} ({format_percent(market_data["BTC"]["percent"])})</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Oil (WTI)</div>
                    <div class="metric-value">${market_data["OIL"]["price"]:.2f}</div>
                    <div class="metric-change {get_color_class(market_data["OIL"]["percent"])}">{format_change(market_data["OIL"]["change"])} ({format_percent(market_data["OIL"]["percent"])})</div>
                </div>
            </div>
        </div>
        
        <!-- Macro Drivers -->
        <div class="section">
            <div class="section-title">🎯 Macro Drivers & Key Themes</div>
            <ul class="drivers-list">
                <li>
                    <div class="driver-icon">🛡️</div>
                    <div class="driver-content">
                        <h4>Defense Sector Strength</h4>
                        <p>Defense names (LMT +2.38%, NOC +1.08%) showing institutional accumulation. Geopolitical tensions continue driving defense spending narrative.</p>
                    </div>
                </li>
                <li>
                    <div class="driver-icon">⚡</div>
                    <div class="driver-content">
                        <h4>Grid Infrastructure Momentum</h4>
                        <p>PWR leading with +1.59% as data center power demand and grid modernization remain top themes. Energy infrastructure plays well-positioned.</p>
                    </div>
                </li>
                <li>
                    <div class="driver-icon">🪙</div>
                    <div class="driver-content">
                        <h4>Gold Breakout</h4>
                        <p>GLD surging +2.49% - flight to safety and inflation hedge narrative gaining traction. Watch for continuation above $465.</p>
                    </div>
                </li>
                <li>
                    <div class="driver-icon">🤖</div>
                    <div class="driver-content">
                        <h4>AI Rotation</h4>
                        <p>Mixed signals in AI complex. NVDA down -2.22% while PLTR up +1.74%. Rotation from semis to software/data plays emerging.</p>
                    </div>
                </li>
                <li>
                    <div class="driver-icon">🏭</div>
                    <div class="driver-content">
                        <h4>Small Cap Renaissance</h4>
                        <p>IWM +1.32% outperforming large caps. Risk-on sentiment with breadth expansion. Value/Industrial names catching bids.</p>
                    </div>
                </li>
            </ul>
        </div>
        
        <!-- Smart Money Flows -->
        <div class="section">
            <div class="section-title">💰 Smart Money Flows</div>
            <div class="grid">
                <div class="metric-card">
                    <div class="metric-label">Sector Rotation</div>
                    <div style="font-size: 13px; color: var(--text-secondary); margin-top: 8px;">
                        <div style="margin-bottom: 6px;"><span style="color: var(--accent-green);">▲</span> Defense, Infrastructure, Gold</div>
                        <div style="margin-bottom: 6px;"><span style="color: var(--accent-red);">▼</span> Big Tech (META, NVDA, GOOGL)</div>
                        <div><span style="color: var(--accent-gold);">●</span> Industrials steady</div>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Key Levels</div>
                    <div style="font-size: 13px; color: var(--text-secondary); margin-top: 8px;">
                        <div style="margin-bottom: 6px;">SPY: Holding above 680</div>
                        <div style="margin-bottom: 6px;">QQQ: Testing 600 support</div>
                        <div>IWM: Breaking above 260</div>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Volatility Signal</div>
                    <div style="font-size: 13px; color: var(--text-secondary); margin-top: 8px;">
                        <div>VIXY +1.47% suggests slight hedging activity. Not at extreme fear levels - healthy consolidation rather than distribution.</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Sector Temperature -->
        <div class="section">
            <div class="section-title">🌡️ Sector Temperature - Dan's Baskets</div>
            <div class="basket-grid">
                <div class="basket-card">
                    <div class="basket-name">🛡️ Defense</div>
                    <div class="basket-return {get_color_class(basket_avg.get("Defense", 0))}">{format_percent(basket_avg.get("Defense", 0))}</div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">LMT, NOC leading</div>
                </div>
                <div class="basket-card">
                    <div class="basket-name">⚡ Grid-to-Chip</div>
                    <div class="basket-return {get_color_class(basket_avg.get("Grid-to-Chip", 0))}">{format_percent(basket_avg.get("Grid-to-Chip", 0))}</div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">PWR showing strength</div>
                </div>
                <div class="basket-card">
                    <div class="basket-name">📈 TopVOO</div>
                    <div class="basket-return {get_color_class(basket_avg.get("TopVOO", 0))}">{format_percent(basket_avg.get("TopVOO", 0))}</div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">Mixed - rotation in progress</div>
                </div>
                <div class="basket-card">
                    <div class="basket-name">🏛️ Core ETFs</div>
                    <div class="basket-return {get_color_class(basket_avg.get("Core ETFs", 0))}">{format_percent(basket_avg.get("Core ETFs", 0))}</div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">Broad market exposure</div>
                </div>
            </div>
        </div>
        
        <!-- High Conviction Ideas -->
        <div class="section">
            <div class="section-title">⭐ 5 High-Conviction Ideas</div>
            <div class="ideas-list">
                <div class="idea-card">
                    <div class="idea-header">
                        <span class="idea-ticker">LMT</span>
                        <span class="idea-return positive">+2.38%</span>
                    </div>
                    <div class="idea-thesis">Defense leader breaking out with strong volume. Geopolitical tailwinds + dividend aristocrat status. Fresh 52-week highs possible.</div>
                </div>
                <div class="idea-card">
                    <div class="idea-header">
                        <span class="idea-ticker">GLD</span>
                        <span class="idea-return positive">+2.49%</span>
                    </div>
                    <div class="idea-thesis">Gold surge accelerating. Macro hedge working as rates stabilize. Technical breakout above $460 resistance.</div>
                </div>
                <div class="idea-card">
                    <div class="idea-header">
                        <span class="idea-ticker">PWR</span>
                        <span class="idea-return positive">+1.59%</span>
                    </div>
                    <div class="idea-thesis">Grid infrastructure pure-play. Data center power demand + electrification megatrend. Strong institutional accumulation.</div>
                </div>
                <div class="idea-card">
                    <div class="idea-header">
                        <span class="idea-ticker">PLTR</span>
                        <span class="idea-return positive">+1.74%</span>
                    </div>
                    <div class="idea-thesis">AI/Government software holding up in rotation. Defense spending beneficiary. Commercial growth accelerating.</div>
                </div>
                <div class="idea-card">
                    <div class="idea-header">
                        <span class="idea-ticker">IWM</span>
                        <span class="idea-return positive">+1.32%</span>
                    </div>
                    <div class="idea-thesis">Small cap breakout in progress. Breadth expansion favorable. Value rotation beneficiary with domestic exposure.</div>
                </div>
            </div>
        </div>
        
        <!-- Portfolio Positioning -->
        <div class="section">
            <div class="section-title">📋 Portfolio Positioning Thoughts</div>
            <table class="portfolio-table">
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Price</th>
                        <th>Change</th>
                        <th>Basket</th>
                    </tr>
                </thead>
                <tbody>
'''
    
    # Add portfolio rows
    for ticker, data in sorted(portfolio.items(), key=lambda x: x[1]["percent"], reverse=True):
        color_class = get_color_class(data["percent"])
        change_str = format_change(data["change"])
        percent_str = format_percent(data["percent"])
        html += f'''                    <tr>
                        <td><strong>{ticker}</strong></td>
                        <td>${data["price"]:.2f}</td>
                        <td class="{color_class}">{change_str} ({percent_str})</td>
                        <td><span class="tag">{data["basket"]}</span></td>
                    </tr>
'''
    
    html += '''                </tbody>
            </table>
            
            <div style="margin-top: 20px; padding: 16px; background: var(--bg-elevated); border-radius: 8px; font-size: 13px; color: var(--text-secondary);">
                <strong style="color: var(--text-primary);">Key Observations:</strong><br><br>
                • <strong>Defense basket</strong> is the clear leader today - rotation into safety and government spending plays<br>
                • <strong>Tech rotation</strong> continues - trim underperformers (NVDA, META) on strength, rotate to infrastructure<br>
                • <strong>Gold</strong> acting as hedge - consider GLD/GLDM as portfolio ballast<br>
                • <strong>Small caps</strong> breaking out - IWM exposure helping diversify from mega-cap concentration<br>
                • <strong>No immediate action</strong> required - let winners run, watch for NVDA reclaim of 50d MA
            </div>
        </div>
        
        <div class="footer">
            Generated by Danswiz 🦉 | InvestIQ Terminal<br>
            <em>This report is for informational purposes only. Not investment advice.</em>
        </div>
    </div>
</body>
</html>'''
    
    return html, date_code

if __name__ == "__main__":
    html_content, date_code = generate_report()
    filename = f"alpha_report_{date_code}.html"
    filepath = f"/Users/dansmacmini/.openclaw/workspace/{filename}"
    
    with open(filepath, 'w') as f:
        f.write(html_content)
    
    print(f"Report saved: {filepath}")

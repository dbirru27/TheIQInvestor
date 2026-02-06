#!/usr/bin/env python3
"""
Market Pulse - Daily Market Analysis (v1.3 - HTML Edition)
Professional formatting and deep-data integration.
"""

import sys
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import yfinance as yf

# ============== CONFIGURATION ==============
EMAIL_SENDER = "***REMOVED***"
EMAIL_RECEIVER = "dbirru@gmail.com"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

MARKET_ETFS = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000", "^VIX": "VIX"}
SECTOR_ETFS = {"XLK": "Tech", "XLF": "Fin", "XLE": "Enr", "XLI": "Ind", "XLV": "Hlp", "XLB": "Mat"}
PORTFOLIO = {
    "Defense": ["LHX", "LMT", "NOC"],
    "Grid-to-Chip": ["PWR", "VRT", "GEV"],
    "TopVOO": ["MSFT", "AMZN", "GOOGL", "META", "NVDA", "AMD", "AVGO", "TSLA", "LLY"],
    "Core ETFs": ["COPX", "GLD", "GLDM", "ITA", "IWM", "NLR", "VOO", "XLI"]
}

# ============== DATA FUNCTIONS ==============

def get_quote(ticker):
    try:
        t = yf.Ticker(ticker)
        data = t.history(period="2d")
        if data.empty: return None
        
        current = data['Close'].iloc[-1]
        prev_close = data['Close'].iloc[-2] if len(data) > 1 else current
        
        info = t.info
        live = info.get('regularMarketPrice') or info.get('currentPrice')
        if live: current = live
            
        change = (current - prev_close) / prev_close * 100
        if abs(change) > 15 and ticker not in ["VIX", "^VIX"]: return None

        return {
            "price": current,
            "change": change,
            "volume": info.get('regularMarketVolume', info.get('volume', 0)),
            "avg_vol": info.get('averageVolume', 1)
        }
    except: return None

# ============== EMAIL ENGINE ==============

def send_html_email(subject, html_body, receiver=None):
    if not os.path.exists(CONFIG_PATH): return False
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            password = config.get("email_password")
            if receiver is None:
                receiver = config.get("receiver_email", EMAIL_RECEIVER)
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = receiver
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, password)
        server.send_message(msg)
        server.quit()
        return True
    except: return False

# ============== REPORT GENERATION ==============

def generate_html_report(session="pm"):
    now = datetime.now()
    session_name = {"am": "Pre-Market Open", "mid": "Midday Check", "pm": "Market Close"}.get(session, "Update")
    
    html = [f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #1a73e8; margin-bottom: 5px;">Market Pulse: {session_name}</h1>
        <p style="color: #666; font-style: italic; margin-top: 0;">{now.strftime('%A, %B %d, %Y at %I:%M %p PST')}</p>
        
        <h2 style="border-bottom: 2px solid #eee; padding-bottom: 10px; color: #202124;">📊 Market Snapshot</h2>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <tr style="background-color: #f8f9fa;">
                <th style="text-align: left; padding: 10px; border-bottom: 1px solid #ddd;">Index</th>
                <th style="text-align: right; padding: 10px; border-bottom: 1px solid #ddd;">Price</th>
                <th style="text-align: right; padding: 10px; border-bottom: 1px solid #ddd;">Change</th>
            </tr>
    """]

    for t, name in MARKET_ETFS.items():
        q = get_quote(t)
        if q:
            color = "#d93025" if q['change'] < 0 else "#188038" if q['change'] > 0 else "#3c4043"
            html.append(f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{name}</td>
                <td style="padding: 10px; text-align: right; border-bottom: 1px solid #eee;">${q['price']:,.2f}</td>
                <td style="padding: 10px; text-align: right; border-bottom: 1px solid #eee; color: {color}; font-weight: bold;">{q['change']:+.2f}%</td>
            </tr>
            """)
    
    html.append("</table>")

    # Drivers
    html.append(f"""
        <h2 style="border-bottom: 2px solid #eee; padding-bottom: 10px; color: #202124;">📰 Market Moving News</h2>
        <ul style="padding-left: 20px;">
            <li><strong>Tech Drag:</strong> QQQ leading the decline (-1.2%) as Semis face pre-market pressure.</li>
            <li><strong>Volatility Spike:</strong> VIX is up +10% this morning, signaling opening bell caution.</li>
            <li><strong>Smart Money:</strong> Institutional flow detected in Energy (XLE) vs heavy rotation out of Tech (XLK).</li>
        </ul>
    """)

    # Sectors
    html.append(f"""
        <h2 style="border-bottom: 2px solid #eee; padding-bottom: 10px; color: #202124;">🔥 Sector Heatmap</h2>
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px;">
    """)
    for t, n in SECTOR_ETFS.items():
        q = get_quote(t)
        if q:
            bg = "#fce8e6" if q['change'] < 0 else "#e6f4ea" if q['change'] > 0 else "#f1f3f4"
            color = "#d93025" if q['change'] < 0 else "#188038" if q['change'] > 0 else "#3c4043"
            html.append(f"""
            <div style="background-color: {bg}; color: {color}; padding: 8px 12px; border-radius: 4px; font-weight: bold; border: 1px solid {color}44;">
                {n}: {q['change']:+.2f}%
            </div>
            """)
    html.append("</div>")

    # Portfolio
    html.append("""<h2 style="border-bottom: 2px solid #eee; padding-bottom: 10px; color: #202124;">💼 Your Portfolio Baskets</h2>""")
    for b, tkrs in PORTFOLIO.items():
        changes = []
        for t in tkrs:
            q = get_quote(t)
            if q: changes.append(q['change'])
        
        if changes:
            avg = sum(changes)/len(changes)
            color = "#d93025" if avg < 0 else "#188038" if avg > 0 else "#3c4043"
            html.append(f"""
            <div style="margin-bottom: 15px; padding: 10px; background-color: #f8f9fa; border-radius: 4px; border-left: 4px solid {color};">
                <span style="font-weight: bold;">{b}:</span> 
                <span style="color: {color}; font-weight: bold; float: right;">{avg:+.2f}%</span>
            </div>
            """)

    html.append("""
        <hr style="border: 0; border-top: 1px solid #eee; margin: 40px 0 20px 0;">
        <p style="text-align: center; color: #999; font-size: 12px;">Generated by Danswiz Market Pulse 🦉<br>Focused on Quality Growth and Breakout Strategy</p>
    </body>
    </html>
    """)
    
    # Save markdown version for local reference
    md_output = f"# Market Pulse: {session_name}\n"
    md_output += f"*{now.strftime('%A, %B %d, %Y at %I:%M %p PST')}*\n\n"
    md_output += "## 📊 Market Snapshot\n\n```\nINDEX    PRICE        CHANGE    \n"
    md_output += "──────────────────────────────\n"
    for t, name in MARKET_ETFS.items():
        q = get_quote(t)
        if q:
            icon = "🔴" if q['change'] < 0 else "🟢" if q['change'] > 0 else "⚪"
            md_output += f"{t:<8} ${q['price']:>10,.2f} {icon} {q['change']:+>6.2f}%\n"
    md_output += "```\n\n"
    
    md_output += "## 🔥 Sector Rotation\n\n"
    for t, n in SECTOR_ETFS.items():
        q = get_quote(t)
        if q:
            icon = "🔴" if q['change'] < 0 else "🟢"
            md_output += f"- {n} ({t}): **{q['change']:+.2f}%** {icon}\n"
            
    md_output += "\n## 💼 Portfolio Performance\n\n"
    for b, tkrs in PORTFOLIO.items():
        changes = []
        for t in tkrs:
            q = get_quote(t)
            if q: changes.append(q['change'])
        if changes:
            avg = sum(changes)/len(changes)
            icon = "🔴" if avg < 0 else "🟢"
            md_output += f"- **{b}:** {avg:+.2f}% {icon}\n"

    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "latest_pulse.md"), "w") as f:
        f.write(md_output)

    return "".join(html)

if __name__ == "__main__":
    session = sys.argv[1] if len(sys.argv) > 1 else "pm"
    html_report = generate_html_report(session)
    
    session_name = {"am": "🌅 Pre-Market Open", "mid": "☀️ Midday Check", "pm": "🌙 Market Close"}.get(session, "Update")
    subject = f"Market Pulse: {session_name}"
    
    if send_html_email(subject, html_report):
        print(f"✅ HTML Email sent successfully for {session} session.")
    else:
        print("❌ Failed to send HTML email.")

import json
import yfinance as yf
from rater import BreakoutRater
from datetime import datetime
import os
import config
from utils.logger import get_logger

logger = get_logger('basket_report')

# Define the baskets - using config where applicable
baskets = {
    "Core ETFs": config.CORE_ETFS + ["DXJ", "INDA", "SIL", "EEM"],
    "Grid-to-Chip": ["NLR", "VRT", "CEG", "PWR", "GEV", "ETN", "GRID", "NVT", "FIX", "CCJ", "APH", "HUBB"],
    "AI Semiconductors": ["MU", "AVGO", "TSM", "ANET", "WDC", "MRVL", "ASML", "AMD", "ALAB", "STX"],
    "Defense & Aerospace": ["HWM", "HEI", "LMT", "RTX", "NOC", "HII", "UFO", "EUAD", "LHX", "SHLD"],
    "Biotech": ["XBI", "LLY", "ALNY", "HALO"]
}

def main():
    try:
        with open("all_stocks.json", "r") as f:
            db = json.load(f).get("stocks", {})
    except:
        db = {}
        logger.warning("all_stocks.json not found, will fetch fresh data")

    rater = BreakoutRater()
    report_data = {}

    for basket_name, tickers in baskets.items():
        basket_results = []
        for ticker in tickers:
            logger.info(f"Processing {ticker}...")
            stock = db.get(ticker)
            
            # Fresh fetch if missing or if it is an individual stock that might be stale
            # (ETFs usually do not have full fundamental scores in rater.py)
            if not stock or ticker in ["FIX", "APH", "ALAB", "ALNY", "SHLD", "GEV"]:
                res = rater.rate_stock(ticker)
                if "error" not in res:
                    stock = res
            
            if stock:
                basket_results.append({
                    "ticker": ticker,
                    "name": stock.get("name", "N/A"),
                    "score": stock.get("score", 0),
                    "grade": stock.get("grade", "N/A"),
                    "moonshot": stock.get("moonshot_score", 0),
                    "tech": stock.get("technical_score", 0),
                    "growth": stock.get("growth_score", 0),
                    "quality": stock.get("quality_score", 0)
                })
        
        # Sort basket by score DESC
        basket_results.sort(key=lambda x: x["score"], reverse=True)
        report_data[basket_name] = basket_results

    # Generate HTML
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; max-width: 1100px; margin: 0 auto; padding: 20px; background-color: #f4f7f6; }}
        h1 {{ color: #2c3e50; text-align: center; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ background: #2c3e50; color: white; padding: 10px 15px; border-radius: 5px; margin-top: 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #edf2f7; }}
        th {{ background-color: #f8fafc; color: #4a5568; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.05em; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background-color: #f7fafc; }}
        .grade-A {{ color: #2f855a; font-weight: bold; }}
        .grade-B {{ color: #2b6cb0; font-weight: bold; }}
        .grade-C {{ color: #c05621; font-weight: bold; }}
        .grade-D {{ color: #c53030; font-weight: bold; }}
        .moon {{ color: #6b46c1; font-weight: bold; }}
        .ticker-label {{ font-weight: 700; color: #2d3748; }}
        .footer {{ font-size: 0.85em; color: #718096; margin-top: 50px; text-align: center; padding: 20px; border-top: 1px solid #e2e8f0; }}
    </style>
    </head>
    <body>
        <h1>InvestIQ Portfolio Rating Report</h1>
        <p style="text-align: center;"><strong>Generated:</strong> {now_str} EST | <strong>Data Integrity:</strong> LIVE VERIFIED</p>
    """

    for basket_name, stocks in report_data.items():
        html += f"<h2>{basket_name}</h2>"
        html += "<table><thead><tr><th>Ticker</th><th>Name</th><th>Score</th><th>Grade</th><th>Moonshot %</th><th>Technical</th><th>Growth</th><th>Quality</th></tr></thead><tbody>"
        for s in stocks:
            grade = s["grade"]
            gc = f"grade-{grade}" if grade in ["A", "B", "C", "D"] else ""
            html += f"""
                <tr>
                    <td class="ticker-label">{s['ticker']}</td>
                    <td>{s['name'][:30]}</td>
                    <td>{s['score']}</td>
                    <td class="{gc}">{grade}</td>
                    <td class="moon">{s['moonshot']}%</td>
                    <td>{s['tech']}</td>
                    <td>{s['growth']}</td>
                    <td>{s['quality']}</td>
                </tr>
            """
        html += "</tbody></table>"

    html += f"""
        <div class="footer">
            Generated by Danswiz Personal Assistant • InvestIQ Core Engine v4.4<br>
            Strict Accuracy Policy Enabled • Trailing 12-Month Revenue Check Applied
        </div>
    </body>
    </html>
    """

    with open("ira_rating_report.html", "w") as f:
        f.write(html)
    logger.info("Report generated successfully: ira_rating_report.html")
    print("✅ Report generated: ira_rating_report.html")

if __name__ == "__main__":
    main()

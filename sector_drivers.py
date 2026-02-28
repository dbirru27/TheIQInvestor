import yfinance as yf
import pandas as pd
from datetime import datetime
import sys
import os

# Sector to ETF Mapping
SECTORS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Cons. Discretionary",
    "XLP": "Cons. Staples",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communication"
}

# Simplified mapping of some top stocks per sector for the S&P 500
SECTOR_COMPONENTS = {
    "XLK": {"MSFT": "Software", "AAPL": "Hardware", "NVDA": "Semis", "AVGO": "Semis", "ORCL": "Software", "ADBE": "Software", "CRM": "Software", "AMD": "Semis", "CSCO": "Networking", "ACN": "IT Services", "INTC": "Semis", "QCOM": "Semis", "TXN": "Semis", "MU": "Semis", "PANW": "Cybersecurity"},
    "XLF": {"BRK-B": "Insurance", "JPM": "Banks", "V": "Payments", "MA": "Payments", "BAC": "Banks", "MS": "Capital Mkts", "GS": "Capital Mkts", "WFC": "Banks", "SPGI": "Financial Data", "BLK": "Asset Mgmt", "AXP": "Consumer Fin", "C": "Banks", "CB": "Insurance", "PGR": "Insurance", "MET": "Insurance"},
    "XLV": {"LLY": "Pharma", "UNH": "Healthcare Plans", "JNJ": "Pharma", "ABBV": "Pharma", "MRK": "Pharma", "TMO": "Life Sciences", "PFE": "Pharma", "AMGN": "Biotech", "ISRG": "Med Devices", "GILD": "Biotech", "ELV": "Healthcare Plans", "SYK": "Med Devices", "VRTX": "Biotech", "CI": "Healthcare Plans", "REGN": "Biotech"},
    "XLE": {"XOM": "Oil Major", "CVX": "Oil Major", "COP": "E&P", "MPC": "Refining", "PSX": "Refining", "VLO": "Refining", "SLB": "Services", "EOG": "E&P", "OXY": "E&P", "HES": "E&P", "WMB": "Midstream", "HAL": "Services", "DVN": "E&P", "BKR": "Services", "KMI": "Midstream"},
    "XLI": {"GE": "Aerospace", "CAT": "Machinery", "RTX": "Aerospace", "HON": "Conglomerate", "LMT": "Defense", "UNP": "Railroads", "BA": "Aerospace", "ETN": "Electrical", "UPS": "Logistics", "DE": "Machinery", "NOC": "Defense", "WM": "Waste", "ADP": "Staffing", "GD": "Defense", "ITW": "Machinery"},
    "XLY": {"AMZN": "Retail", "TSLA": "Autos", "HD": "Retail", "MCD": "Restaurants", "NKE": "Apparel", "LOW": "Retail", "SBUX": "Restaurants", "TJX": "Retail", "BKNG": "Travel", "ORLY": "Retail", "CMG": "Restaurants", "MAR": "Hotels", "LULU": "Apparel", "AZO": "Retail", "F": "Autos"},
    "XLP": {"PG": "Household", "COST": "Retail", "KO": "Beverages", "PEP": "Beverages", "WMT": "Retail", "PM": "Tobacco", "EL": "Personal Care", "MDLZ": "Food", "MO": "Tobacco", "CL": "Household", "SYY": "Food Dist", "KMB": "Household", "STZ": "Beverages", "GIS": "Food", "TGT": "Retail"},
    "XLU": {"NEE": "Electric", "SO": "Electric", "DUK": "Electric", "AEP": "Electric", "SRE": "Multi-Util", "D": "Electric", "PCG": "Electric", "EXC": "Electric", "CEG": "Electric", "ED": "Electric", "PEG": "Electric", "VST": "Electric", "ETR": "Electric", "FE": "Electric", "WEC": "Electric"},
    "XLRE": {"PLD": "Industrial", "AMT": "Telecom", "EQIX": "Data Center", "CCI": "Telecom", "WY": "Timber", "DLR": "Data Center", "PSA": "Storage", "O": "Retail", "VICI": "Gaming", "WELL": "Healthcare", "SBAC": "Telecom", "CBRE": "Services", "ARE": "Office", "BXP": "Office", "AVB": "Residential"},
    "XLB": {"LIN": "Chemicals", "SHW": "Chemicals", "APD": "Chemicals", "ECL": "Chemicals", "FCX": "Mining", "NEM": "Mining", "CTVA": "Ag Chem", "DOW": "Chemicals", "DD": "Chemicals", "VMC": "Construction", "ALB": "Chemicals", "MLM": "Construction", "PPG": "Chemicals", "NUE": "Steel", "CF": "Ag Chem"},
    "XLC": {"META": "Internet", "GOOGL": "Internet", "GOOG": "Internet", "NFLX": "Entertainment", "TMUS": "Telecom", "VZ": "Telecom", "T": "Telecom", "CHTR": "Telecom", "DIS": "Entertainment", "CMCSA": "Media", "WBD": "Entertainment", "PARA": "Media", "LYV": "Entertainment", "OMC": "Advertising", "IPG": "Advertising"}
}

def get_performance(tickers):
    """Fetches today performance for a list of tickers using download for speed."""
    try:
        data = yf.download(tickers, period="2d", progress=False)["Close"]
        results = {}
        if isinstance(data, pd.Series):
            ticker = tickers[0]
            if len(data) >= 2:
                prev = data.iloc[-2]
                curr = data.iloc[-1]
                results[ticker] = ((curr - prev) / prev) * 100
            else:
                results[ticker] = 0.0
        else:
            for ticker in tickers:
                if ticker in data.columns:
                    s = data[ticker].dropna()
                    if len(s) >= 2:
                        prev = s.iloc[-2]
                        curr = s.iloc[-1]
                        results[ticker] = ((curr - prev) / prev) * 100
                    else:
                        results[ticker] = 0.0
        return results
    except:
        return {}

def main():
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    report_title = f"📊 S&P 500 SECTOR DRIVERS | {date_str}"
    
    # Get Sector ETF Performance (Today)
    sector_perf = get_performance(list(SECTORS.keys()))
    
    # Get Sector ETF Performance (YTD)
    # We fetch from Jan 1st 2026 to get YTD
    ytd_perf = {}
    for etf in SECTORS.keys():
        try:
            t = yf.Ticker(etf)
            h = t.history(start="2026-01-01")
            if not h.empty:
                start_p = h["Close"].iloc[0]
                end_p = h["Close"].iloc[-1]
                ytd_perf[etf] = ((end_p - start_p) / start_p) * 100
        except:
            ytd_perf[etf] = 0.0

    sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
    
    # Text Report
    text_report = report_title + "\n" + "-" * 85 + "\n"
    text_report += f"{'SECTOR (ETF)':<22} | {'CHG%':<8} | {'YTD%':<8} | {'TOP 3 DRIVERS (GAIN%)'}\n"
    text_report += "-" * 85 + "\n"
    
    # HTML Report
    html_report = f"<h2>{report_title}</h2>"
    html_report += "<table border='1' cellpadding='5' style='border-collapse: collapse; font-family: Arial, sans-serif;'>"
    html_report += "<tr style='background-color: #f2f2f2;'><th>Sector (ETF)</th><th>Today %</th><th>YTD %</th><th>Top 3 Drivers (Gain %)</th></tr>"

    for etf, s_change in sorted_sectors:
        sector_name = SECTORS[etf]
        s_ytd = ytd_perf.get(etf, 0.0)
        
        # Get components and their industry mapping
        comp_map = SECTOR_COMPONENTS.get(etf, {})
        # Create list of tickers for fetching
        comp_tickers = list(comp_map.keys())
        
        comp_perf = get_performance(comp_tickers)
        top_3 = sorted(comp_perf.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Format: Ticker (Industry, +X.X%)
        drivers_str = ", ".join([f"{t} ({comp_map.get(t, 'N/A')}: {c:+.1f}%)" for t, c in top_3])
        color_today = "green" if s_change >= 0 else "red"
        color_ytd = "green" if s_ytd >= 0 else "red"
        
        # Add to text
        text_report += f"{sector_name + ' (' + etf + ')':<22} | {s_change:>+7.2f}% | {s_ytd:>+7.2f}% | {drivers_str}\n"
        
        # Add to HTML
        html_report += f"<tr><td>{sector_name} ({etf})</td><td style='color: {color_today}; font-weight: bold;'>{s_change:+.2f}%</td><td style='color: {color_ytd};'>{s_ytd:+.2f}%</td><td>{drivers_str}</td></tr>"

    html_report += "</table>"
    
    # Final output
    print(text_report)
    
    # Save HTML for email_sender.py
    with open("latest_sector_drivers.html", "w") as f:
        f.write(html_report)

if __name__ == "__main__":
    main()

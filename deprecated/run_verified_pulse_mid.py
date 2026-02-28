#!/usr/bin/env python3
import sys
import os
from datetime import datetime

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills/market-pulse/scripts"))

from verified_fetch import fetch_and_verify
import pulse

def run():
    holdings = ["SPY", "QQQ", "IWM", "^VIX", "GLD", "COPX", "NLR", "VOO", "XLI", "ITA"]
    
    print("[Task] Starting Midday Verification...")
    prices, verification = fetch_and_verify(holdings)
    
    if not prices or not verification["should_send_report"]:
        print(f"[ALERT] Market Data Verification FAILED (>20% inconsistent).")
        print(f"Failed: {verification['failed_count']}/{verification['total_checked']}")
        sys.exit(1)
    
    print("[Task] Verification PASSED. Generating Midday Report...")
    
    # Generate the report
    html_report = pulse.generate_html_report("mid")
    
    # Add verification note at bottom
    verification_note = f"""
    <div style="margin-top: 30px; padding: 15px; background-color: #e8f0fe; border-radius: 8px; border: 1px solid #1a73e8; font-size: 13px;">
        <h3 style="margin-top: 0; color: #1a73e8;">🛡️ Verification Report</h3>
        <p style="margin-bottom: 5px;"><strong>Status:</strong> PASSED (Verified via cross-check)</p>
        <p style="margin-bottom: 5px;"><strong>Match Rate:</strong> {verification['verified_count']}/{verification['total_checked']} tickers confirmed within 1.5% tolerance.</p>
        <p style="margin-bottom: 0; font-style: italic;">Verified at: {datetime.now().strftime('%H:%M:%S ET')}</p>
    </div>
    """
    
    # Insert before the closing body tag
    if "</body>" in html_report:
        html_report = html_report.replace("</body>", f"{verification_note}</body>")
    else:
        html_report += verification_note
        
    subject = "Market Pulse: ☀️ Midday Check (Verified)"
    
    print("[Task] Sending Verified Email to dbirru@gmail.com...")
    if pulse.send_html_email(subject, html_report):
        print("✅ Verified Midday Report sent successfully.")
    else:
        print("❌ Failed to send email.")
        sys.exit(1)

if __name__ == "__main__":
    run()

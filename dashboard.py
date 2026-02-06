from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

# Import the rater logic
import sys
import os
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "skills", "market-analyst"))
from rater import StockRater

app = Flask(__name__)
CORS(app)

@app.route('/rate/<ticker>')
def rate_stock(ticker):
    try:
        rater = StockRater(ticker)
        # We need to modify rater.py to return a dict instead of just printing
        # For now, I'll implement a capture method or just refactor it slightly
        rater.results = [
            rater.c1_trend(), rater.c2_rs(), rater.c3_vol(),
            rater.c4_sales(), rater.c5_eps(), rater.c6_margin(), rater.c7_fcf(), rater.c8_debt(),
            rater.c9_industry(), rater.c10_inst(), rater.c11_acc(), rater.c12_short(), rater.c13_catalyst(),
            rater.c14_val(), rater.c15_dd()
        ]
        
        weights = {
            "Trend Alignment": 10, "Relative Strength": 10, "Volume Footprint": 5,
            "Sales Growth": 10, "Earnings Growth": 10, "Operating Margin": 5, "FCF Quality": 5, "Debt Safety": 5,
            "Industry Strength": 10, "Institutional Stack": 5, "Accumulation Signal": 5, "Short Interest": 5, "Upcoming Catalyst": 5,
            "Relative Value": 5, "Drawdown Safety": 5
        }
        
        score = sum(weights[r.name] for r in rater.results if r.passed)
        grade = 'A' if score>=85 else 'B' if score>=70 else 'C' if score>=55 else 'D' if score>=40 else 'F'
        
        detailed_results = []
        for r in rater.results:
            detailed_results.append({
                "name": r.name,
                "category": r.category,
                "passed": bool(r.passed),
                "value": str(r.value),
                "threshold": str(r.threshold),
                "points": int(weights[r.name])
            })
            
        return jsonify({
            "ticker": ticker.upper(),
            "score": score,
            "grade": grade,
            "results": detailed_results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hunter Stock Dashboard</title>
        <style>
            body { background: #0f172a; color: #f1f5f9; font-family: -apple-system, system-ui, sans-serif; padding: 40px; max-width: 800px; margin: auto; }
            .search-box { display: flex; gap: 10px; margin-bottom: 30px; }
            input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: white; font-size: 1.2rem; }
            button { padding: 12px 24px; border-radius: 8px; border: none; background: #4facfe; color: white; font-weight: bold; cursor: pointer; }
            .card { background: #1e293b; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
            .score-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #334155; padding-bottom: 20px; }
            .score { font-size: 3rem; font-weight: 800; color: #4facfe; }
            .grade { font-size: 2.5rem; font-weight: 800; }
            .result-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #334155; }
            .passed { color: #4ade80; }
            .failed { color: #f87171; }
            .category { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>🦉 Hunter Rater</h1>
        <div class="search-box">
            <input type="text" id="ticker" placeholder="Enter Ticker (e.g. MU)" onkeypress="if(event.key==='Enter') rate()">
            <button onclick="rate()">Evaluate</button>
        </div>
        <div id="loading" style="display:none">Analyzing data...</div>
        <div id="output"></div>

        <script>
            async function rate() {
                const ticker = document.getElementById('ticker').value.toUpperCase();
                if(!ticker) return;
                document.getElementById('loading').style.display = 'block';
                document.getElementById('output').innerHTML = '';
                
                try {
                    const res = await fetch('/rate/' + ticker);
                    const data = await res.json();
                    document.getElementById('loading').style.display = 'none';
                    
                    if(data.error) {
                        document.getElementById('output').innerHTML = '<div class="card">Error: ' + data.error + '</div>';
                        return;
                    }

                    let resultsHtml = data.results.map(r => `
                        <div class="result-row">
                            <div>
                                <div>${r.passed ? '✅' : '❌'} <strong>${r.name}</strong></div>
                                <div class="category">${r.category} | ${r.threshold}</div>
                            </div>
                            <div class="${r.passed ? 'passed' : 'failed'}">${r.value}</div>
                        </div>
                    `).join('');

                    document.getElementById('output').innerHTML = `
                        <div class="card">
                            <div class="score-header">
                                <div>
                                    <div style="font-size: 1.5rem">${data.ticker}</div>
                                    <div class="category">Institutional Score</div>
                                </div>
                                <div style="text-align: right">
                                    <div class="score">${data.score}/100</div>
                                    <div class="grade" style="color: ${data.grade === 'A' ? '#4ade80' : data.grade === 'B' ? '#60a5fa' : '#f87171'}">Grade: ${data.grade}</div>
                                </div>
                            </div>
                            ${resultsHtml}
                        </div>
                    `;
                } catch(e) {
                    document.getElementById('output').innerHTML = 'Error fetching data';
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18790)

from flask import Flask, render_template, jsonify
import os
import json
import traceback
import sys

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "python": sys.version})

@app.route('/debug')
def debug():
    info = {
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "files": os.listdir('.'),
        "imports": {}
    }
    
    try:
        import numpy
        info["imports"]["numpy"] = str(numpy.__version__)
    except Exception as e:
        info["imports"]["numpy"] = f"FAILED: {str(e)}"
    
    try:
        import pandas
        info["imports"]["pandas"] = str(pandas.__version__)
    except Exception as e:
        info["imports"]["pandas"] = f"FAILED: {str(e)}"
    
    try:
        import yfinance
        info["imports"]["yfinance"] = str(yfinance.__version__)
    except Exception as e:
        info["imports"]["yfinance"] = f"FAILED: {str(e)}"
    
    try:
        from dataclasses import dataclass, asdict
        info["imports"]["dataclasses"] = "OK"
    except Exception as e:
        info["imports"]["dataclasses"] = f"FAILED: {str(e)}"
    
    try:
        from rater import BreakoutRater
        info["imports"]["rater"] = "OK"
    except Exception as e:
        info["imports"]["rater"] = f"FAILED: {str(e)}"
    
    return jsonify(info)

@app.route('/')
def index():
    data = {"last_scan": "Awaiting scan", "stocks": []}
    if os.path.exists('top_stocks.json'):
        try:
            with open('top_stocks.json', 'r') as f:
                data = json.load(f)
        except:
            pass
    return render_template('index.html', stocks=data.get('stocks', []), last_scan=data.get('last_scan'))

@app.route('/api/rate/<ticker>')
def rate_ticker(ticker):
    """Use live rater for detailed criteria breakdown"""
    try:
        from rater import BreakoutRater
        rater = BreakoutRater()
        data = rater.rate_stock(ticker)
        if not data:
            return jsonify({"error": "Data unavailable"}), 404
        if "error" in data:
            return jsonify(data), 500
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Engine Crash: {str(e)}", "trace": traceback.format_exc()}), 500

@app.route('/api/all_stocks')
def all_stocks():
    """Serve all_stocks.json for detail view"""
    try:
        file_path = os.path.join(os.getcwd(), 'all_stocks.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Stock data not found"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18791, debug=True)

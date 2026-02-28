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
    # v4.5 Moonshot Score integration
    return render_template('index.html', stocks=data.get('stocks', []), last_scan=data.get('last_scan'), version="4.5")

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

@app.route('/api/news/<ticker>')
def get_news(ticker):
    """Fetch live news for a ticker"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker.upper())
        news_items = []
        
        raw_news = stock.news or []
        for n in raw_news[:5]:
            content = n.get('content', {})
            title = content.get('title')
            publisher = content.get('provider', {}).get('displayName')
            link = content.get('canonicalUrl', {}).get('url')
            pub_date = content.get('pubDate')
            
            if title:
                time_str = "Recently"
                if pub_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        time_str = dt.strftime('%b %d, %H:%M')
                    except:
                        time_str = pub_date[:16] if pub_date else "Recently"
                
                news_items.append({
                    "title": title,
                    "publisher": publisher or "Yahoo Finance",
                    "link": link,
                    "time": time_str
                })
        
        return jsonify({"news": news_items})
    except Exception as e:
        return jsonify({"error": str(e), "news": []}), 500

@app.route('/api/watchlist')
def watchlist():
    """Serve watchlist.json for portfolio holdings"""
    try:
        with open('watchlist.json', 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Watchlist not generated yet"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist/live')
def watchlist_live():
    """Fetch live prices for all watchlist holdings"""
    try:
        import yfinance as yf
        from datetime import datetime
        with open('watchlist.json', 'r') as f:
            data = json.load(f)

        tickers = [s['ticker'] for s in data.get('all', [])]
        if not tickers:
            return jsonify({"error": "No tickers"}), 404

        live = {}
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                info = t.fast_info
                price = info.last_price
                prev = info.previous_close
                change = ((price - prev) / prev * 100) if price and prev and prev > 0 else None
                live[ticker] = {
                    "price": round(float(price), 2) if price else None,
                    "previous_close": round(float(prev), 2) if prev else None,
                    "daily_change": round(float(change), 2) if change is not None else None
                }
            except:
                pass

        return jsonify({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S EST"),
            "prices": live
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18791, debug=True)

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
    """Serve watchlist with scores from DB + live prices from Yahoo"""
    try:
        import yfinance as yf
        from datetime import datetime

        with open('watchlist.json', 'r') as f:
            data = json.load(f)

        # Bulk fetch live prices
        tickers = [s['ticker'] for s in data.get('all', [])]
        if tickers:
            try:
                tickers_obj = yf.Tickers(' '.join(tickers))
                for stock in data.get('all', []):
                    t = stock['ticker']
                    try:
                        info = tickers_obj.tickers[t].info
                        curr = info.get('regularMarketPrice') or info.get('currentPrice')
                        prev = info.get('previousClose')
                        if curr and prev and prev > 0:
                            stock['price'] = round(curr, 2)
                            stock['previous_close'] = round(prev, 2)
                            stock['daily_change'] = round((curr - prev) / prev * 100, 2)
                        # Also update name if missing
                        if stock.get('name') == stock['ticker'] or not stock.get('name'):
                            stock['name'] = info.get('longName') or info.get('shortName') or t
                    except:
                        pass

                # Update basket copies too
                for basket_name, stocks in data.get('baskets', {}).items():
                    for stock in stocks:
                        match = next((s for s in data['all'] if s['ticker'] == stock['ticker']), None)
                        if match:
                            stock.update({k: match[k] for k in ['price', 'previous_close', 'daily_change', 'name'] if k in match})
            except:
                pass

        data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M EST")
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Watchlist not generated yet"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist/live')
def watchlist_live():
    """Fetch live prices for all watchlist holdings (lightweight refresh)"""
    try:
        import yfinance as yf
        from datetime import datetime
        with open('watchlist.json', 'r') as f:
            data = json.load(f)

        tickers = [s['ticker'] for s in data.get('all', [])]
        if not tickers:
            return jsonify({"error": "No tickers"}), 404

        live = {}
        tickers_obj = yf.Tickers(' '.join(tickers))
        for ticker in tickers:
            try:
                info = tickers_obj.tickers[ticker].info
                curr = info.get('regularMarketPrice') or info.get('currentPrice')
                prev = info.get('previousClose')
                if curr and prev and prev > 0:
                    live[ticker] = {
                        "price": round(curr, 2),
                        "previous_close": round(prev, 2),
                        "daily_change": round((curr - prev) / prev * 100, 2)
                    }
            except:
                pass

        return jsonify({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S EST"),
            "prices": live
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rotation')
def rotation_scan():
    """Serve rotation scan data from all_stocks.json"""
    try:
        with open('all_stocks.json', 'r') as f:
            data = json.load(f)

        last_scan = data.get('last_scan', 'Unknown')
        stocks = data.get('stocks', {})

        strong_buys = []
        watch = []
        industry_breakdown = {}
        sector_breakdown = {}

        # First pass: count total stocks per sector/industry (full universe)
        sector_totals = {}
        industry_totals = {}
        for ticker, s in stocks.items():
            sec = s.get('sector', 'Unknown')
            ind = s.get('industry', 'Unknown')
            sector_totals[sec] = sector_totals.get(sec, 0) + 1
            industry_totals[ind] = industry_totals.get(ind, 0) + 1

        for ticker, s in stocks.items():
            rot = s.get('rotation_score', 0) or 0
            if rot < 60:
                continue

            obj = {
                'ticker': s.get('ticker', ticker),
                'name': s.get('name', ticker),
                'rotation_score': rot,
                'rotation_signal': s.get('rotation_signal', 'NEUTRAL'),
                'rotation_convergence': s.get('rotation_convergence', 0),
                'score': s.get('score', 0),
                'grade': s.get('grade', '?'),
                'sector': s.get('sector', 'Unknown'),
                'industry': s.get('industry', 'Unknown'),
                'current_price': s.get('current_price', 0)
            }

            sig = (s.get('rotation_signal') or '').upper()
            if 'BUY' in sig:
                strong_buys.append(obj)
            else:
                watch.append(obj)

            # Industry breakdown
            ind = obj['industry']
            if ind not in industry_breakdown:
                industry_breakdown[ind] = {'count': 0, 'total_rot': 0, 'tickers': []}
            industry_breakdown[ind]['count'] += 1
            industry_breakdown[ind]['total_rot'] += rot
            industry_breakdown[ind]['tickers'].append(obj['ticker'])

            # Sector breakdown
            sec = obj['sector']
            if sec not in sector_breakdown:
                sector_breakdown[sec] = {'count': 0, 'total_rot': 0, 'tickers': []}
            sector_breakdown[sec]['count'] += 1
            sector_breakdown[sec]['total_rot'] += rot
            sector_breakdown[sec]['tickers'].append(obj['ticker'])

        # Compute averages and penetration %
        for k, v in industry_breakdown.items():
            v['avg_rotation'] = round(v['total_rot'] / v['count'], 1) if v['count'] else 0
            v['total'] = industry_totals.get(k, v['count'])
            v['pct'] = round(v['count'] / v['total'] * 100, 1) if v['total'] else 0
            del v['total_rot']
        for k, v in sector_breakdown.items():
            v['avg_rotation'] = round(v['total_rot'] / v['count'], 1) if v['count'] else 0
            v['total'] = sector_totals.get(k, v['count'])
            v['pct'] = round(v['count'] / v['total'] * 100, 1) if v['total'] else 0
            del v['total_rot']

        strong_buys.sort(key=lambda x: x['rotation_score'], reverse=True)
        watch.sort(key=lambda x: x['rotation_score'], reverse=True)

        return jsonify({
            'last_scan': last_scan,
            'strong_buys': strong_buys,
            'watch': watch,
            'industry_breakdown': industry_breakdown,
            'sector_breakdown': sector_breakdown
        })
    except FileNotFoundError:
        return jsonify({'error': 'Stock data not found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18791, debug=True)

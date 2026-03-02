from flask import Flask, render_template, jsonify, request
import os
import json
import traceback
import sys
import urllib.request

app = Flask(__name__)

# Supabase Configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://jvgxgfbthfsdqtvzeuqz.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Load from .env file if not set (local dev)
if not SUPABASE_KEY:
    try:
        with open('.env') as f:
            for line in f:
                if line.startswith('SUPABASE_KEY='):
                    SUPABASE_KEY = line.strip().split('=', 1)[1]
    except FileNotFoundError:
        pass

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
    if os.path.exists('data/top_stocks.json'):
        try:
            with open('data/top_stocks.json', 'r') as f:
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
        file_path = os.path.join(os.getcwd(), 'data', 'all_stocks.json')
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

        with open('data/watchlist.json', 'r') as f:
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
        with open('data/watchlist.json', 'r') as f:
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
        with open('data/all_stocks.json', 'r') as f:
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

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Fetch portfolio from Supabase, fall back to portfolio.json"""
    try:
        # Try Supabase first
        url = f'{SUPABASE_URL}/rest/v1/baskets?select=*,holdings(*)&order=sort_order'
        req = urllib.request.Request(url, headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        })
        resp = urllib.request.urlopen(req)
        baskets = json.loads(resp.read())
        
        # Transform to the format the frontend expects
        result = {"baskets": {}}
        for b in baskets:
            result["baskets"][b["name"]] = {
                "id": b["id"],
                "icon": b["icon"],
                "weight": b["weight"],
                "tickers": {h["ticker"]: float(h["position_pct"]) for h in b["holdings"]}
            }
        return jsonify(result)
    except Exception as e:
        # Fall back to JSON file
        try:
            with open('data/portfolio.json') as f:
                return jsonify(json.load(f))
        except FileNotFoundError:
            return jsonify({"error": "Portfolio not found"}), 404
        except Exception as e2:
            return jsonify({"error": str(e2)}), 500

@app.route('/api/portfolio', methods=['POST'])
def save_portfolio():
    """Save portfolio to Supabase, fall back to portfolio.json"""
    try:
        data = request.get_json()
        
        # Try Supabase first
        try:
            # Delete all existing holdings
            req = urllib.request.Request(
                f'{SUPABASE_URL}/rest/v1/holdings?id=gt.0',
                method='DELETE',
                headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
            )
            urllib.request.urlopen(req)
            
            # Delete all baskets
            req = urllib.request.Request(
                f'{SUPABASE_URL}/rest/v1/baskets?id=gt.0',
                method='DELETE',
                headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
            )
            urllib.request.urlopen(req)
            
            # Re-insert baskets and holdings
            for i, (name, basket) in enumerate(data.get('baskets', {}).items()):
                basket_data = json.dumps({
                    "name": name,
                    "icon": basket.get("icon", "📋"),
                    "weight": basket.get("weight", ""),
                    "sort_order": i
                }).encode()
                req = urllib.request.Request(
                    f'{SUPABASE_URL}/rest/v1/baskets',
                    data=basket_data,
                    method='POST',
                    headers={
                        'apikey': SUPABASE_KEY,
                        'Authorization': f'Bearer {SUPABASE_KEY}',
                        'Content-Type': 'application/json',
                        'Prefer': 'return=representation'
                    }
                )
                resp = urllib.request.urlopen(req)
                basket_row = json.loads(resp.read())[0]
                basket_id = basket_row['id']
                
                holdings = [{"basket_id": basket_id, "ticker": t, "position_pct": p} 
                           for t, p in basket.get("tickers", {}).items()]
                if holdings:
                    req = urllib.request.Request(
                        f'{SUPABASE_URL}/rest/v1/holdings',
                        data=json.dumps(holdings).encode(),
                        method='POST',
                        headers={
                            'apikey': SUPABASE_KEY,
                            'Authorization': f'Bearer {SUPABASE_KEY}',
                            'Content-Type': 'application/json'
                        }
                    )
                    urllib.request.urlopen(req)
        except Exception as supabase_error:
            # If Supabase fails, fall back to JSON file
            pass
        
        # Save JSON backup (skip on read-only filesystems like Vercel)
        try:
            with open('data/portfolio.json', 'w') as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist_entries', methods=['GET'])
def get_watchlist_entries():
    """Fetch watchlist entries from Supabase, fall back to JSON"""
    try:
        # Try Supabase first
        url = f'{SUPABASE_URL}/rest/v1/watchlist_entries?select=*&order=created_at.desc'
        req = urllib.request.Request(url, headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        })
        resp = urllib.request.urlopen(req)
        entries = json.loads(resp.read())
        
        # Transform to match frontend expectation
        return jsonify({"entries": [{
            "ticker": e["ticker"],
            "added_date": e["added_date"],
            "entry_price": float(e["entry_price"]),
            "snapshot": e.get("snapshot", {})
        } for e in entries]})
    except Exception as e:
        # Fall back to JSON file
        try:
            with open('data/watchlist_entries.json') as f:
                return jsonify(json.load(f))
        except FileNotFoundError:
            return jsonify({"entries": []})

@app.route('/api/watchlist_entries', methods=['POST'])
def save_watchlist_entries():
    """Save watchlist entries to Supabase, fall back to JSON"""
    try:
        data = request.get_json()
        entries = data.get('entries', [])
        
        # Try Supabase first
        try:
            # Delete all existing
            req = urllib.request.Request(
                f'{SUPABASE_URL}/rest/v1/watchlist_entries?id=gt.0',
                method='DELETE',
                headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
            )
            urllib.request.urlopen(req)
            
            # Insert all
            if entries:
                rows = [{
                    "ticker": e["ticker"],
                    "added_date": e.get("added_date"),
                    "entry_price": e["entry_price"],
                    "snapshot": e.get("snapshot", {})
                } for e in entries]
                req = urllib.request.Request(
                    f'{SUPABASE_URL}/rest/v1/watchlist_entries',
                    data=json.dumps(rows).encode(),
                    method='POST',
                    headers={
                        'apikey': SUPABASE_KEY,
                        'Authorization': f'Bearer {SUPABASE_KEY}',
                        'Content-Type': 'application/json'
                    }
                )
                urllib.request.urlopen(req)
        except Exception as supabase_error:
            # If Supabase fails, fall back to JSON
            pass
        
        # Save JSON backup (skip on read-only filesystems like Vercel)
        try:
            with open('data/watchlist_entries.json', 'w') as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stock_price/<ticker>')
def get_stock_price(ticker):
    """Get current price for a ticker (used when adding to watchlist)"""
    import yfinance as yf
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        
        # Fetch snapshot from all_stocks.json
        snapshot = {}
        try:
            with open('data/all_stocks.json') as f:
                all_data = json.load(f)
            stock_data = all_data.get('stocks', {}).get(ticker.upper(), {})
            if stock_data:
                snapshot = {
                    "name": stock_data.get('name', ticker.upper()),
                    "sector": stock_data.get('sector', ''),
                    "industry": stock_data.get('industry', ''),
                    "score": stock_data.get('score', 0),
                    "grade": stock_data.get('grade', 'N/A'),
                    "rotation_score": stock_data.get('rotation_score', 0),
                    "rotation_signal": stock_data.get('rotation_signal', 'N/A'),
                    "moonshot_score": stock_data.get('moonshot_score', 0),
                    "forward_pe": stock_data.get('forward_pe'),
                    "recommendation": stock_data.get('recommendation', ''),
                    "target_mean": stock_data.get('target_mean')
                }
        except:
            pass
        
        return jsonify({
            "ticker": ticker.upper(),
            "price": round(price, 2) if price else None,
            "name": info.get('longName') or info.get('shortName') or ticker.upper(),
            "snapshot": snapshot
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist_entries/live')
def watchlist_entries_live():
    """Bulk fetch current prices for all watchlist tickers"""
    import yfinance as yf
    try:
        with open('data/watchlist_entries.json') as f:
            data = json.load(f)
        tickers = list(set(e['ticker'] for e in data.get('entries', [])))
        if not tickers:
            return jsonify({"prices": {}})
        
        tickers_obj = yf.Tickers(' '.join(tickers))
        prices = {}
        for t in tickers:
            try:
                info = tickers_obj.tickers[t].info
                curr = info.get('regularMarketPrice') or info.get('currentPrice')
                if curr:
                    prices[t] = round(curr, 2)
            except:
                pass
        return jsonify({"prices": prices})
    except:
        return jsonify({"prices": {}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18791, debug=True)

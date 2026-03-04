from flask import Flask, render_template, jsonify, request
import os
import json
import traceback
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

def fetch_live_prices_bulk(tickers, batch_size=15):
    """Fetch real-time prices using Yahoo spark endpoint (batch, fast).
    range=1d&interval=1m gives true intraday real-time prices.
    chartPreviousClose = yesterday's official close (correct daily change reference).
    """
    results = {}
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        symbols = ','.join(batch)
        url = f'https://query1.finance.yahoo.com/v8/finance/spark?symbols={symbols}&range=1d&interval=1m'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read())
            for sym, info in data.items():
                closes = info.get('close', [])
                curr = closes[-1] if closes else None
                prev = info.get('chartPreviousClose')  # yesterday's official close
                if curr and prev and prev > 0:
                    results[sym] = {
                        "price": round(curr, 2),
                        "previous_close": round(prev, 2),
                        "daily_change": round((curr - prev) / prev * 100, 2)
                    }
        except Exception:
            pass
    return results


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

        data['last_updated'] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M EST")
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Watchlist not generated yet"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist/live')
def watchlist_live():
    """Fetch live prices for all portfolio holdings using lightweight Yahoo API"""
    try:
        
        # Get tickers from Supabase (source of truth), fall back to JSON
        tickers = []
        try:
            url = f'{SUPABASE_URL}/rest/v1/holdings?select=ticker'
            req = urllib.request.Request(url, headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            })
            resp = urllib.request.urlopen(req)
            holdings = json.loads(resp.read())
            tickers = list(set(h['ticker'] for h in holdings))
        except:
            try:
                with open('data/portfolio.json', 'r') as f:
                    data = json.load(f)
                for basket in data.get('baskets', {}).values():
                    tickers.extend(basket.get('tickers', {}).keys())
                tickers = list(set(tickers))
            except:
                pass
        
        if not tickers:
            return jsonify({"error": "No tickers"}), 404

        live = fetch_live_prices_bulk(tickers)

        return jsonify({
            "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S EST"),
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
    """Save portfolio to Supabase using incremental updates (upsert/targeted delete).
    Never wipes everything — only applies the diff: insert new, update changed, delete removed.
    """
    try:
        data = request.get_json()
        sb_headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }

        def sb_get(path):
            req = urllib.request.Request(f'{SUPABASE_URL}{path}', headers=sb_headers)
            return json.loads(urllib.request.urlopen(req).read())

        def sb_post(path, payload, prefer=None):
            h = {**sb_headers}
            if prefer: h['Prefer'] = prefer
            req = urllib.request.Request(f'{SUPABASE_URL}{path}',
                data=json.dumps(payload).encode(), method='POST', headers=h)
            return json.loads(urllib.request.urlopen(req).read())

        def sb_patch(path, payload):
            req = urllib.request.Request(f'{SUPABASE_URL}{path}',
                data=json.dumps(payload).encode(), method='PATCH', headers=sb_headers)
            urllib.request.urlopen(req)

        def sb_delete(path):
            req = urllib.request.Request(f'{SUPABASE_URL}{path}', method='DELETE', headers=sb_headers)
            urllib.request.urlopen(req)

        try:
            # --- Step 1: Get current state from Supabase ---
            existing_baskets = sb_get('/rest/v1/baskets?select=id,name,icon,weight,sort_order')
            existing_map = {b['name']: b for b in existing_baskets}

            incoming_baskets = data.get('baskets', {})
            incoming_names = set(incoming_baskets.keys())
            existing_names = set(existing_map.keys())

            # --- Step 2: Delete removed baskets (cascades to holdings via FK) ---
            for name in existing_names - incoming_names:
                bid = existing_map[name]['id']
                sb_delete(f'/rest/v1/holdings?basket_id=eq.{bid}')
                sb_delete(f'/rest/v1/baskets?id=eq.{bid}')

            # --- Step 3: Upsert each basket + its holdings ---
            for i, (name, basket) in enumerate(incoming_baskets.items()):
                if name in existing_map:
                    # Update existing basket metadata
                    bid = existing_map[name]['id']
                    sb_patch(f'/rest/v1/baskets?id=eq.{bid}', {
                        "icon": basket.get("icon", "📋"),
                        "weight": basket.get("weight", ""),
                        "sort_order": i
                    })
                else:
                    # Insert new basket
                    rows = sb_post('/rest/v1/baskets', {
                        "name": name,
                        "icon": basket.get("icon", "📋"),
                        "weight": basket.get("weight", ""),
                        "sort_order": i
                    }, prefer='return=representation')
                    bid = rows[0]['id']
                    existing_map[name] = {'id': bid}

                # Sync holdings: get current, diff, apply changes
                cur_holdings = sb_get(f'/rest/v1/holdings?basket_id=eq.{bid}&select=id,ticker,position_pct')
                cur_map = {h['ticker']: h for h in cur_holdings}
                new_tickers = basket.get("tickers", {})

                # Delete removed tickers
                for ticker in set(cur_map) - set(new_tickers):
                    sb_delete(f'/rest/v1/holdings?id=eq.{cur_map[ticker]["id"]}')

                # Insert new tickers
                to_insert = [{"basket_id": bid, "ticker": t, "position_pct": p}
                             for t, p in new_tickers.items() if t not in cur_map]
                if to_insert:
                    sb_post('/rest/v1/holdings', to_insert)

                # Update changed position sizes
                for ticker, pct in new_tickers.items():
                    if ticker in cur_map and cur_map[ticker]['position_pct'] != pct:
                        sb_patch(f'/rest/v1/holdings?id=eq.{cur_map[ticker]["id"]}',
                                 {"position_pct": pct})

        except Exception as supabase_error:
            return jsonify({"error": f"Supabase save failed: {str(supabase_error)}"}), 500

        # Save JSON backup locally (skip on read-only filesystems like Vercel)
        try:
            with open('data/portfolio.json', 'w') as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlists', methods=['GET'])
def get_watchlists():
    """Fetch all watchlists with their items from Supabase"""
    try:
        url = f'{SUPABASE_URL}/rest/v1/watchlists?select=*,watchlist_items(*)&order=sort_order'
        req = urllib.request.Request(url, headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        })
        resp = urllib.request.urlopen(req)
        watchlists = json.loads(resp.read())

        # Load scores from all_stocks.json
        all_stocks = {}
        try:
            with open('data/all_stocks.json') as f:
                all_stocks = json.load(f).get('stocks', {})
        except:
            pass

        result = {"watchlists": {}}
        for wl in watchlists:
            items = []
            for item in wl.get('watchlist_items', []):
                scores = all_stocks.get(item['ticker'], {})
                items.append({
                    "id": item["id"],
                    "ticker": item["ticker"],
                    "added_date": item.get("added_date"),
                    "entry_price": float(item["entry_price"]) if item.get("entry_price") else None,
                    "snapshot": item.get("snapshot", {}),
                    "score": scores.get("score", 0),
                    "grade": scores.get("grade", "N/A"),
                    "rotation_score": scores.get("rotation_score", 0),
                    "sector": scores.get("sector", ""),
                    "name": scores.get("name", item["ticker"])
                })
            result["watchlists"][wl["name"]] = {
                "id": wl["id"],
                "icon": wl.get("icon", "👁️"),
                "items": items
            }
        return jsonify(result)
    except Exception as e:
        return jsonify({"watchlists": {}, "error": str(e)})

@app.route('/api/watchlists', methods=['POST'])
def create_watchlist():
    """Create a new watchlist"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        icon = data.get('icon', '👁️')
        if not name:
            return jsonify({"error": "Name required"}), 400

        body = json.dumps({"name": name, "icon": icon}).encode()
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/watchlists',
            data=body, method='POST',
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            }
        )
        resp = urllib.request.urlopen(req)
        row = json.loads(resp.read())[0]
        return jsonify({"status": "ok", "id": row["id"], "name": row["name"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlists/<int:wl_id>', methods=['DELETE'])
def delete_watchlist(wl_id):
    """Delete a watchlist and its items (CASCADE)"""
    try:
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/watchlists?id=eq.{wl_id}',
            method='DELETE',
            headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        )
        urllib.request.urlopen(req)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlists/<int:wl_id>/items', methods=['POST'])
def add_watchlist_item(wl_id):
    """Add a ticker to a watchlist"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        entry_price = data.get('entry_price')
        snapshot = data.get('snapshot', {})
        if not ticker:
            return jsonify({"error": "Ticker required"}), 400

        body = json.dumps({
            "watchlist_id": wl_id,
            "ticker": ticker,
            "entry_price": entry_price,
            "snapshot": snapshot
        }).encode()
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/watchlist_items',
            data=body, method='POST',
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            }
        )
        resp = urllib.request.urlopen(req)
        return jsonify({"status": "ok"})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        if 'duplicate' in err_body.lower() or '23505' in err_body:
            return jsonify({"error": f"{ticker} already in this watchlist"}), 409
        return jsonify({"error": err_body}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlist_items/<int:item_id>', methods=['DELETE'])
def delete_watchlist_item(item_id):
    """Remove a ticker from a watchlist"""
    try:
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/watchlist_items?id=eq.{item_id}',
            method='DELETE',
            headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        )
        urllib.request.urlopen(req)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watchlists/live')
def watchlists_live():
    """Bulk fetch current prices for all watchlist tickers"""
    try:
        url = f'{SUPABASE_URL}/rest/v1/watchlist_items?select=ticker'
        req = urllib.request.Request(url, headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        })
        resp = urllib.request.urlopen(req)
        items = json.loads(resp.read())
        tickers = list(set(i['ticker'] for i in items))
        if not tickers:
            return jsonify({"prices": {}})

        live = fetch_live_prices_bulk(tickers)

        return jsonify({"prices": live, "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S EST")})
    except Exception as e:
        return jsonify({"prices": {}, "error": str(e)})

@app.route('/api/stock_price/<ticker>')
def get_stock_price(ticker):
    """Get current price + snapshot for a ticker"""
    try:
        ticker = ticker.upper()
        price_data = fetch_live_prices_bulk([ticker])
        price = price_data.get(ticker, {}).get('price')

        # Snapshot from all_stocks.json
        snapshot = {}
        try:
            with open('data/all_stocks.json') as f:
                stock_data = json.load(f).get('stocks', {}).get(ticker, {})
            if stock_data:
                snapshot = {
                    "name": stock_data.get('name', ticker),
                    "sector": stock_data.get('sector', ''),
                    "score": stock_data.get('score', 0),
                    "grade": stock_data.get('grade', 'N/A'),
                    "rotation_score": stock_data.get('rotation_score', 0),
                }
        except:
            pass

        return jsonify({
            "ticker": ticker,
            "price": round(price, 2) if price else None,
            "name": snapshot.get("name", ticker),
            "snapshot": snapshot
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18791, debug=True)

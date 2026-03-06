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

def load_insider_scores():
    """Load insider universe scores as a ticker -> {ins_score, insider_signal} lookup"""
    # Try universe scan first (all stocks)
    try:
        with open('data/insider_universe.json') as f:
            data = json.load(f)
        return {t: {'ins_score': d.get('ins_score', 0), 'insider_signal': d.get('signal', 'neutral')}
                for t, d in data.get('signals', {}).items()}
    except Exception:
        pass
    # Fallback: portfolio-only insider scan
    try:
        with open('data/insider_signals.json') as f:
            data = json.load(f)
        return {t: {'ins_score': d.get('ins_score', 0), 'insider_signal': d.get('signal', 'neutral')}
                for t, d in data.get('signals', {}).items()}
    except Exception:
        pass
    # Last fallback: all_stocks.json (if patched)
    try:
        with open('data/all_stocks.json') as f:
            data = json.load(f)
        result = {}
        for t, s in data.get('stocks', {}).items():
            if s.get('ins_score', 0) != 0:
                result[t] = {'ins_score': s['ins_score'], 'insider_signal': s.get('insider_signal', 'neutral')}
        return result
    except Exception:
        return {}


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
    """Serve all_stocks.json for detail view, with insider scores injected"""
    try:
        file_path = os.path.join(os.getcwd(), 'data', 'all_stocks.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        # Inject insider scores into each stock
        ins_lookup = load_insider_scores()
        for ticker, stock in data.get('stocks', {}).items():
            ins = ins_lookup.get(ticker, {})
            stock['ins_score'] = ins.get('ins_score', stock.get('ins_score', 0))
            stock['insider_signal'] = ins.get('insider_signal', stock.get('insider_signal', 'neutral'))
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
    """Serve portfolio from Supabase (always fresh) + scores from all_stocks.json"""
    try:
        # Load scores from all_stocks.json
        all_stocks = {}
        try:
            with open('data/all_stocks.json') as f:
                raw = json.load(f)
            all_stocks = raw.get('stocks', raw)
        except Exception:
            pass

        # Fetch baskets + holdings from Supabase (source of truth)
        sb_headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/baskets?select=name,icon,weight,sort_order,holdings(ticker,position_pct)&order=sort_order',
            headers=sb_headers
        )
        baskets_raw = json.loads(urllib.request.urlopen(req).read())

        all_stocks_list = []
        baskets = {}

        for b in baskets_raw:
            basket_name = b['name']
            basket_meta = {'icon': b.get('icon', '📋'), 'weight': b.get('weight', '')}
            baskets[basket_name] = []

            for h in b.get('holdings', []):
                ticker = h['ticker']
                scores = all_stocks.get(ticker, {})
                stock = {
                    'ticker': ticker,
                    'name': scores.get('name', ticker),
                    'sector': scores.get('sector', ''),
                    'score': scores.get('score', 0),
                    'grade': scores.get('grade', 'N/A'),
                    'technical_score': scores.get('technical_score', 0),
                    'growth_score': scores.get('growth_score', 0),
                    'quality_score': scores.get('quality_score', 0),
                    'context_score': scores.get('context_score', 0),
                    'moonshot_score': scores.get('moonshot_score', 0),
                    'rotation_score': scores.get('rotation_score', 0),
                    'trailing_pe': scores.get('trailing_pe'),
                    'forward_pe': scores.get('forward_pe'),
                    'peg_ratio': scores.get('peg_ratio'),
                    'revenue_growth': scores.get('revenue_growth'),
                    'earnings_growth': scores.get('earnings_growth'),
                    'current_price': scores.get('current_price'),
                    'position_size': h.get('position_pct', 0),
                    'basket': basket_name,
                    'basket_metadata': basket_meta,
                    'price': None,
                    'previous_close': None,
                    'daily_change': None,
                }
                all_stocks_list.append(stock)
                baskets[basket_name].append(stock)

        return jsonify({
            'all': all_stocks_list,
            'baskets': baskets,
            'last_updated': datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M EST")
        })

    except Exception as e:
        # Fallback to cached watchlist.json if Supabase is unavailable
        try:
            with open('data/watchlist.json') as f:
                data = json.load(f)
            data['last_updated'] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M EST")
            return jsonify(data)
        except Exception:
            pass
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
        ins_lookup = load_insider_scores()
        for t in live:
            ins = ins_lookup.get(t, {})
            live[t]['ins_score'] = ins.get('ins_score', 0)
            live[t]['insider_signal'] = ins.get('insider_signal', 'neutral')

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
        ins_lookup = load_insider_scores()

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

            ins = ins_lookup.get(ticker, {})
            obj = {
                'ticker': s.get('ticker', ticker),
                'name': s.get('name', ticker),
                'rotation_score': rot,
                'rotation_signal': s.get('rotation_signal', 'NEUTRAL'),
                'rotation_convergence': s.get('rotation_convergence', 0),
                'rs_rating': s.get('rs_rating', 0),
                'score': s.get('score', 0),
                'grade': s.get('grade', '?'),
                'sector': s.get('sector', 'Unknown'),
                'industry': s.get('industry', 'Unknown'),
                'current_price': s.get('current_price', 0),
                'ins_score': ins.get('ins_score', s.get('ins_score', 0)),
                'insider_signal': ins.get('insider_signal', s.get('insider_signal', 'neutral'))
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

@app.route('/api/insider_signals')
def insider_signals():
    """Serve latest insider transaction signal data"""
    try:
        with open('data/insider_signals.json') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "No insider data yet. Run scripts/insider_scan.py first."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sell_signals')
def sell_signals():
    """Serve latest sell signal data from sell_signals.json"""
    try:
        with open('data/sell_signals.json') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"date": None, "signals": []})
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
        ins_lookup = load_insider_scores()
        # Attach INS to each price entry
        for t in live:
            ins = ins_lookup.get(t, {})
            live[t]['ins_score'] = ins.get('ins_score', 0)
            live[t]['insider_signal'] = ins.get('insider_signal', 'neutral')

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
                ins = load_insider_scores().get(ticker, {})
                snapshot = {
                    "name": stock_data.get('name', ticker),
                    "sector": stock_data.get('sector', ''),
                    "score": stock_data.get('score', 0),
                    "grade": stock_data.get('grade', 'N/A'),
                    "rotation_score": stock_data.get('rotation_score', 0),
                    "ins_score": ins.get('ins_score', stock_data.get('ins_score', 0)),
                    "insider_signal": ins.get('insider_signal', stock_data.get('insider_signal', 'neutral')),
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

@app.route('/api/market_internals')
def market_internals():
    """Market health dashboard: index MAs, VIX, sector performance, breadth"""
    try:
        results = {}

        # --- Index ETFs: SPY, QQQ, IWM with 50d/200d MA ---
        indices = ['SPY', 'QQQ', 'IWM']
        index_data = {}
        for sym in indices:
            try:
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1y&interval=1d'
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=10)
                chart = json.loads(resp.read())
                result = chart.get('chart', {}).get('result', [{}])[0]
                closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
                # Filter out None values for MA calculation
                valid_closes = [c for c in closes if c is not None]
                if valid_closes:
                    current = valid_closes[-1]
                    ma50 = sum(valid_closes[-50:]) / min(len(valid_closes), 50) if len(valid_closes) >= 50 else None
                    ma200 = sum(valid_closes[-200:]) / min(len(valid_closes), 200) if len(valid_closes) >= 200 else None
                    prev = valid_closes[-2] if len(valid_closes) >= 2 else current
                    index_data[sym] = {
                        'price': round(current, 2),
                        'change_pct': round((current - prev) / prev * 100, 2) if prev else 0,
                        'ma50': round(ma50, 2) if ma50 else None,
                        'ma200': round(ma200, 2) if ma200 else None,
                        'above_50': current > ma50 if ma50 else None,
                        'above_200': current > ma200 if ma200 else None,
                    }
            except Exception:
                pass
        results['indices'] = index_data

        # --- VIX ---
        try:
            url = 'https://query1.finance.yahoo.com/v8/finance/spark?symbols=%5EVIX&range=1d&interval=1m'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=8)
            vix_data = json.loads(resp.read())
            vix_closes = vix_data.get('^VIX', {}).get('close', [])
            vix_current = vix_closes[-1] if vix_closes else None
            results['vix'] = round(vix_current, 2) if vix_current else None
        except Exception:
            results['vix'] = None

        # --- Sector ETFs: today's % change ---
        sector_etfs = ['XLK', 'XLF', 'XLE', 'XLI', 'XLV', 'XLB', 'XLRE', 'XLY', 'XLP', 'XLU', 'XLC']
        sector_names = {
            'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
            'XLI': 'Industrials', 'XLV': 'Healthcare', 'XLB': 'Materials',
            'XLRE': 'Real Estate', 'XLY': 'Cons. Disc.', 'XLP': 'Cons. Staples',
            'XLU': 'Utilities', 'XLC': 'Comm. Services'
        }
        sector_prices = fetch_live_prices_bulk(sector_etfs)
        sectors = []
        for etf in sector_etfs:
            p = sector_prices.get(etf)
            if p:
                sectors.append({
                    'ticker': etf,
                    'name': sector_names.get(etf, etf),
                    'price': p['price'],
                    'change': p['daily_change']
                })
        sectors.sort(key=lambda x: x['change'], reverse=True)
        results['sectors'] = sectors

        # --- Breadth: how many of top 20 stocks are up today ---
        breadth_tickers = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'JPM', 'BAC',
                           'XOM', 'CVX', 'HD', 'PG', 'JNJ', 'UNH', 'V', 'MA', 'AVGO', 'ORCL', 'CSCO', 'TXN']
        breadth_prices = fetch_live_prices_bulk(breadth_tickers)
        up_count = sum(1 for t, p in breadth_prices.items() if p.get('daily_change', 0) > 0)
        results['breadth'] = {
            'up': up_count,
            'total': len(breadth_tickers),
            'pct': round(up_count / len(breadth_tickers) * 100, 1)
        }

        # --- O'Neil IBD Market Stage ---
        # Distribution day = index drops ≥0.2% on higher volume than previous day
        # Follow-through day = index gains ≥1.25% on higher volume, day 4+ of rally attempt
        # 0-2 dist = Confirmed Rally, 3-4 = Under Pressure, 5+ = Correction
        try:
            url = 'https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=3mo'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=10)
            spy_chart = json.loads(resp.read())['chart']['result'][0]
            spy_closes = spy_chart['indicators']['quote'][0]['close']
            spy_volumes = spy_chart['indicators']['quote'][0]['volume']

            dist_count = 0
            stall_count = 0
            dist_dates = []
            n = min(26, len(spy_closes))
            for i in range(len(spy_closes) - n + 1, len(spy_closes)):
                if i <= 0:
                    continue
                prev_c, curr_c = spy_closes[i-1], spy_closes[i]
                prev_v, curr_v = spy_volumes[i-1], spy_volumes[i]
                if not all([prev_c, curr_c, prev_v, curr_v]):
                    continue
                pct = (curr_c - prev_c) / prev_c * 100
                if pct <= -0.2 and curr_v > prev_v:
                    dist_count += 1
                elif 0 <= pct < 0.4 and curr_v > prev_v * 1.1:
                    stall_count += 1

            total_dist = dist_count + stall_count

            # Check for follow-through day in last 10 sessions
            ftd = False
            for i in range(-10, 0):
                idx = len(spy_closes) + i
                if idx > 0 and spy_closes[idx] and spy_closes[idx-1] and spy_volumes[idx] and spy_volumes[idx-1]:
                    pct = (spy_closes[idx] - spy_closes[idx-1]) / spy_closes[idx-1] * 100
                    if pct >= 1.25 and spy_volumes[idx] > spy_volumes[idx-1]:
                        ftd = True

            if total_dist >= 5:
                stage = 'MARKET IN CORRECTION'
                stage_color = 'red'
                action = 'Avoid new buys. Raise cash. Protect profits.'
            elif total_dist >= 3:
                stage = 'RALLY UNDER PRESSURE'
                stage_color = 'yellow'
                action = 'Be cautious. Tighten stops. No aggressive buys.'
            elif ftd or total_dist <= 2:
                stage = 'CONFIRMED RALLY'
                stage_color = 'green'
                action = 'Green light for new buys. Follow rotation signals.'
            else:
                stage = 'RALLY ATTEMPT'
                stage_color = 'orange'
                action = 'Market trying to rally. Wait for follow-through day.'

            results['market_stage'] = {
                'stage': stage,
                'color': stage_color,
                'action': action,
                'distribution_days': dist_count,
                'stalling_days': stall_count,
                'total_distribution': total_dist,
                'follow_through_day': ftd,
                'window': '25 sessions'
            }
        except Exception:
            results['market_stage'] = None

        results['timestamp'] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S EST")
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/catalyst_calendar')
def catalyst_calendar():
    """Earnings dates + FOMC schedule — reads from daily cache file"""
    try:
        cache_path = os.path.join(os.path.dirname(__file__), 'data', 'earnings_calendar.json')
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return jsonify(json.load(f))
        else:
            return jsonify({"error": "Calendar cache not found. Run scripts/earnings_calendar.py to generate.", "earnings": [], "fomc": []}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


## ===== THESIS JOURNAL =====
def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else []

def _save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

THESIS_FILE = 'data/trade_theses.json'
JOURNAL_FILE = 'data/trade_journal.json'

@app.route('/api/thesis', methods=['GET'])
def get_theses():
    ticker = request.args.get('ticker', '').upper()
    theses = _load_json(THESIS_FILE, [])
    if ticker:
        theses = [t for t in theses if t.get('ticker') == ticker]
    return jsonify({"theses": theses})

@app.route('/api/thesis', methods=['POST'])
def save_thesis():
    try:
        data = request.get_json()
        required = ['ticker', 'thesis', 'target_price', 'stop_loss']
        for field in required:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        theses = _load_json(THESIS_FILE, [])
        entry = {
            "id": len(theses) + 1,
            "ticker": data['ticker'].upper(),
            "thesis": data['thesis'],
            "target_price": float(data['target_price']),
            "stop_loss": float(data['stop_loss']),
            "entry_price": float(data.get('entry_price', 0)),
            "catalyst": data.get('catalyst', ''),
            "timeline": data.get('timeline', ''),
            "prove_wrong": data.get('prove_wrong', ''),
            "checklist": data.get('checklist', {}),
            "rr_ratio": float(data.get('rr_ratio', 0)),
            "created_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
            "status": "OPEN"
        }
        theses.append(entry)
        _save_json(THESIS_FILE, theses)
        return jsonify({"status": "ok", "id": entry["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

## ===== TRADE JOURNAL =====
@app.route('/api/trade_journal', methods=['GET'])
def get_trade_journal():
    trades = _load_json(JOURNAL_FILE, [])
    # Calculate P&L for each trade
    wins, losses = [], []
    for t in trades:
        if t.get('exit_price') and t.get('entry_price') and t['entry_price'] > 0:
            t['pl_pct'] = round((t['exit_price'] - t['entry_price']) / t['entry_price'] * 100, 2)
            if t['pl_pct'] > 0:
                wins.append(t['pl_pct'])
            else:
                losses.append(t['pl_pct'])
        else:
            t['pl_pct'] = None
        # Days held
        if t.get('entry_date') and t.get('exit_date'):
            try:
                d1 = datetime.strptime(t['entry_date'][:10], '%Y-%m-%d')
                d2 = datetime.strptime(t['exit_date'][:10], '%Y-%m-%d')
                t['days_held'] = (d2 - d1).days
            except:
                t['days_held'] = None
        else:
            t['days_held'] = None

    total_trades = len([t for t in trades if t.get('pl_pct') is not None])
    win_rate = round(len(wins) / total_trades * 100, 1) if total_trades else 0
    avg_win = round(sum(wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(losses) / len(losses), 2) if losses else 0
    gross_wins = sum(wins)
    gross_losses = abs(sum(losses))
    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else float('inf') if gross_wins > 0 else 0
    total_pl = round(sum(t.get('pl_pct', 0) or 0 for t in trades), 2)

    return jsonify({
        "trades": trades,
        "stats": {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "total_pl": total_pl
        }
    })

@app.route('/api/trade_journal', methods=['POST'])
def add_trade():
    try:
        data = request.get_json()
        if not data.get('ticker'):
            return jsonify({"error": "ticker required"}), 400

        trades = _load_json(JOURNAL_FILE, [])
        trade = {
            "id": len(trades) + 1,
            "ticker": data['ticker'].upper(),
            "basket": data.get('basket', ''),
            "action": data.get('action', 'BUY').upper(),
            "entry_price": float(data.get('entry_price', 0)),
            "exit_price": float(data['exit_price']) if data.get('exit_price') else None,
            "quantity_or_pct": data.get('quantity_or_pct', ''),
            "entry_date": data.get('entry_date', datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d')),
            "exit_date": data.get('exit_date'),
            "thesis_id": data.get('thesis_id'),
            "exit_reason": data.get('exit_reason', ''),
            "notes": data.get('notes', ''),
            "created_at": datetime.now(ZoneInfo("America/New_York")).isoformat()
        }
        trades.append(trade)
        _save_json(JOURNAL_FILE, trades)
        return jsonify({"status": "ok", "id": trade["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

## ===== INSIDER ACTIVITY =====
@app.route('/api/insider_activity')
def insider_activity():
    """Fetch insider transactions from Finviz for portfolio tickers"""
    try:
        # Get portfolio tickers
        tickers = []
        try:
            sb_headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
            req = urllib.request.Request(
                f'{SUPABASE_URL}/rest/v1/holdings?select=ticker',
                headers=sb_headers
            )
            holdings = json.loads(urllib.request.urlopen(req).read())
            tickers = list(set(h['ticker'] for h in holdings))
        except:
            pass

        if not tickers:
            return jsonify({"insider_data": [], "cluster_buys": []})

        insider_data = []

        def fetch_insider(ticker):
            results = []
            try:
                url = f'https://finviz.com/quote.ashx?t={ticker}&ty=i'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                resp = urllib.request.urlopen(req, timeout=10)
                html = resp.read().decode('utf-8', errors='ignore')

                # Parse insider table — look for rows with insider data
                import re
                # Find the insider trading table
                insider_section = re.findall(r'insider-row[^>]*>(.*?)</tr>', html, re.DOTALL)
                for row in insider_section[:10]:
                    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                    if len(cells) >= 6:
                        # Clean HTML tags
                        clean = lambda s: re.sub(r'<[^>]+>', '', s).strip()
                        results.append({
                            'ticker': ticker,
                            'insider': clean(cells[0]),
                            'title': clean(cells[1]),
                            'date': clean(cells[2]),
                            'transaction': clean(cells[3]),
                            'shares': clean(cells[4]),
                            'value': clean(cells[5]) if len(cells) > 5 else ''
                        })
            except Exception:
                pass
            return results

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(fetch_insider, t): t for t in tickers[:20]}
            for f in as_completed(futures):
                insider_data.extend(f.result())

        # Detect cluster buys (3+ buys in same ticker in same month)
        from collections import defaultdict
        buy_counts = defaultdict(list)
        for txn in insider_data:
            if 'buy' in txn.get('transaction', '').lower() or 'purchase' in txn.get('transaction', '').lower():
                key = txn['ticker']
                buy_counts[key].append(txn)

        cluster_buys = []
        for ticker, buys in buy_counts.items():
            if len(buys) >= 3:
                cluster_buys.append({
                    'ticker': ticker,
                    'buy_count': len(buys),
                    'insiders': [b['insider'] for b in buys[:5]]
                })

        return jsonify({
            "insider_data": insider_data[:100],
            "cluster_buys": cluster_buys,
            "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S EST")
        })
    except Exception as e:
        return jsonify({"error": str(e), "insider_data": [], "cluster_buys": []}), 500

## ===== PORTFOLIO RISK / CORRELATION =====
@app.route('/api/portfolio_risk')
def portfolio_risk():
    """Calculate portfolio correlation, beta, and drawdown estimates"""
    try:
        # Get portfolio holdings with position sizes
        sb_headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/baskets?select=name,holdings(ticker,position_pct)&order=sort_order',
            headers=sb_headers
        )
        baskets_raw = json.loads(urllib.request.urlopen(req).read())

        basket_tickers = {}
        all_tickers = set()
        holdings_weights = {}
        for b in baskets_raw:
            name = b['name']
            basket_tickers[name] = []
            for h in b.get('holdings', []):
                t = h['ticker']
                basket_tickers[name].append(t)
                all_tickers.add(t)
                holdings_weights[t] = float(h.get('position_pct', 0))

        all_tickers = list(all_tickers)
        if not all_tickers:
            return jsonify({"error": "No holdings found"}), 404

        # Fetch 6-month daily closes for all tickers + SPY
        fetch_tickers = all_tickers + (['SPY'] if 'SPY' not in all_tickers else [])
        returns_data = {}

        def fetch_returns(ticker):
            try:
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1d'
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=10)
                chart = json.loads(resp.read())
                closes = chart.get('chart', {}).get('result', [{}])[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                valid = [c for c in closes if c is not None]
                if len(valid) < 20:
                    return ticker, []
                # Calculate daily returns
                daily_returns = [(valid[i] - valid[i-1]) / valid[i-1] for i in range(1, len(valid))]
                return ticker, daily_returns
            except:
                return ticker, []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_returns, t): t for t in fetch_tickers}
            for f in as_completed(futures):
                ticker, rets = f.result()
                if rets:
                    returns_data[ticker] = rets

        # Calculate basket-level average returns for correlation matrix
        basket_returns = {}
        for name, tickers in basket_tickers.items():
            valid_tickers = [t for t in tickers if t in returns_data]
            if not valid_tickers:
                continue
            min_len = min(len(returns_data[t]) for t in valid_tickers)
            avg_returns = []
            for i in range(min_len):
                avg = sum(returns_data[t][i] for t in valid_tickers) / len(valid_tickers)
                avg_returns.append(avg)
            basket_returns[name] = avg_returns

        # Pairwise correlation between baskets
        def corr(a, b):
            n = min(len(a), len(b))
            if n < 10:
                return None
            a, b = a[:n], b[:n]
            mean_a = sum(a) / n
            mean_b = sum(b) / n
            cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
            std_a = (sum((x - mean_a)**2 for x in a) / n) ** 0.5
            std_b = (sum((x - mean_b)**2 for x in b) / n) ** 0.5
            if std_a == 0 or std_b == 0:
                return None
            return round(cov / (std_a * std_b), 3)

        basket_names = list(basket_returns.keys())
        correlation_matrix = {}
        for i, name_a in enumerate(basket_names):
            correlation_matrix[name_a] = {}
            for j, name_b in enumerate(basket_names):
                if i == j:
                    correlation_matrix[name_a][name_b] = 1.0
                else:
                    c = corr(basket_returns[name_a], basket_returns[name_b])
                    correlation_matrix[name_a][name_b] = c

        # Portfolio beta vs SPY (equal-weight baskets, weighted tickers within each basket)
        spy_returns = returns_data.get('SPY', [])
        portfolio_beta = None
        estimated_drop = None
        basket_betas = {}
        if spy_returns and basket_returns:
            # Calculate per-basket beta
            min_len_spy = len(spy_returns)
            for bname, brets in basket_returns.items():
                ml = min(len(brets), min_len_spy)
                if ml < 20:
                    continue
                mean_b = sum(brets[:ml]) / ml
                mean_s = sum(spy_returns[:ml]) / ml
                cov_bs = sum((brets[i] - mean_b) * (spy_returns[i] - mean_s) for i in range(ml)) / ml
                var_s = sum((x - mean_s)**2 for x in spy_returns[:ml]) / ml
                if var_s > 0:
                    basket_betas[bname] = round(cov_bs / var_s, 3)

            # Portfolio beta = average of basket betas (equal-weight baskets)
            if basket_betas:
                portfolio_beta = round(sum(basket_betas.values()) / len(basket_betas), 2)
                estimated_drop = round(10 * portfolio_beta, 1)

        # Top 5 concentration
        sorted_holdings = sorted(holdings_weights.items(), key=lambda x: x[1], reverse=True)
        top5 = [{"ticker": t, "weight": w} for t, w in sorted_holdings[:5]]
        top5_total = round(sum(w for _, w in sorted_holdings[:5]), 1)

        return jsonify({
            "correlation_matrix": correlation_matrix,
            "basket_names": basket_names,
            "basket_betas": basket_betas,
            "portfolio_beta": portfolio_beta,
            "estimated_drop_10pct": estimated_drop,
            "concentration": {
                "top5": top5,
                "top5_total_pct": top5_total
            },
            "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S EST")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


## ===== SCREENER =====
@app.route('/api/screener')
def screener():
    """Filter all_stocks.json by query params: rotation_min, rotation_max, ins_min, ins_max,
       grades (comma-sep), sector, rs_min, peg_max, sort, order"""
    try:
        with open('data/all_stocks.json') as f:
            data = json.load(f)
        stocks = data.get('stocks', {})
        ins_lookup = load_insider_scores()

        results = []
        for ticker, s in stocks.items():
            ins = ins_lookup.get(ticker, {})
            s['ins_score'] = ins.get('ins_score', s.get('ins_score', 0))
            s['insider_signal'] = ins.get('insider_signal', s.get('insider_signal', 'neutral'))
            s['ticker'] = ticker
            results.append(s)

        # Apply filters
        rot_min = request.args.get('rotation_min', type=float)
        rot_max = request.args.get('rotation_max', type=float)
        ins_min = request.args.get('ins_min', type=float)
        ins_max = request.args.get('ins_max', type=float)
        grades = request.args.get('grades', '')
        sector = request.args.get('sector', '')
        rs_min = request.args.get('rs_min', type=int)
        peg_max = request.args.get('peg_max', type=float)

        if rot_min is not None:
            results = [s for s in results if (s.get('rotation_score') or 0) >= rot_min]
        if rot_max is not None:
            results = [s for s in results if (s.get('rotation_score') or 0) <= rot_max]
        if ins_min is not None:
            results = [s for s in results if (s.get('ins_score') or 0) >= ins_min]
        if ins_max is not None:
            results = [s for s in results if (s.get('ins_score') or 0) <= ins_max]
        if grades:
            grade_set = set(g.strip().upper() for g in grades.split(','))
            results = [s for s in results if s.get('grade', '').upper() in grade_set]
        if sector:
            results = [s for s in results if s.get('sector', '').lower() == sector.lower()]
        if rs_min is not None:
            results = [s for s in results if (s.get('rs_rating') or 0) >= rs_min]
        if peg_max is not None:
            results = [s for s in results if s.get('peg_ratio') is not None and s['peg_ratio'] <= peg_max]

        # Sort
        sort_key = request.args.get('sort', 'rotation_score')
        sort_order = request.args.get('order', 'desc')
        results.sort(
            key=lambda x: x.get(sort_key) if x.get(sort_key) is not None else -9999,
            reverse=(sort_order == 'desc')
        )

        return jsonify({
            'results': results[:200],
            'total': len(results),
            'timestamp': datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M EST")
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


## ===== ALERTS =====
ALERTS_FILE = 'data/alerts.json'

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    alerts = _load_json(ALERTS_FILE, [])
    return jsonify({'alerts': alerts})

@app.route('/api/alerts', methods=['POST'])
def create_alert():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        atype = data.get('type', '')
        threshold = data.get('threshold')
        if not ticker or not atype or threshold is None:
            return jsonify({'error': 'ticker, type, and threshold required'}), 400

        alerts = _load_json(ALERTS_FILE, [])
        alert = {
            'id': len(alerts) + 1,
            'ticker': ticker,
            'type': atype,
            'threshold': float(threshold),
            'triggered': False,
            'triggered_at': None,
            'current_value': None,
            'created_at': datetime.now(ZoneInfo("America/New_York")).isoformat()
        }
        alerts.append(alert)
        _save_json(ALERTS_FILE, alerts)
        return jsonify({'status': 'ok', 'alert': alert})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/<int:alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    try:
        alerts = _load_json(ALERTS_FILE, [])
        alerts = [a for a in alerts if a.get('id') != alert_id]
        _save_json(ALERTS_FILE, alerts)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


## ===== REPORT CARD =====
@app.route('/api/report/<ticker>')
def stock_report(ticker):
    """Full report card data for a single stock"""
    try:
        ticker = ticker.upper()
        with open('data/all_stocks.json') as f:
            data = json.load(f)
        stock = data.get('stocks', {}).get(ticker)
        if not stock:
            return jsonify({'error': f'{ticker} not found'}), 404

        ins = load_insider_scores().get(ticker, {})
        stock['ins_score'] = ins.get('ins_score', stock.get('ins_score', 0))
        stock['insider_signal'] = ins.get('insider_signal', stock.get('insider_signal', 'neutral'))
        stock['ticker'] = ticker
        return jsonify(stock)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


## ===== DASHBOARD SUMMARY =====
@app.route('/api/dashboard_summary')
def dashboard_summary():
    """Returns market indices (with MAs), VIX, TNX, sectors for dashboard command center"""
    indices = ['SPY', 'QQQ', 'IWM', 'DIA']
    sectors = {
        'Technology': 'XLK', 'Financials': 'XLF', 'Energy': 'XLE',
        'Healthcare': 'XLV', 'Industrials': 'XLI', 'Materials': 'XLB',
        'Real Estate': 'XLRE', 'Consumer Disc.': 'XLY', 'Consumer Staples': 'XLP',
        'Utilities': 'XLU', 'Communication': 'XLC'
    }
    indicators = {'^VIX': '%5EVIX', '^TNX': '%5ETNX'}

    # --- Sector ETFs via spark (fast) ---
    sector_tickers = list(sectors.values())
    results = {}
    for i in range(0, len(sector_tickers), 15):
        batch = sector_tickers[i:i+15]
        symbols = ','.join(batch)
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/spark?symbols={symbols}&range=1d&interval=1m'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read())
            for sym, info in data.items():
                closes = info.get('close', [])
                curr = closes[-1] if closes else None
                prev = info.get('chartPreviousClose')
                if curr and prev and prev > 0:
                    results[sym] = {
                        'price': round(curr, 2),
                        'change_pct': round((curr - prev) / prev * 100, 2),
                        'prev_close': round(prev, 2)
                    }
        except Exception:
            pass

    # --- Indices via chart endpoint (gives 1y data for MA calculation) ---
    index_data = {}
    for sym in indices:
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1y&interval=1d'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=10)
            chart = json.loads(resp.read())
            result = chart.get('chart', {}).get('result', [{}])[0]
            closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
            valid_closes = [c for c in closes if c is not None]
            if valid_closes:
                current = valid_closes[-1]
                ma50 = sum(valid_closes[-50:]) / min(len(valid_closes), 50) if len(valid_closes) >= 50 else None
                ma200 = sum(valid_closes[-200:]) / min(len(valid_closes), 200) if len(valid_closes) >= 200 else None
                prev = valid_closes[-2] if len(valid_closes) >= 2 else current
                index_data[sym] = {
                    'price': round(current, 2),
                    'change_pct': round((current - prev) / prev * 100, 2) if prev else 0,
                    'prev_close': round(prev, 2),
                    'ma50': round(ma50, 2) if ma50 else None,
                    'ma200': round(ma200, 2) if ma200 else None,
                    'above_50': current > ma50 if ma50 else None,
                    'above_200': current > ma200 if ma200 else None,
                }
        except Exception:
            pass

    # --- Indicators (^VIX, ^TNX) via chart endpoint ---
    for display_name, encoded in indicators.items():
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=1d&interval=1m'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read())['chart']['result'][0]
            meta = data['meta']
            price = meta.get('regularMarketPrice', 0)
            prev = meta.get('chartPreviousClose', price)
            change_pct = round((price - prev) / prev * 100, 2) if prev else 0
            results[display_name] = {
                'price': round(price, 2),
                'change_pct': change_pct,
                'prev_close': round(prev, 2)
            }
        except Exception:
            results[display_name] = {'price': 0, 'change_pct': 0, 'prev_close': 0}

    return jsonify({
        'indices': {t: index_data.get(t, {'price': 0, 'change_pct': 0, 'prev_close': 0}) for t in indices},
        'sectors': {name: {'ticker': etf, **results.get(etf, {'price': 0, 'change_pct': 0, 'prev_close': 0})} for name, etf in sectors.items()},
        'indicators': {t: results.get(t, {'price': 0, 'change_pct': 0, 'prev_close': 0}) for t in indicators}
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18791, debug=True)

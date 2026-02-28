import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join(os.getcwd(), 'market_data.db')

class MarketDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()
        
        # Tickers Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickers (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                industry TEXT,
                last_updated DATE
            )
        ''')

        # Price History Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                symbol TEXT,
                date DATE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (symbol, date),
                FOREIGN KEY (symbol) REFERENCES tickers (symbol)
            )
        ''')

        # Fundamentals Cache Table (JSON blob for flexibility)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fundamentals (
                symbol TEXT PRIMARY KEY,
                data JSON,
                updated_at DATETIME,
                FOREIGN KEY (symbol) REFERENCES tickers (symbol)
            )
        ''')
        
        self.conn.commit()

    def get_fundamentals(self, symbol):
        # Return cached fundamentals if < 24h old
        cursor = self.conn.cursor()
        cursor.execute("SELECT data, updated_at FROM fundamentals WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        
        if row:
            import json
            data = json.loads(row[0])
            updated_at = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - updated_at < timedelta(hours=24):
                return data
        return None

    def save_fundamentals(self, symbol, data_dict):
        import json
        cursor = self.conn.cursor()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        json_str = json.dumps(data_dict)
        
        cursor.execute('''
            INSERT INTO fundamentals (symbol, data, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET data = ?, updated_at = ?
        ''', (symbol, json_str, now_str, json_str, now_str))
        self.conn.commit()


    def get_history(self, symbol, period="1y", start_date=None):
        """
        Get price history for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            period: Time period (backward compatibility, not used with start_date)
            start_date: Optional start date filter (default: 1 year ago)
                       Can be datetime.date, datetime, or string 'YYYY-MM-DD'
        
        Returns:
            DataFrame with OHLCV data, or None if no data found
        """
        # Default start_date to 1 year ago if not provided
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).date()
        
        # Convert start_date to string format for SQL
        if isinstance(start_date, datetime):
            start_date_str = start_date.strftime('%Y-%m-%d')
        elif hasattr(start_date, 'strftime'):  # datetime.date
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = str(start_date)
        
        query = "SELECT date, open, high, low, close, volume FROM prices WHERE symbol = ? AND date >= ? ORDER BY date ASC"
        df = pd.read_sql(query, self.conn, params=(symbol, start_date_str), parse_dates=['date'])
        
        if df.empty:
            return None
            
        df.set_index('date', inplace=True)
        df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        }, inplace=True)
        return df

    def get_history_smart(self, symbol, days_needed=250):
        """
        Database-first history fetch. 
        If DB data is stale or missing, fetches incremental from YF.
        """
        # 1. Try to get from DB
        df = self.get_history(symbol)
        
        last_date = None
        if df is not None and not df.empty:
            last_date = df.index.max().date()
            
        today = datetime.now().date()
        
        # If we have data and it's from today (or Friday if it's the weekend), we're good
        # Simplified: if last_date is today, don't fetch.
        if last_date == today:
            return df
            
        # 2. Fetch incremental from YF
        try:
            ticker_obj = yf.Ticker(symbol)
            if last_date:
                # Fetch only new days
                start_fetch = last_date + timedelta(days=1)
                new_data = ticker_obj.history(start=start_fetch)
            else:
                # Full fetch (9 months as optimized earlier)
                new_data = ticker_obj.history(period="9mo")
                
            if not new_data.empty:
                # Save new data to DB (if on Mac Mini / writable env)
                try:
                    self._save_prices(symbol, new_data)
                except Exception as e:
                    # On Vercel, this will fail (read-only), which is fine.
                    pass
                
                # Combine
                if df is not None:
                    # Clean new_data columns to match YF standard
                    if isinstance(new_data.columns, pd.MultiIndex):
                        new_data.columns = new_data.columns.get_level_values(0)
                    
                    # Ensure indices are just dates for comparison
                    new_data.index = pd.to_datetime(new_data.index).tz_localize(None)
                    df.index = pd.to_datetime(df.index).tz_localize(None)
                    
                    combined = pd.concat([df, new_data])
                    # Remove duplicates if any
                    combined = combined[~combined.index.duplicated(keep='last')]
                    return combined.sort_index()
                else:
                    return new_data
                    
            return df # Fallback to what we have if YF fails
        except:
            return df

    def _save_prices(self, symbol, data):
        cursor = self.conn.cursor()
        data_to_save = data.copy()
        data_to_save.reset_index(inplace=True)
        
        # Normalize columns
        if 'Date' not in data_to_save.columns and 'date' not in data_to_save.columns:
            # Handle index being named something else
            data_to_save.rename(columns={data_to_save.columns[0]: 'Date'}, inplace=True)

        records = []
        for _, r in data_to_save.iterrows():
            d_str = r['Date'].strftime('%Y-%m-%d') if hasattr(r['Date'], 'strftime') else str(r['Date'])[:10]
            records.append((
                symbol, d_str, r['Open'], r['High'], r['Low'], r['Close'], r['Volume']
            ))
        
        cursor.executemany('''
            INSERT OR IGNORE INTO prices (symbol, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', records)
        
        last_entry_date = data_to_save['Date'].max()
        if hasattr(last_entry_date, 'strftime'):
            last_entry_date = last_entry_date.strftime('%Y-%m-%d')
        else:
            last_entry_date = str(last_entry_date)[:10]

        cursor.execute('''
            INSERT INTO tickers (symbol, last_updated) VALUES (?, ?)
            ON CONFLICT(symbol) DO UPDATE SET last_updated = ?
        ''', (symbol, last_entry_date, last_entry_date))
        self.conn.commit()

    def update_ticker(self, symbol):
        cursor = self.conn.cursor()
        
        # Check last update
        cursor.execute("SELECT last_updated FROM tickers WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        
        start_date = None
        if row and row[0]:
            last_date = datetime.strptime(row[0], '%Y-%m-%d').date()
            # If updated today or yesterday (depending on market close), maybe skip?
            # For now, just try to fetch from next day.
            start_date = last_date + timedelta(days=1)
            if start_date > datetime.now().date():
                return # Already up to date
        
        # Fetch Data
        try:
            # yfinance expects string dates
            ticker_obj = yf.Ticker(symbol)
            
            if start_date:
                # Incremental Update
                data = ticker_obj.history(start=start_date)
            else:
                # Full Download (1y default for now, or max)
                # User asked for 6m lookback logic, so we need at least 1y to be safe.
                data = ticker_obj.history(period="2y")
            
            if data.empty:
                return

            # Clean Data for Insert
            data.reset_index(inplace=True)
            # Ensure columns exist (Date, Open, High, Low, Close, Volume)
            # YF sometimes returns different cases or Datetime with timezone
            
            # Normalize Date
            data['Date'] = data['Date'].dt.date.astype(str)
            
            records = []
            for _, r in data.iterrows():
                records.append((
                    symbol, 
                    r['Date'], 
                    r['Open'], r['High'], r['Low'], r['Close'], r['Volume']
                ))
            
            # Upsert Prices
            cursor.executemany('''
                INSERT OR IGNORE INTO prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', records)
            
            # Update Ticker Timestamp
            last_entry_date = data['Date'].max()
            cursor.execute('''
                INSERT INTO tickers (symbol, last_updated) VALUES (?, ?)
                ON CONFLICT(symbol) DO UPDATE SET last_updated = ?
            ''', (symbol, last_entry_date, last_entry_date))
            
            self.conn.commit()
            return True # Updated
            
        except Exception as e:
            print(f"DB Update Error {symbol}: {e}")
            return False

    def close(self):
        self.conn.close()

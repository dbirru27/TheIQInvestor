"""
Shared data fetcher with in-memory TTL cache.
Prevents multiple scripts from hammering YFinance for the same data.
"""
import yfinance as yf
import threading
import time
from datetime import datetime
import pandas as pd

try:
    from utils.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

# Global cache and lock
_cache = {}
_lock = threading.Lock()

def _is_cache_valid(cache_entry, max_age_seconds):
    """Check if a cache entry is still valid."""
    if cache_entry is None:
        return False
    
    age = time.time() - cache_entry['timestamp']
    return age < max_age_seconds

def get_quote(ticker, max_age_seconds=300):
    """
    Get quote for a single ticker with TTL cache.
    
    Args:
        ticker: Stock ticker symbol
        max_age_seconds: Maximum cache age in seconds (default: 5 minutes)
    
    Returns:
        dict with keys: price, prev_close, change_pct, volume, timestamp
        None if fetch fails
    """
    cache_key = f"quote:{ticker}"
    
    with _lock:
        # Check cache
        if cache_key in _cache and _is_cache_valid(_cache[cache_key], max_age_seconds):
            logger.debug(f"Cache hit for {ticker}")
            return _cache[cache_key]['data']
    
    # Cache miss - fetch fresh data
    logger.debug(f"Cache miss for {ticker}, fetching from YFinance")
    
    try:
        t = yf.Ticker(ticker)
        
        # Try fast_info first (faster)
        try:
            info = t.fast_info
            price = info.last_price
            prev_close = info.previous_close
            
            # Try to get volume from fast_info if available
            try:
                volume = info.last_volume
            except:
                volume = None
        except Exception as e:
            logger.debug(f"fast_info failed for {ticker}, trying history: {e}")
            
            # Fallback to history
            hist = t.history(period="2d")
            
            if hist.empty or len(hist) < 1:
                logger.warning(f"No history data for {ticker}")
                return None
            
            price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else price
            volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns else None
        
        # Calculate change
        if prev_close and prev_close != 0:
            change_pct = ((price - prev_close) / prev_close) * 100
        else:
            change_pct = 0.0
        
        # Build quote dict
        quote = {
            'price': float(price),
            'prev_close': float(prev_close),
            'change_pct': float(change_pct),
            'volume': int(volume) if volume else None,
            'timestamp': time.time()
        }
        
        # Store in cache
        with _lock:
            _cache[cache_key] = {
                'data': quote,
                'timestamp': time.time()
            }
        
        logger.debug(f"Fetched and cached {ticker}: ${price:.2f} ({change_pct:+.2f}%)")
        return quote
        
    except Exception as e:
        logger.error(f"Error fetching quote for {ticker}: {e}")
        return None

def get_quotes(tickers, max_age_seconds=300):
    """
    Batch fetch quotes for multiple tickers.
    
    Args:
        tickers: List of ticker symbols
        max_age_seconds: Maximum cache age in seconds
    
    Returns:
        dict mapping ticker -> quote dict
        Missing/failed tickers will have None values
    """
    logger.info(f"Fetching quotes for {len(tickers)} tickers")
    
    results = {}
    
    for ticker in tickers:
        quote = get_quote(ticker, max_age_seconds)
        results[ticker] = quote
    
    success_count = sum(1 for q in results.values() if q is not None)
    logger.info(f"Successfully fetched {success_count}/{len(tickers)} quotes")
    
    return results

def get_history(ticker, period="1y", max_age_seconds=3600):
    """
    Get historical data for a ticker with TTL cache.
    
    Args:
        ticker: Stock ticker symbol
        period: Time period (e.g., "1d", "5d", "1mo", "1y")
        max_age_seconds: Maximum cache age in seconds (default: 1 hour)
    
    Returns:
        pandas DataFrame with historical data
        None if fetch fails
    """
    cache_key = f"history:{ticker}:{period}"
    
    with _lock:
        # Check cache
        if cache_key in _cache and _is_cache_valid(_cache[cache_key], max_age_seconds):
            logger.debug(f"Cache hit for history {ticker} ({period})")
            return _cache[cache_key]['data']
    
    # Cache miss - fetch fresh data
    logger.debug(f"Cache miss for history {ticker} ({period}), fetching from YFinance")
    
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        
        if hist.empty:
            logger.warning(f"No history data for {ticker} ({period})")
            return None
        
        # Store in cache
        with _lock:
            _cache[cache_key] = {
                'data': hist.copy(),
                'timestamp': time.time()
            }
        
        logger.debug(f"Fetched and cached history for {ticker}: {len(hist)} rows")
        return hist
        
    except Exception as e:
        logger.error(f"Error fetching history for {ticker}: {e}")
        return None

def clear_cache():
    """Clear all cached data."""
    with _lock:
        _cache.clear()
    logger.info("Cache cleared")

def get_cache_stats():
    """Get cache statistics."""
    with _lock:
        total_entries = len(_cache)
        quote_entries = sum(1 for k in _cache.keys() if k.startswith('quote:'))
        history_entries = sum(1 for k in _cache.keys() if k.startswith('history:'))
        
        return {
            'total_entries': total_entries,
            'quote_entries': quote_entries,
            'history_entries': history_entries
        }

if __name__ == "__main__":
    # Test the data fetcher
    print("Testing data_fetcher.py")
    print("-" * 50)
    
    # Test single quote
    print("\n1. Testing get_quote('SPY'):")
    quote = get_quote('SPY')
    if quote:
        print(f"   Price: ${quote['price']:.2f}")
        print(f"   Change: {quote['change_pct']:+.2f}%")
        print(f"   Volume: {quote['volume']:,}" if quote['volume'] else "   Volume: N/A")
    else:
        print("   Failed to fetch quote")
    
    # Test batch quotes
    print("\n2. Testing get_quotes(['SPY', 'QQQ', 'IWM']):")
    quotes = get_quotes(['SPY', 'QQQ', 'IWM'])
    for ticker, q in quotes.items():
        if q:
            print(f"   {ticker}: ${q['price']:.2f} ({q['change_pct']:+.2f}%)")
        else:
            print(f"   {ticker}: Failed")
    
    # Test cache hit
    print("\n3. Testing cache (should be instant):")
    start = time.time()
    quote2 = get_quote('SPY')
    elapsed = time.time() - start
    print(f"   Fetched in {elapsed*1000:.1f}ms (cached)")
    
    # Test history
    print("\n4. Testing get_history('SPY', '5d'):")
    hist = get_history('SPY', '5d')
    if hist is not None:
        print(f"   Retrieved {len(hist)} days of data")
        print(f"   Latest close: ${hist['Close'].iloc[-1]:.2f}")
    else:
        print("   Failed to fetch history")
    
    # Cache stats
    print("\n5. Cache statistics:")
    stats = get_cache_stats()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Quote entries: {stats['quote_entries']}")
    print(f"   History entries: {stats['history_entries']}")
    
    print("\n✓ Data fetcher tests complete")

import pandas as pd
import yfinance as yf
from flask_caching import Cache

# Use FileSystemCache which is persistent and can be shared between processes
cache = Cache(config={'CACHE_TYPE': 'FileSystemCache', 'CACHE_DIR': 'flask_cache'})

STOCK_UNIVERSES = {
    "NIFTY_50": [
        'ADANIENT', 'ADANIPORTS', 'APOLLOHOSP', 'ASIANPAINT', 'AXISBANK', 'BAJAJ-AUTO', 'BAJFINANCE',
        'BAJAJFINSV', 'BPCL', 'BHARTIARTL', 'BRITANNIA', 'CIPLA', 'COALINDIA', 'DIVISLAB', 'DRREDDY',
        'EICHERMOT', 'GRASIM', 'HCLTECH', 'HDFCBANK', 'HDFCLIFE', 'HEROMOTOCO', 'HINDALCO', 'HINDUNILVR',
        'ICICIBANK', 'ITC', 'INDUSINDBK', 'INFY', 'JSWSTEEL', 'KOTAKBANK', 'LTIM', 'LT', 'M&M',
        'MARUTI', 'NTPC', 'NESTLEIND', 'ONGC', 'POWERGRID', 'RELIANCE', 'SBILIFE', 'SBIN', 'SUNPHARMA',
        'TCS', 'TATACONSUM', 'TATAMOTORS', 'TATASTEEL', 'TECHM', 'TITAN', 'UPL', 'ULTRACEMCO', 'WIPRO'
    ],
    "NIFTY_NEXT_50": [
        'ACC', 'ADANIENSOL', 'ADANIGREEN', 'AMBUJACEM', 'DMART', 'BAJAJHLDNG', 'BANKBARODA', 'BERGEPAINT', 'BEL',
        'BOSCHLTD', 'CHOLAFIN', 'COLPAL', 'DLF', 'DABUR', 'GAIL', 'GODREJCP', 'HAVELLS', 'HAL', 'ICICIGI',
        'ICICIPRULI', 'IOC', 'IGL', 'INDIGO', 'JSWENERGY', 'LICI', 'MARICO', 'MOTHERSON', 'MUTHOOTFIN',
        'NAUKRI', 'PIDILITIND', 'PEL', 'PNB', 'PGHH', 'SIEMENS', 'SBICARD', 'SHREECEM', 'SRF',
        'TATAPOWER', 'TVSMOTOR', 'TRENT', 'VEDL', 'VBL', 'ZEEL', 'ZOMATO'
    ]
}

@cache.memoize(timeout=43200) # Cache data for 12 hours
def get_historical_data(symbol, start_date, end_date):
    """
    Fetches historical data for a stock AND the Nifty index together.
    This creates a self-contained DataFrame with Relative_Strength pre-calculated.
    This is the original, robust logic.
    """
    ticker_symbol_ns = f"{symbol}.NS"
    nifty_symbol = "^NSEI"
    
    print(f"Fetching data for {ticker_symbol_ns} and {nifty_symbol} from {start_date} to {end_date}")
    try:
        # Download both tickers at once. yfinance returns a multi-level column DataFrame.
        all_data = yf.download([ticker_symbol_ns, nifty_symbol], start=start_date, end=end_date, progress=False, auto_adjust=True)

        # Check for valid data
        if ticker_symbol_ns not in all_data['Close'].columns or all_data['Close'][ticker_symbol_ns].isnull().all():
             print(f"--> WARNING: Data for {ticker_symbol_ns} could not be downloaded. Skipping.")
             return pd.DataFrame()

        # Extract just the stock's OHLCV data by selecting its column level
        stock_data = all_data.loc[:, (slice(None), ticker_symbol_ns)].copy()
        stock_data.columns = stock_data.columns.droplevel(1) # Flatten the multi-level columns
        
        # Calculate Relative Strength using the full downloaded data
        stock_close = all_data['Close'][ticker_symbol_ns]
        nifty_close = all_data['Close'][nifty_symbol]
        stock_data['Relative_Strength'] = (stock_close / nifty_close)
        
        # Fetch and add sector information
        try:
            ticker_info = yf.Ticker(ticker_symbol_ns).info
            stock_data['Sector'] = ticker_info.get('sector', 'Unknown')
        except Exception:
            stock_data['Sector'] = 'Unknown'
        
        # Drop rows where essential data might be missing
        return stock_data.dropna(subset=['Open', 'High', 'Low', 'Close', 'Relative_Strength'])

    except Exception as e:
        print(f"--> CRITICAL ERROR fetching data for {ticker_symbol_ns}: {e}")
        return pd.DataFrame()

def get_stock_universe(universe_name="NIFTY_50"):
    return STOCK_UNIVERSES.get(universe_name, [])
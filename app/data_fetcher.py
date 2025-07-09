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

# --- MODIFIED SECTION ---
# Add the memoize decorator to cache the results of this function.
# Timeout is set to 12 hours (43200 seconds).
@cache.memoize(timeout=43200)
def get_historical_data(symbol, start_date, end_date):
    """
    Fetches historical data. Handles both individual stocks (e.g., 'RELIANCE')
    and index symbols (e.g., '^NSEI') correctly.
    """
    nifty_symbol = "^NSEI" # The benchmark is always NIFTY 50

    # --- START OF MODIFIED LOGIC ---
    # Check if the requested symbol is an index or a stock
    if symbol.startswith('^'):
        # If it's an index, it's the only ticker we need to download.
        ticker_to_download_main = symbol
        tickers_for_yfinance = [ticker_to_download_main]
    else:
        # If it's a stock, append .NS and download it along with the NIFTY benchmark
        ticker_to_download_main = f"{symbol}.NS"
        tickers_for_yfinance = [ticker_to_download_main, nifty_symbol]
    # --- END OF MODIFIED LOGIC ---
    
    print(f"--- [CACHE MISS] Fetching fresh data for {tickers_for_yfinance} from {start_date} to {end_date} ---")
    
    try:
        all_data = yf.download(tickers_for_yfinance, start=start_date, end=end_date, progress=False, auto_adjust=True)

        # Handle cases where data is not available
        if isinstance(all_data.columns, pd.MultiIndex):
            # If multiple tickers were downloaded, check the main one
            if ticker_to_download_main not in all_data['Close'].columns or all_data['Close'][ticker_to_download_main].isnull().all():
                print(f"--> WARNING: Data for {ticker_to_download_main} could not be downloaded. Skipping.")
                return pd.DataFrame()
        elif all_data.empty:
            print(f"--> WARNING: Data for {ticker_to_download_main} could not be downloaded. Skipping.")
            return pd.DataFrame()

        # Data cleaning
        all_data.index = pd.to_datetime(all_data.index)
        if not all_data.index.is_unique:
            all_data = all_data.loc[~all_data.index.duplicated(keep='first')]
        all_data.sort_index(inplace=True)

        # If we downloaded multiple tickers, extract the main one and calculate relative strength
        if isinstance(all_data.columns, pd.MultiIndex):
            stock_data = all_data.loc[:, (slice(None), ticker_to_download_main)].copy()
            stock_data.columns = stock_data.columns.droplevel(1)
            stock_close = all_data['Close'][ticker_to_download_main]
            nifty_close = all_data['Close'][nifty_symbol]
            stock_data['Relative_Strength'] = (stock_close / nifty_close)
        else:
            # If we only downloaded one ticker (an index), just use it
            stock_data = all_data.copy()
            stock_data['Relative_Strength'] = 1.0 # An index has a relative strength of 1 to itself

        # Add Sector Info (will be 'Unknown' for an index, which is fine)
        try:
            ticker_info = yf.Ticker(ticker_to_download_main).info
            stock_data['Sector'] = ticker_info.get('sector', 'Unknown')
        except Exception:
            stock_data['Sector'] = 'Unknown'
        
        return stock_data.dropna(subset=['Open', 'High', 'Low', 'Close'])

    except Exception as e:
        print(f"--> CRITICAL ERROR fetching data for {ticker_to_download_main}: {e}")
        return pd.DataFrame()

def get_stock_universe(universe_name="NIFTY_50"):
    return STOCK_UNIVERSES.get(universe_name, [])
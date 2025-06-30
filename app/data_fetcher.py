# app/data_fetcher.py (Corrected and Robust Version)

import pandas as pd
import yfinance as yf
from flask_caching import Cache
from datetime import date

# Use FileSystemCache to share data between the training script and the web app
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
    ticker_symbol_ns = f"{symbol}.NS"
    nifty_symbol = "^NSEI"
    
    print(f"Fetching data for {ticker_symbol_ns} and {nifty_symbol} from {start_date} to {end_date}")
    try:
        # ** THE FIX: Reverted to a single, combined download call **
        all_data = yf.download([ticker_symbol_ns, nifty_symbol], start=start_date, end=end_date, progress=False, auto_adjust=True)

        # Check if the primary stock data was downloaded successfully
        if ticker_symbol_ns not in all_data['Close'].columns or all_data['Close'][ticker_symbol_ns].isnull().all():
             print(f"--> WARNING: Data for {ticker_symbol_ns} could not be downloaded. Skipping.")
             return pd.DataFrame()

        # Extract the OHLCV data for the specific stock
        stock_data = all_data.loc[:, (slice(None), ticker_symbol_ns)].copy()
        stock_data.columns = stock_data.columns.droplevel(1) # Remove the multi-index level
        
        # Extract Close prices for relative strength calculation
        stock_close = all_data['Close'][ticker_symbol_ns]
        nifty_close = all_data['Close'][nifty_symbol]
        
        # Calculate and assign the Relative Strength
        stock_data['Relative_Strength'] = (stock_close / nifty_close)
        
        # Fetch and add sector information
        try:
            ticker_info = yf.Ticker(ticker_symbol_ns).info
            stock_data['Sector'] = ticker_info.get('sector', 'Unknown')
        except Exception:
            stock_data['Sector'] = 'Unknown'
        
        # Drop any rows with NaN values that might have been created
        return stock_data.dropna()

    except Exception as e:
        print(f"--> CRITICAL ERROR fetching data for {ticker_symbol_ns}: {e}")
        return pd.DataFrame()

def get_stock_universe(universe_name="NIFTY_50"):
    return STOCK_UNIVERSES.get(universe_name, [])
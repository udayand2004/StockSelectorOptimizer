import pandas as pd
import sqlite3
from .config import DB_FILE, STOCK_UNIVERSES

def get_stock_universe(universe_name="NIFTY_50"):
    return STOCK_UNIVERSES.get(universe_name, [])

def get_historical_data(symbol, start_date, end_date):
    """
    Fetches historical data for a given symbol and date range FROM THE DATABASE.
    This version contains the definitive fix for the benchmark data issue.
    """
    start_str = pd.to_datetime(start_date).strftime('%Y-%m-%d')
    end_str = pd.to_datetime(end_date).strftime('%Y-%m-%d')
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # Query for the requested symbol's price data
            query = "SELECT * FROM historical_prices WHERE Symbol = ? AND Date BETWEEN ? AND ?"
            stock_df = pd.read_sql_query(query, conn, params=(symbol, start_str, end_str))

            if stock_df.empty:
                return pd.DataFrame()

            # --- Data Cleaning and Formatting ---
            stock_df['Date'] = pd.to_datetime(stock_df['Date'])
            stock_df.set_index('Date', inplace=True)

            # --- Logic for Relative Strength and Sector ---
            if symbol == '^NSEI':
                # If the requested symbol is the benchmark itself:
                # Relative strength is 1, Sector is 'Index'
                stock_df['Relative_Strength'] = 1.0
                stock_df['Sector'] = 'Index'
            else:
                # If it's a regular stock, we need to fetch Nifty data to compare.
                nifty_query = "SELECT Date, Close FROM historical_prices WHERE Symbol = '^NSEI' AND Date BETWEEN ? AND ?"
                nifty_df = pd.read_sql_query(nifty_query, conn, params=(start_str, end_str))
                
                if not nifty_df.empty:
                    nifty_df['Date'] = pd.to_datetime(nifty_df['Date'])
                    nifty_df.set_index('Date', inplace=True)
                    nifty_df.rename(columns={'Close': 'Nifty_Close'}, inplace=True)
                    
                    # Join benchmark data with stock data
                    stock_df = stock_df.join(nifty_df, how='left')
                    stock_df['Relative_Strength'] = stock_df['Close'] / stock_df['Nifty_Close']
                    stock_df.drop(columns=['Nifty_Close'], inplace=True, errors='ignore')
                    # Fill any gaps that might arise from the join
                    stock_df['Relative_Strength'].fillna(method='ffill', inplace=True)
                else:
                    # Fallback if Nifty data is missing for the period
                    stock_df['Relative_Strength'] = 1.0

                # Fetch Sector information for the stock
                meta_query = "SELECT Sector FROM stock_metadata WHERE Symbol = ?"
                cursor = conn.cursor()
                result = cursor.execute(meta_query, (symbol,)).fetchone()
                stock_df['Sector'] = result[0] if result else 'Unknown'

            # Final cleanup
            stock_df.drop(columns=['Symbol'], inplace=True, errors='ignore')

            return stock_df

    except Exception as e:
        print(f"--> DATABASE ERROR fetching data for {symbol}: {e}")
        print("--> Make sure you have run 'python data_ingestion.py' first.")
        return pd.DataFrame()
import pandas as pd
import sqlite3
from .config import DB_FILE, STOCK_UNIVERSES

def get_stock_universe(universe_name="NIFTY_50"):
    return STOCK_UNIVERSES.get(universe_name, [])

def get_historical_data(symbol, start_date, end_date):
    """
    Fetches raw historical data for a given symbol and date range FROM THE DATABASE.
    This version does NOT calculate any features.
    """
    start_str = pd.to_datetime(start_date).strftime('%Y-%m-%d')
    end_str = pd.to_datetime(end_date).strftime('%Y-%m-%d')
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            query = "SELECT * FROM historical_prices WHERE Symbol = ? AND Date BETWEEN ? AND ?"
            stock_df = pd.read_sql_query(query, conn, params=(symbol, start_str, end_str))

            if stock_df.empty:
                return pd.DataFrame()

            stock_df['Date'] = pd.to_datetime(stock_df['Date'])
            stock_df.set_index('Date', inplace=True)

            meta_query = "SELECT Sector FROM stock_metadata WHERE Symbol = ?"
            cursor = conn.cursor()
            result = cursor.execute(meta_query, (symbol,)).fetchone()
            stock_df['Sector'] = result[0] if result else 'Unknown'
            
            stock_df.drop(columns=['Symbol'], inplace=True, errors='ignore')
            return stock_df

    except Exception as e:
        print(f"--> DATABASE ERROR fetching data for {symbol}: {e}")
        return pd.DataFrame()
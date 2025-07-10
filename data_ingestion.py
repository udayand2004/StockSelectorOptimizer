import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from tqdm import tqdm
import time
import os

# Import from the new config file
from app.config import STOCK_UNIVERSES, DB_FILE

TEN_YEARS_AGO = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')
TODAY = datetime.now().strftime('%Y-%m-%d')

def create_database():
    """Creates the database and the required tables if they don't exist."""
    print(f"--- Ensuring database '{DB_FILE}' and tables exist... ---")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_prices (
                Date TEXT NOT NULL,
                Symbol TEXT NOT NULL,
                Open REAL,
                High REAL,
                Low REAL,
                Close REAL,
                Volume INTEGER,
                PRIMARY KEY (Date, Symbol)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_metadata (
                Symbol TEXT PRIMARY KEY,
                Sector TEXT
            )
        """)
        conn.commit()
    print("--- Database is ready. ---")

def ingest_data():
    """Fetches 10 years of data for all stocks and saves to the SQLite DB."""
    nifty_100_symbols = sorted(list(set(
        STOCK_UNIVERSES.get("NIFTY_50", []) + 
        STOCK_UNIVERSES.get("NIFTY_NEXT_50", [])
    )))
    all_symbols_to_ingest = nifty_100_symbols + ['^NSEI']
    
    print(f"\n--- Starting data ingestion for {len(all_symbols_to_ingest)} symbols... ---")
    print(f"--- Period: {TEN_YEARS_AGO} to {TODAY} ---")

    with sqlite3.connect(DB_FILE) as conn:
        for symbol in tqdm(all_symbols_to_ingest, desc="Ingesting Symbols"):
            try:
                ticker = f"{symbol}.NS" if symbol != '^NSEI' else symbol
                data = yf.download(ticker, start=TEN_YEARS_AGO, end=TODAY, auto_adjust=False, progress=False, timeout=30)
                
                if data.empty:
                    tqdm.write(f"--> No data found for {symbol}. Skipping.")
                    continue

                # --- THIS IS THE CRITICAL FIX ---
                # yfinance can sometimes return a MultiIndex column even for a single ticker.
                # We robustly flatten it to a simple index.
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)
                # --- END OF FIX ---

                data.reset_index(inplace=True)
                data.rename(columns={'Adj Close': 'Close'}, inplace=True)
                
                data['Symbol'] = symbol 
                data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
                
                final_columns = ['Date', 'Symbol', 'Open', 'High', 'Low', 'Close', 'Volume']
                prices_df = data[final_columns]

                prices_df.to_sql('historical_prices', conn, if_exists='append', index=False)
                
                if symbol != '^NSEI':
                    info = yf.Ticker(ticker).info
                    sector = info.get('sector', 'Unknown')
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO stock_metadata (Symbol, Sector) VALUES (?, ?)",
                        (symbol, sector)
                    )
                    conn.commit()

                tqdm.write(f"Successfully ingested {symbol}")
                time.sleep(0.5)

            except Exception as e:
                tqdm.write(f"--> FAILED to ingest {symbol}. Error: {e}")

    print("\n--- Data ingestion complete! ---")
    print(f"--- Your database '{DB_FILE}' is now ready to use. ---")


if __name__ == '__main__':
    # Automatically delete the old DB file to ensure a clean start
    if os.path.exists(DB_FILE):
        print(f"--- Deleting old database file: {DB_FILE} ---")
        os.remove(DB_FILE)
        
    create_database()
    ingest_data()
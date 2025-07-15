import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from tqdm import tqdm
import time
import os

# Import from the new config file
from app.config import STOCK_UNIVERSES, DB_FILE, PORTFOLIOS_DB_FILE
from app.factor_analysis import ingest_fama_french_data
TEN_YEARS_AGO = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')
TODAY = datetime.now().strftime('%Y-%m-%d')

def create_database():
    """Creates the main market data database and tables."""
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
    print("--- Market data database is ready. ---")

def create_portfolios_database():
    """Creates the database for storing user-defined portfolios."""
    print(f"--- Ensuring portfolios database '{PORTFOLIOS_DB_FILE}' and tables exist... ---")
    with sqlite3.connect(PORTFOLIOS_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                stocks_json TEXT NOT NULL, -- JSON string of {'STOCK': weight}
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    print("--- Portfolios database is ready. ---")

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

                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)

                data.reset_index(inplace=True)
                data.rename(columns={'Adj Close': 'Close'}, inplace=True)
                
                data['Symbol'] = symbol 
                data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
                
                final_columns = ['Date', 'Symbol', 'Open', 'High', 'Low', 'Close', 'Volume']
                prices_df = data[final_columns]

                # Use a unique constraint to avoid duplicate entries
                prices_df.to_sql('historical_prices', conn, if_exists='append', index=False, method='multi', chunksize=1000)
                
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
    # --- THIS IS THE FIX ---
    # Automatically delete old DB files to ensure a clean start
    if os.path.exists(DB_FILE):
        print(f"--- Deleting old database file: {DB_FILE} ---")
        os.remove(DB_FILE)
    if os.path.exists(PORTFOLIOS_DB_FILE):
        print(f"--- Deleting old portfolios database file: {PORTFOLIOS_DB_FILE} ---")
        os.remove(PORTFOLIOS_DB_FILE)
        
    # Create BOTH databases
    create_database()
    create_portfolios_database() # <-- This line was missing
    
    # Ingest data into the main database
    ingest_data()
    # --- END OF FIX ---
    # --- ADD THIS LINE ---
    # Ingest Fama-French factor data
    ingest_fama_french_data()
    # --- END OF ADDITION ---
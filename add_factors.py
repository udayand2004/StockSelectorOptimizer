# add_factors.py

# --- CORRECTED IMPORTS ---
# We use absolute imports starting from the 'app' package, which Python
# can see because we run this script from the project root.
from app.factor_analysis import ingest_fama_french_data

def main():
    """
    This is a standalone utility script. Its only purpose is to add
    the Fama-French factor data to your existing 'market_data.db'
    database without deleting or re-ingesting all of your stock data.

    Run this script once to fix the 'no such table' error.
    """
    print("=========================================================")
    print("--- Starting Standalone Indian Factor Data Ingestion ---")
    print("--- This will NOT delete your existing stock data. ---")
    print("=========================================================")
    
    # This function is the one we created earlier. It will download the
    # factor data and create the 'fama_french_factors' table in your DB.
    ingest_fama_french_data()
    
    print("\n========================================================")
    print("--- Ingestion Process Complete ---")
    print("Your 'market_data.db' should now contain the 'fama_french_factors' table.")
    print("You can now restart your servers (Flask, Celery) and run your backtest.")
    print("========================================================")


if __name__ == '__main__':
    main()
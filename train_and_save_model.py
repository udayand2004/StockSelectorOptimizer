# train_and_save_model.py

import joblib
from app.ml_models import train_stock_selector
from app.data_fetcher import get_stock_universe, get_historical_data, cache
from flask import Flask
from datetime import date, timedelta

def prime_prediction_cache(symbols):
    """
    Pre-fetches and caches the recent data needed for making predictions.
    This makes the web app's prediction step instantaneous.
    """
    print("\n--- Priming Prediction Cache ---")
    end_date = date.today()
    start_date = end_date - timedelta(days=150) # Same window as in predict_top_stocks
    
    for symbol in symbols:
        # This call will fetch the data and store it in the cache
        get_historical_data(symbol, start_date, end_date)
    
    print("Prediction cache is now primed and ready for the web app.")

def run_training_pipeline():
    """
    This function trains the model, saves it, and primes the cache.
    """
    print("--- Starting Offline Model Training Pipeline ---")
    
    # We need a temporary app context for the cache to work
    temp_app = Flask(__name__)
    cache.init_app(temp_app)
    
    with temp_app.app_context():
        # --- Step 1: Define the universe and train the model ---
        print("Fetching symbols for NIFTY 50 and NIFTY NEXT 50 for training...")
        nifty_50_symbols = get_stock_universe("NIFTY_50")
        nifty_next_50_symbols = get_stock_universe("NIFTY_NEXT_50")
        
        # Combine and remove duplicates
        training_symbols = sorted(list(set(nifty_50_symbols + nifty_next_50_symbols)))
        print(f"Training model on {len(training_symbols)} unique stocks...")
        
        model = train_stock_selector(training_symbols)

        if model:
            model_filename = 'app/stock_selector_model.joblib'
            joblib.dump(model, model_filename)
            print(f"\nModel successfully trained and saved to {model_filename}")
            
            # --- Step 2: Prime the cache with data needed for prediction ---
            prime_prediction_cache(training_symbols)
        else:
            print("\nModel training failed. No model was saved.")

if __name__ == '__main__':
    run_training_pipeline()
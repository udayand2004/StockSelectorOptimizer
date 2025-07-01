import joblib
import pandas as pd
import lightgbm as lgb
from flask import Flask
from datetime import date, timedelta
from tqdm import tqdm

# App imports
from app.data_fetcher import get_stock_universe, get_historical_data, cache
from app.strategy import generate_all_features # <-- CORRECTED IMPORT

def train_production_model(symbols):
    """Trains and saves the final LightGBM model for production use."""
    print("--- Fetching data for production model ---")
    end_date = date.today()
    start_date = end_date - timedelta(days=5 * 365)
    
    all_training_data = []
    print("--- Preparing training data for all symbols ---")
    for symbol in tqdm(symbols, desc="Processing Symbols"):
        # get_historical_data now provides a self-contained DataFrame
        data = get_historical_data(symbol, start_date, end_date)
        if not data.empty:
            # Use the unified strategy to prepare training data
            all_features_df = generate_all_features(data)
            # For training, we only use rows where the 'Target' is not NaN
            training_ready_df = all_features_df.dropna(subset=['Target'])
            if not training_ready_df.empty:
                all_training_data.append(training_ready_df)

    if not all_training_data:
        print("Could not generate any training features. Aborting.")
        return None

    full_dataset = pd.concat(all_training_data)
    feature_cols = ['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']
    X = full_dataset[feature_cols]
    y = full_dataset['Target']

    best_params = {
        'objective': 'regression_l1', 'metric': 'rmse', 'n_estimators': 2000,
        'verbosity': -1, 'boosting_type': 'gbdt', 'n_jobs': -1,
        'lambda_l1': 0.000000035570592833340485, 'lambda_l2': 0.00000023634663148674545, 'num_leaves': 250,
        'feature_fraction': 0.43246049791683877, 'bagging_fraction':0.6098643301693437, 'bagging_freq': 4,
        'min_child_samples': 7,
    }
    
    print(f"--- Training final LightGBM model on {len(X)} data points... ---")
    model = lgb.LGBMRegressor(**best_params)
    
    model.fit(X, y) 
    
    print("Model training complete.")
    return model

def run_training_pipeline():
    """Main training workflow."""
    app = Flask(__name__)
    cache.init_app(app)
    
    with app.app_context():
        nifty_50 = get_stock_universe("NIFTY_50")
        nifty_next_50 = get_stock_universe("NIFTY_NEXT_50")
        training_symbols = sorted(list(set(nifty_50 + nifty_next_50)))
        
        model = train_production_model(training_symbols)

        if model:
            model_filename = 'app/stock_selector_model.joblib'
            joblib.dump(model, model_filename)
            print(f"\nModel successfully trained and saved to {model_filename}")
        else:
            print("\nModel training failed.")

if __name__ == '__main__':
    run_training_pipeline()
# tune_model.py

import optuna
import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from datetime import date, timedelta
from flask import Flask

# App imports - requires a Flask context for the cache
from app.data_fetcher import get_stock_universe, get_historical_data, cache
from app.ml_models import create_features_for_training

def objective(trial, X, y):
    """The objective function for Optuna to optimize."""
    # Define the hyperparameter search space
    param = {
        'objective': 'regression_l1', 'metric': 'rmse', 'n_estimators': 2000,
        'verbosity': -1, 'boosting_type': 'gbdt', 'n_jobs': -1,
        'lambda_l1': trial.suggest_float('lambda_l1', 1e-8, 10.0, log=True),
        'lambda_l2': trial.suggest_float('lambda_l2', 1e-8, 10.0, log=True),
        'num_leaves': trial.suggest_int('num_leaves', 2, 256),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.4, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.4, 1.0),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
    }

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = lgb.LGBMRegressor(**param)
    # Use early stopping to find the optimal number of boosting rounds
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], callbacks=[lgb.early_stopping(100, verbose=False)])
    
    preds = model.predict(X_test)
    r2 = r2_score(y_test, preds)
    return r2

def run_tuning():
    """Main function to run the hyperparameter tuning."""
    print("--- Starting Hyperparameter Tuning with Optuna and LightGBM ---")
    
    app = Flask(__name__)
    cache.init_app(app)
    
    with app.app_context():
        # 1. Fetch a large dataset for robust tuning
        print("Fetching training data...")
        end_date = date.today()
        start_date = end_date - timedelta(days=5 * 365)
        
        nifty_50 = get_stock_universe("NIFTY_50")
        nifty_next_50 = get_stock_universe("NIFTY_NEXT_50")
        all_symbols = sorted(list(set(nifty_50 + nifty_next_50)))
        
        all_features = [f for symbol in all_symbols 
                        if not (data := get_historical_data(symbol, start_date, end_date)).empty
                        and not (f := create_features_for_training(data)).empty]

        if not all_features:
            print("Failed to generate features. Aborting tuning.")
            return

        full_dataset = pd.concat(all_features)
        X = full_dataset[['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']]
        y = full_dataset['Target']

        # 2. Run Optuna study
        print(f"Starting Optuna study on {len(X)} data points...")
        study = optuna.create_study(direction='maximize')
        study.optimize(lambda trial: objective(trial, X, y), n_trials=100, timeout=600) # Run for 100 trials or 10 mins

        # 3. Print the results
        print("\n--- Tuning Complete ---")
        print(f"Number of finished trials: {len(study.trials)}")
        print("Best trial:")
        trial = study.best_trial
        print(f"  Value (R^2): {trial.value:.4f}")
        print("  Best Parameters: ")
        for key, value in trial.params.items():
            print(f"    '{key}': {value},")

if __name__ == '__main__':
    run_tuning()
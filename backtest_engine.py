# backtest_engine.py (Final Version - KeyError Fixed)

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from dateutil.relativedelta import relativedelta
import quantstats as qs
from tqdm import tqdm

# App Imports
from app.data_fetcher import get_stock_universe
from app.ml_models import optimize_portfolio
from sklearn.ensemble import GradientBoostingRegressor

# --- Backtester Configuration ---
START_DATE = "2022-01-01"
END_DATE = date.today().strftime("%Y-%m-%d")
INVESTMENT_UNIVERSE = "NIFTY_50"
TOP_N_STOCKS = 10
TRAINING_WINDOW_YEARS = 3
RISK_FREE_RATE = 0.06

def generate_features_and_target(df, nifty_df):
    """Generates features and target on a full historical DataFrame."""
    if df.empty or len(df) < 80:
        return pd.DataFrame()
        
    features = df.copy()
    
    # --- FIX: Move Relative Strength calculation INSIDE this function ---
    features['Relative_Strength'] = features['Close'].divide(nifty_df)
    
    features['MA_20'] = features['Close'].rolling(window=20).mean()
    features['MA_50'] = features['Close'].rolling(window=50).mean()
    features['ROC_20'] = features['Close'].pct_change(20)
    features['Volatility_20D'] = features['Close'].rolling(window=20).std()
    delta = features['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9)
    features['RSI'] = 100 - (100 / (1 + rs))
    features['Target'] = df['Close'].pct_change(periods=22).shift(-22)
    return features

def run_backtest():
    all_symbols = get_stock_universe(INVESTMENT_UNIVERSE)
    earliest_date = pd.to_datetime(START_DATE) - relativedelta(years=TRAINING_WINDOW_YEARS)

    print("--- Fetching all historical raw data... ---")
    nifty_close = yf.download('^NSEI', start=earliest_date, end=END_DATE, auto_adjust=True, progress=False)['Close']
    master_raw_data = {}
    for symbol in tqdm(all_symbols, desc="Fetching Raw Data"):
        df = yf.download(f"{symbol}.NS", start=earliest_date, end=END_DATE, auto_adjust=True, progress=False)
        if not df.empty:
            master_raw_data[symbol] = df

    print("\n--- Pre-computing all features on full history... ---")
    master_feature_data = {}
    for symbol, df in tqdm(master_raw_data.items(), desc="Generating Features"):
        # Pass the nifty_close data into the function
        features_df = generate_features_and_target(df, nifty_close)
        if not features_df.empty:
            # Drop rows where any of the core features or target are NaN
            master_feature_data[symbol] = features_df.dropna(
                subset=['MA_50', 'RSI', 'Relative_Strength', 'Target']
            )

    print("\n--- Starting backtest loop... ---")
    rebalance_dates = pd.date_range(start=START_DATE, end=END_DATE, freq='BMS')
    all_holdings = {}

    for current_rebalance_date in tqdm(rebalance_dates, desc="Backtesting Progress"):
        train_start_date = current_rebalance_date - relativedelta(years=TRAINING_WINDOW_YEARS)
        
        all_X_train, all_y_train = [], []
        
        for symbol, feature_df in master_feature_data.items():
            # Slice the PRE-COMPUTED feature DataFrame
            train_mask = (feature_df.index >= train_start_date) & (feature_df.index <= current_rebalance_date)
            train_slice = feature_df.loc[train_mask]

            if not train_slice.empty:
                all_X_train.append(train_slice[['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']])
                all_y_train.append(train_slice['Target'])

        if not all_X_train:
            tqdm.write(f"--> No valid training data for {current_rebalance_date.date()}.")
            continue
            
        full_X_train = pd.concat(all_X_train)
        full_y_train = pd.concat(all_y_train)
        
        if full_X_train.empty:
             continue

        model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)
        model.fit(full_X_train, full_y_train)
        
        predictions = {}
        for symbol, feature_df in master_feature_data.items():
            predict_slice = feature_df.loc[feature_df.index <= current_rebalance_date]
            
            if not predict_slice.empty:
                latest_features = predict_slice[['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']].iloc[-1:]
                if not latest_features.isnull().values.any():
                    predictions[symbol] = model.predict(latest_features)[0]
        
        if not predictions:
            all_holdings[current_rebalance_date] = {}
            continue
        
        top_stocks = [s for s, p in sorted(predictions.items(), key=lambda item: item[1], reverse=True)[:TOP_N_STOCKS]]
        tqdm.write(f"Top picks for {current_rebalance_date.date()}: {top_stocks}")
        
        portfolio_data = {s: master_raw_data[s].loc[(master_raw_data[s].index >= train_start_date) & (master_raw_data[s].index <= current_rebalance_date)] 
                          for s in top_stocks if s in master_raw_data}
        
        if len(portfolio_data) < 2:
            all_holdings[current_rebalance_date] = {}
            continue
        weights = optimize_portfolio(portfolio_data, RISK_FREE_RATE)
        all_holdings[current_rebalance_date] = weights
        tqdm.write(f"Generated holdings for {current_rebalance_date.date()}: { {k: v for k, v in weights.items() if v > 0} }")

    # --- PERFORMANCE CALCULATION ---
    print("\n--- Calculating Performance ---")
    if not all_holdings:
        print("No holdings were generated during the backtest.")
        return

    holdings_df = pd.DataFrame.from_dict(all_holdings, orient='index').fillna(0)
    valid_symbols_in_holdings = holdings_df.columns
    price_df = pd.DataFrame({symbol: master_raw_data[symbol]['Close'] for symbol in valid_symbols_in_holdings if symbol in master_raw_data}).loc[START_DATE:END_DATE]
    
    returns_data = price_df.pct_change().fillna(0)
    aligned_holdings = holdings_df.reindex(returns_data.index, method='ffill').fillna(0)
    
    common_cols = aligned_holdings.columns.intersection(returns_data.columns)
    portfolio_returns = (aligned_holdings[common_cols] * returns_data[common_cols]).sum(axis=1)

    # --- REPORTING ---
    print("\n--- Backtest Complete: Strategy Performance Report ---")
    benchmark_returns = yf.download('^NSEI', start=START_DATE, end=END_DATE, auto_adjust=True, progress=False)['Close'].pct_change()
    qs.reports.html(portfolio_returns, benchmark=benchmark_returns, output='backtest_report.html', title='ML Stock Selector Strategy')
    print("\nReport saved to backtest_report.html. Open this file in your browser.")

if __name__ == '__main__':
    run_backtest()
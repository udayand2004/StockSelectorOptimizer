import pandas as pd
import numpy as np
import yfinance as yf
import quantstats as qs
from tqdm import tqdm
from datetime import date
from dateutil.relativedelta import relativedelta
import lightgbm as lgb
import uuid
import os

# App Imports
from .data_fetcher import get_stock_universe, get_historical_data
from .ml_models import optimize_portfolio
from .strategy import generate_all_features

def run_backtest(start_date_str, end_date_str, universe_name, top_n, rebalance_freq='BMS'):
    """
    Runs a full backtest and returns a dictionary of results for UI rendering.
    """
    TRAINING_WINDOW_YEARS = 3
    RISK_FREE_RATE = 0.06

    # --- Main backtesting loop (this part is correct and unchanged) ---
    all_symbols = get_stock_universe(universe_name)
    earliest_date = pd.to_datetime(start_date_str) - relativedelta(years=TRAINING_WINDOW_YEARS)
    master_raw_data = {}
    for symbol in tqdm(all_symbols, desc="[Backtest] Fetching Raw Data"):
        df = get_historical_data(symbol, earliest_date, end_date_str)
        if not df.empty:
            master_raw_data[symbol] = df
    master_feature_data = {}
    for symbol, df in tqdm(master_raw_data.items(), desc="[Backtest] Generating Features"):
        features_df = generate_all_features(df)
        if not features_df.empty:
            master_feature_data[symbol] = features_df
    rebalance_dates = pd.date_range(start=start_date_str, end=end_date_str, freq=rebalance_freq)
    all_holdings = {}
    feature_cols = ['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']
    for rebalance_date in tqdm(rebalance_dates, desc="[Backtest] Progress"):
        train_start_date = rebalance_date - relativedelta(years=TRAINING_WINDOW_YEARS)
        all_X_train, all_y_train = [], []
        for symbol, feature_df in master_feature_data.items():
            train_mask = (feature_df.index >= train_start_date) & (feature_df.index < rebalance_date)
            train_data = feature_df.loc[train_mask].copy()
            train_data = train_data.dropna(subset=feature_cols).dropna(subset=['Target'])
            if not train_data.empty:
                all_X_train.append(train_data[feature_cols])
                all_y_train.append(train_data['Target'])
        if not all_X_train: continue
        model = lgb.LGBMRegressor(n_estimators=100, n_jobs=-1, verbosity=-1, random_state=42)
        model.fit(pd.concat(all_X_train), pd.concat(all_y_train))
        predictions = {}
        for symbol, feature_df in master_feature_data.items():
            predict_slice = feature_df.loc[feature_df.index < rebalance_date]
            if not predict_slice.empty:
                latest_features = predict_slice[feature_cols].dropna()
                if not latest_features.empty:
                    predictions[symbol] = model.predict(latest_features.tail(1))[0]
        if not predictions:
            all_holdings[rebalance_date] = {}
            continue
        top_stocks = [s for s, p in sorted(predictions.items(), key=lambda item: item[1], reverse=True)[:top_n]]
        portfolio_data = {s: master_raw_data[s].loc[master_raw_data[s].index < rebalance_date] for s in top_stocks if s in master_raw_data}
        if len(portfolio_data) >= 2:
            weights = optimize_portfolio(portfolio_data, RISK_FREE_RATE)
            all_holdings[rebalance_date] = weights
            
    # --- NEW: Calculate and Format Results for JSON ---
    print("\n--- [Backtest] Calculating and Formatting Results ---")
    if not all_holdings:
        raise ValueError("No holdings were generated during the backtest.")

    holdings_df = pd.DataFrame.from_dict(all_holdings, orient='index').fillna(0)
    holdings_df.sort_index(inplace=True)
    price_df = pd.DataFrame({symbol: master_raw_data[symbol]['Close'] for symbol in holdings_df.columns if symbol in master_raw_data}).loc[start_date_str:end_date_str]
    price_df.sort_index(inplace=True)
    
    returns_df = price_df.pct_change().fillna(0)
    aligned_holdings = holdings_df.reindex(returns_df.index, method='ffill').fillna(0)
    common_cols = aligned_holdings.columns.intersection(returns_df.columns)
    portfolio_returns = (aligned_holdings[common_cols] * returns_df[common_cols]).sum(axis=1)

    benchmark_returns = yf.download('^NSEI', start=start_date_str, end=end_date_str, auto_adjust=True, progress=False)['Close'].pct_change()
    
    # 1. Calculate KPIs
    kpis = {
        "CAGR": f"{qs.stats.cagr(portfolio_returns) * 100:.2f}%",
        "Sharpe": f"{qs.stats.sharpe(portfolio_returns):.2f}",
        "Max Drawdown": f"{qs.stats.max_drawdown(portfolio_returns) * 100:.2f}%",
        "Calmar": f"{qs.stats.calmar(portfolio_returns):.2f}",
        "Benchmark CAGR": f"{qs.stats.cagr(benchmark_returns) * 100:.2f}%"
    }
    
    # 2. Prepare Equity Curve Chart Data
    equity_curve = (1 + portfolio_returns).cumprod()
    benchmark_curve = (1 + benchmark_returns).cumprod()
    equity_chart_data = {
        "dates": equity_curve.index.strftime('%Y-%m-%d').tolist(),
        "portfolio": equity_curve.values.tolist(),
        "benchmark": benchmark_curve.reindex(equity_curve.index, method='ffill').values.tolist()
    }
    
    # 3. Prepare Drawdown Chart Data
    drawdown_series = qs.stats.to_drawdown_series(portfolio_returns)
    drawdown_chart_data = {
        "dates": drawdown_series.index.strftime('%Y-%m-%d').tolist(),
        "values": (drawdown_series.values * 100).tolist() # In percentage
    }

    # 4. Combine into a single dictionary and return
    results_payload = {
        "kpis": kpis,
        "charts": {
            "equity": equity_chart_data,
            "drawdown": drawdown_chart_data
        }
    }
    
    print("\nBacktest analysis complete. Returning JSON payload.")
    return results_payload
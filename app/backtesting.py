# app/backtesting.py

import pandas as pd
import numpy as np
import quantstats as qs
from tqdm import tqdm
from datetime import date
from dateutil.relativedelta import relativedelta
import joblib
import json
import lightgbm as lgb
from . import factor_analysis
from .data_fetcher import get_stock_universe, get_historical_data
from .ml_models import optimize_portfolio, get_portfolio_sector_exposure
from .strategy import generate_all_features
from .reporting import generate_gemini_report
from . import factor_analysis 
# --- HELPER: JSON-SAFE CONVERTER ---
def to_json_safe(obj):
    """Converts numpy/pandas objects to JSON-serializable types."""
    if isinstance(obj, np.generic): return obj.item()
    if isinstance(obj, (np.ndarray,)): return obj.tolist()
    if isinstance(obj, pd.Timestamp): return obj.isoformat()
    if isinstance(obj, pd.Index): return obj.tolist()
    if pd.isna(obj): return None
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# --- HELPER: SHARED REPORTING FUNCTION ---
# In app/backtesting.py, find the generate_report_payload function and REPLACE it with this:

def generate_report_payload(portfolio_returns, benchmark_returns, holdings_df, master_raw_data, rebalance_logs, risk_free_rate):
    """
    A centralized function to generate the entire QuantStats report payload.
    This version includes a critical fix to handle zero-trade scenarios.
    """
    # --- FIX 1: HANDLE ZERO-ACTIVITY STRATEGY ---
    if holdings_df.sum().sum() < 1e-9:
        print("--- [Reporting] No trades were made. Generating a zero-performance report. ---")
        start_date = holdings_df.index.min()
        end_date = holdings_df.index.max()
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        strategy_equity = pd.Series(1.0, index=date_range)
        benchmark_equity = (1 + benchmark_returns.fillna(0)).cumprod()

        kpis = {
            "CAGR﹪": 0.0, "Sharpe": 0.0, "Max Drawdown": 0.0,
            "Sortino": 0.0, "Beta": 0.0, "Calmar": 0.0,
            "Daily VaR": 0.0, "Daily CVaR": 0.0,
            "Error": "Strategy did not execute any trades. This may be due to the regime filter always being active or the model never producing positive predictions."
        }
        
        return {
            "kpis": kpis,
            "factor_exposure": {"error": "Factor analysis not run because no trades were made."}, # Add placeholder
            "charts": {
                "equity": { "data": [
                    {'x': strategy_equity.index.strftime('%Y-%m-%d').tolist(), 'y': strategy_equity.values.tolist(), 'mode': 'lines', 'name': 'Strategy (No Trades)'},
                    {'x': benchmark_equity.index.strftime('%Y-%m-%d').tolist(), 'y': benchmark_equity.values.tolist(), 'mode': 'lines', 'name': 'Benchmark (NIFTY 50)'}
                ], "layout": {'title': 'Strategy vs. Benchmark Performance'} },
                "drawdown": {"data": [], "layout": {'title': 'Strategy Drawdowns (No Trades)'}},
                "historical_weights": {"data": [], "layout": {'title': 'Historical Stock Weights (No Trades)'}},
                "historical_sectors": {"data": [], "layout": {'title': 'Historical Sector Exposure (No Trades)'}}
            },
            "tables": {"monthly_returns": "{}", "yearly_returns": "{}"},
            "logs": rebalance_logs,
            "ai_report": "AI analysis skipped: The strategy did not make any trades."
        }
    # --- END OF FIX 1 ---

    portfolio_returns.fillna(0, inplace=True)
    benchmark_returns.fillna(0, inplace=True)
    combined = pd.merge(portfolio_returns.rename('Strategy'), benchmark_returns.rename('Benchmark'), left_index=True, right_index=True, how='inner')
    
    portfolio_returns_clean = combined['Strategy']
    benchmark_returns_clean = combined['Benchmark']
    
    kpis_df = qs.reports.metrics(portfolio_returns_clean, benchmark=benchmark_returns_clean, rf=risk_free_rate, display=False)
    if 'Strategy' not in kpis_df.columns:
         raise ValueError("QuantStats failed to generate metrics for the strategy.")
    kpis = kpis_df.loc[:, 'Strategy']
    
    #
    # --- THIS IS THE CORRECTED INDENTATION ---
    #
    # Perform Factor Exposure Analysis
    factor_exposure_results = factor_analysis.analyze_factor_exposure(portfolio_returns_clean)
    rolling_factor_results_json = factor_analysis.analyze_rolling_factor_exposure(portfolio_returns_clean)
    drawdown_series = qs.stats.to_drawdown_series(portfolio_returns_clean)
    monthly_returns_df = qs.stats.monthly_returns(portfolio_returns_clean, compounded=True)
    yearly_returns_df = portfolio_returns_clean.resample('YE').apply(lambda x: (1 + x).prod() - 1).to_frame(name='Strategy')
    yearly_returns_df.index = yearly_returns_df.index.year

    strategy_equity = (1 + portfolio_returns_clean).cumprod()
    benchmark_equity = (1 + benchmark_returns_clean).cumprod()
    
    sector_exposure_over_time = {}
    for a_date, weights in holdings_df.iterrows():
        portfolio_data = { s: master_raw_data[s] for s in weights.index if s in master_raw_data and weights.get(s, 0) > 0 }
        sector_exposure_over_time[a_date] = get_portfolio_sector_exposure(portfolio_data, weights)
    sector_exposure_df = pd.DataFrame.from_dict(sector_exposure_over_time, orient='index').fillna(0)
    
    stock_traces = [{'x': holdings_df.index.strftime('%Y-%m-%d').tolist(), 'y': (holdings_df[stock] * 100).tolist(), 'name': stock, 'type': 'bar'} for stock in holdings_df.columns if holdings_df[stock].sum() > 0]
    stock_layout = {'title': 'Historical Stock Weights (%)', 'barmode': 'stack', 'yaxis': {'ticksuffix': '%'}, 'legend': {'traceorder': 'reversed'}}
    
    sector_traces = [{'x': sector_exposure_df.index.strftime('%Y-%m-%d').tolist(), 'y': (sector_exposure_df[sector] * 100).tolist(), 'name': sector, 'type': 'bar'} for sector in sector_exposure_df.columns if sector_exposure_df[sector].sum() > 0]
    sector_layout = {'title': 'Historical Sector Exposure (%)', 'barmode': 'stack', 'yaxis': {'ticksuffix': '%'}, 'legend': {'traceorder': 'reversed'}}

    ai_report = generate_gemini_report(kpis.to_dict(), {}, yearly_returns_df['Strategy'].to_dict(), rebalance_logs)
    
    results_payload = {
        "kpis": kpis.to_dict(),
        "factor_exposure": factor_exposure_results,  # Add factor results to the payload
        "charts": {
            "equity": { "data": [{'x': strategy_equity.index.strftime('%Y-%m-%d').tolist(), 'y': strategy_equity.values.tolist(), 'mode': 'lines', 'name': 'Strategy', 'line': {'color': '#0d6efd', 'width': 2}}, {'x': benchmark_equity.index.strftime('%Y-%m-%d').tolist(), 'y': benchmark_equity.values.tolist(), 'mode': 'lines', 'name': 'Benchmark (NIFTY 50)', 'line': {'color': '#6c757d', 'dash': 'dot', 'width': 1.5}}], "layout": {'title': 'Strategy vs. Benchmark Performance', 'yaxis': {'title': 'Cumulative Growth', 'type': 'log'}, 'legend': {'x': 0.01, 'y': 0.99}, 'margin': {'t': 40, 'b': 40, 'l': 60, 'r': 20}} },
            "drawdown": { "data": [{'x': drawdown_series.index.strftime('%Y-%m-%d').tolist(), 'y': (drawdown_series.values * 100).tolist(), 'type': 'scatter', 'mode': 'lines', 'fill': 'tozeroy', 'name': 'Drawdown', 'line': {'color': '#dc3545'}}], "layout": {'title': 'Strategy Drawdowns', 'yaxis': {'title': 'Drawdown (%)'}, 'margin': {'t': 40, 'b': 40, 'l': 60, 'r': 20}} },
            "historical_weights": {"data": stock_traces, "layout": stock_layout},
            "historical_sectors": {"data": sector_traces, "layout": sector_layout},
            "rolling_factor_betas": rolling_factor_results_json
        },
        "tables": { "monthly_returns": monthly_returns_df.to_json(orient='split'), "yearly_returns": yearly_returns_df.to_json(orient='split') },
        "logs": rebalance_logs,
        "ai_report": ai_report,   
    }
    return json.loads(json.dumps(results_payload, default=to_json_safe))

def calculate_performance(holdings_df, master_raw_data, start_date_str, end_date_str, risk_free_rate, rebalance_logs):
    """
    Centralized performance calculation function.
    """
    log_progress = lambda message: print(message)
    log_progress("--- [Reporting] Starting performance calculation...")

    clean_date_index = pd.date_range(start=start_date_str, end=end_date_str, freq='B')
    
    benchmark_data = get_historical_data('^NSEI', start_date_str, end_date_str)
    benchmark_returns = benchmark_data['Close'].pct_change(fill_method=None)
    benchmark_returns.name = 'Benchmark'
    
    # Pass benchmark returns to the payload generator in case the strategy has no trades.
    if holdings_df.sum().sum() < 1e-9:
        return generate_report_payload(pd.Series(), benchmark_returns, holdings_df, master_raw_data, rebalance_logs, risk_free_rate)

    valid_cols = [col for col in holdings_df.columns if col in master_raw_data]
    price_df = pd.DataFrame({
        symbol: master_raw_data[symbol]['Close'] for symbol in valid_cols
    }).reindex(clean_date_index, method='ffill')
    
    price_df.sort_index(inplace=True)
    returns_df = price_df.pct_change(fill_method=None)
    
    holdings_df.sort_index(inplace=True)
    aligned_holdings = holdings_df.reindex(returns_df.index, method='ffill').fillna(0)

    TRANSACTION_COST_BPS = 15
    turnover = (aligned_holdings.shift(1).fillna(0) - aligned_holdings).abs().sum(axis=1) / 2
    transaction_costs = turnover * (TRANSACTION_COST_BPS / 10000)
    portfolio_returns = (aligned_holdings * returns_df[aligned_holdings.columns]).sum(axis=1) - transaction_costs
    portfolio_returns.name = 'Strategy'
    
    return generate_report_payload(portfolio_returns, benchmark_returns, holdings_df, master_raw_data, rebalance_logs, risk_free_rate)

# --- BACKTESTER 1: ML-DRIVEN STRATEGY ---
def run_backtest(start_date_str, end_date_str, universe_name, top_n, risk_free_rate, rebalance_freq='BMS', progress_callback=None):
    def log_progress(message):
        if progress_callback: progress_callback(message)

    log_progress("--- [Backtest Engine] Initializing ML Walk-Forward Backtest ---")
    
    all_symbols = get_stock_universe(universe_name)
    earliest_date = pd.to_datetime(start_date_str) - relativedelta(years=5)

    master_raw_data = {
        symbol: get_historical_data(symbol, earliest_date, end_date_str)
        for symbol in tqdm(all_symbols, desc="Loading Stock Data")
    }
    master_raw_data = {k: v for k, v in master_raw_data.items() if not v.empty}
    
    benchmark_master_df = get_historical_data('^NSEI', earliest_date, end_date_str)
    if benchmark_master_df.empty:
        raise ValueError("Could not load master benchmark data. Backtest cannot proceed.")
    
    log_progress("--- Starting Walk-Forward Simulation... ---")
    rebalance_dates = pd.date_range(start=start_date_str, end=end_date_str, freq=rebalance_freq)
    all_holdings = {}
    rebalance_logs = []
    model = None
    last_train_date = pd.Timestamp.min
    feature_cols = ['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength', 'Momentum_3M', 'Momentum_6M', 'Momentum_12M', 'Sharpe_3M']

    for rebalance_date in tqdm(rebalance_dates, desc="Backtesting Progress"):
        if model is None or (rebalance_date - last_train_date).days > 365:
            # ... Model retraining logic is correct ...
            log_progress(f"--- Retraining model for date: {rebalance_date.date()} ---")
            train_start = rebalance_date - relativedelta(years=3)
            train_end = rebalance_date
            all_training_data = []
            for symbol, raw_data in master_raw_data.items():
                train_stock_slice = raw_data.loc[train_start:train_end]
                train_bench_slice = benchmark_master_df.loc[train_start:train_end]
                if len(train_stock_slice) < 252: continue
                features_df = generate_all_features(train_stock_slice, train_bench_slice)
                training_ready_df = features_df.dropna(subset=['Target'] + feature_cols)
                if not training_ready_df.empty: all_training_data.append(training_ready_df)
            if all_training_data:
                full_dataset = pd.concat(all_training_data)
                X_train, y_train = full_dataset[feature_cols], full_dataset['Target']
                model = lgb.LGBMRegressor(objective='regression_l1', n_estimators=500, n_jobs=-1, random_state=42)
                model.fit(X_train, y_train)
                last_train_date = rebalance_date
                log_progress("--- Model retraining complete. ---")
            else:
                log_progress("--- Not enough data for retraining, using previous model. ---")

        # --- FIX 2: ROBUST REGIME FILTER ---
        current_log = {'Date': rebalance_date.strftime('%Y-%m-%d'), 'Action': 'Hold Cash', 'Details': {}}
        try:
            nifty_past_data = benchmark_master_df.loc[benchmark_master_df.index < rebalance_date]
            if len(nifty_past_data) < 200:
                current_log['Details'] = "Not enough market history for 200-day MA."
                all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue
            
            last_price = nifty_past_data['Close'].iloc[-1]
            nifty_ma_200 = nifty_past_data['Close'].rolling(window=200).mean().iloc[-1]
            
            if pd.isna(last_price) or pd.isna(nifty_ma_200):
                 current_log['Details'] = "NaN value encountered in regime filter data."
                 all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

            # The core filter logic. If price is below the MA, hold cash.
            if last_price < nifty_ma_200:
                current_log['Details'] = f"Regime filter triggered: NIFTY Close ({last_price:.2f}) < 200-MA ({nifty_ma_200:.2f})"
                all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue
        
        except (IndexError, ValueError) as e:
            current_log['Details'] = f"Error in regime filter calculation: {e}"
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue
        # --- END OF FIX 2 ---

        if model is None:
            current_log['Details'] = "ML model is not trained yet."
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        predictions = {}
        for symbol, raw_data in master_raw_data.items():
            stock_past_data = raw_data.loc[raw_data.index < rebalance_date]
            benchmark_past_data = benchmark_master_df.loc[benchmark_master_df.index < rebalance_date]
            if len(stock_past_data) < 252: continue
            features_df = generate_all_features(stock_past_data, benchmark_past_data)
            if features_df.empty: continue
            latest_features = features_df[feature_cols].dropna()
            if not latest_features.empty:
                predictions[symbol] = model.predict(latest_features.tail(1))[0]
        
        if not predictions:
            current_log['Details'] = "ML model returned no valid predictions for this period."
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        top_stocks = [s for s, p in sorted(predictions.items(), key=lambda item: item[1], reverse=True) if p > 0][:top_n]
        
        if not top_stocks:
            current_log['Details'] = "No stocks had positive predictions."
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        portfolio_data = {s: master_raw_data[s].loc[master_raw_data[s].index < rebalance_date] for s in top_stocks}
        
        if len(portfolio_data) >= 2:
            weights = optimize_portfolio(portfolio_data, risk_free_rate)
            all_holdings[rebalance_date] = weights
            current_log['Action'] = 'Rebalanced Portfolio'; current_log['Details'] = weights
        else:
            current_log['Details'] = "Not enough valid stocks with positive predictions to form a portfolio."
            all_holdings[rebalance_date] = {}
        rebalance_logs.append(current_log)

    holdings_df = pd.DataFrame.from_dict(all_holdings, orient='index').fillna(0)
    return calculate_performance(holdings_df, master_raw_data, start_date_str, end_date_str, risk_free_rate, rebalance_logs)

# --- BACKTESTER 2: CUSTOM PORTFOLIO ---
def run_custom_portfolio_backtest(holdings, start_date_str, end_date_str, risk_free_rate, rebalance_freq='BMS', progress_callback=None):
    def log_progress(message):
        if progress_callback: progress_callback(message)

    log_progress("--- [Custom Backtest] Initializing ---")
    
    all_symbols = list(holdings.keys())
    earliest_date = pd.to_datetime(start_date_str) - relativedelta(days=50)

    master_raw_data = {
        symbol: get_historical_data(symbol, earliest_date, end_date_str)
        for symbol in tqdm(all_symbols, desc="Loading Custom Portfolio Data")
    }
    master_raw_data = {k: v for k, v in master_raw_data.items() if not v.empty}
    
    log_progress("--- [Custom Backtest] Simulating fixed-weight rebalancing... ---")
    rebalance_dates = pd.date_range(start=start_date_str, end=end_date_str, freq=rebalance_freq)
    
    holdings_df = pd.DataFrame([holdings] * len(rebalance_dates), index=rebalance_dates)
    rebalance_logs = [{'Date': date.strftime('%Y-%m-%d'), 'Action': 'Rebalanced to Custom Weights', 'Details': holdings} for date in rebalance_dates]
    
    return calculate_performance(holdings_df, master_raw_data, start_date_str, end_date_str, risk_free_rate, rebalance_logs)
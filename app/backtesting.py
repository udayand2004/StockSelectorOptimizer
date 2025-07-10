import pandas as pd
import numpy as np
import quantstats as qs
from tqdm import tqdm
from datetime import date
from dateutil.relativedelta import relativedelta
import joblib
import json

from .data_fetcher import get_stock_universe, get_historical_data
from .ml_models import optimize_portfolio, get_portfolio_sector_exposure
# This must be the modified version of strategy.py that accepts two arguments
from .strategy import generate_all_features 

# Helper function to make the final results dictionary JSON-safe for Celery
def to_json_safe(obj):
    if isinstance(obj, (np.integer, np.int64)): return int(obj)
    if isinstance(obj, (np.floating, np.float64)): return float(obj)
    if isinstance(obj, (np.ndarray,)): return obj.tolist()
    if isinstance(obj, pd.Timestamp): return obj.isoformat()
    if isinstance(obj, pd.Index): return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def run_backtest(start_date_str, end_date_str, universe_name, top_n, rebalance_freq='BMS', progress_callback=None):
    def log_progress(message):
        if progress_callback: progress_callback(message)

    log_progress("--- [Backtest Engine] Initializing (Bias-Aware Mode) ---")
    model = joblib.load('app/stock_selector_model.joblib')
    all_symbols = get_stock_universe(universe_name)
    earliest_date = pd.to_datetime(start_date_str) - relativedelta(days=400)

    # --- BIAS-FREE DATA LOADING ---
    # Load all raw data for the entire period + buffer once at the start.
    log_progress("--- [Backtest Engine] Loading all raw data from DB... ---")
    master_raw_data = {}
    for symbol in tqdm(all_symbols, desc="Loading Stock Data"):
        df = get_historical_data(symbol, earliest_date, end_date_str)
        if not df.empty: master_raw_data[symbol] = df
    
    # Load benchmark data for the entire period just once.
    benchmark_master_df = get_historical_data('^NSEI', earliest_date, end_date_str)
    if benchmark_master_df.empty:
        raise ValueError("Could not load master benchmark data. The backtest cannot proceed.")
    # --- END OF DATA LOADING ---
    
    log_progress("--- [Backtest Engine] Data loading complete. Starting simulation... ---")
    rebalance_dates = pd.date_range(start=start_date_str, end=end_date_str, freq=rebalance_freq)
    all_holdings = {}
    rebalance_logs = []
    feature_cols = ['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength', 'Momentum_3M', 'Momentum_6M', 'Momentum_12M', 'Sharpe_3M']

    for rebalance_date in tqdm(rebalance_dates, desc="Backtesting Progress"):
        # Regime Filter uses a point-in-time slice of the master benchmark data.
        nifty_past_data = benchmark_master_df.loc[benchmark_master_df.index < rebalance_date]
        current_log = {'Date': rebalance_date.strftime('%Y-%m-%d'), 'Action': 'Hold Cash', 'Details': {}}

        if len(nifty_past_data) < 200:
            current_log['Details'] = "Not enough market data for regime filter"
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue
        
        nifty_ma_200 = nifty_past_data['Close'].rolling(window=200).mean().iloc[-1]
        if nifty_past_data['Close'].iloc[-1] < nifty_ma_200:
            current_log['Details'] = "Regime filter triggered (Market in Downtrend)"
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        # --- BIAS-FREE FEATURE GENERATION ---
        predictions = {}
        for symbol, raw_data in master_raw_data.items():
            # Create point-in-time slices for both the stock and the benchmark.
            stock_past_data = raw_data.loc[raw_data.index < rebalance_date]
            benchmark_past_data = benchmark_master_df.loc[benchmark_master_df.index < rebalance_date]

            if len(stock_past_data) < 252: continue
            
            # The core bias fix: Pass BOTH point-in-time dataframes to the feature generator.
            features_df = generate_all_features(stock_past_data, benchmark_past_data)
            
            if features_df.empty: continue
            latest_features = features_df[feature_cols].dropna()

            if not latest_features.empty:
                prediction = model.predict(latest_features.tail(1))[0]
                predictions[symbol] = prediction
        
        if not predictions:
            current_log['Details'] = "ML model returned no valid predictions"
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        top_stocks = [s for s, p in sorted(predictions.items(), key=lambda item: item[1], reverse=True)[:top_n]]
        portfolio_data = {s: master_raw_data[s].loc[master_raw_data[s].index < rebalance_date] for s in top_stocks}
        
        if len(portfolio_data) >= 2:
            weights = optimize_portfolio(portfolio_data, 0.06); all_holdings[rebalance_date] = weights
            current_log['Action'] = 'Rebalanced Portfolio'; current_log['Details'] = weights
        else:
            current_log['Details'] = "Not enough valid stocks to form a portfolio"
            all_holdings[rebalance_date] = {}
        rebalance_logs.append(current_log)

    # --- FINAL REPORTING (This block is robust and does not need changes) ---
    log_progress("\n--- [Backtest Engine] Calculating final performance metrics... ---")
    if not all_holdings:
        raise ValueError("No holdings were generated during the entire backtest period.")

    holdings_df = pd.DataFrame.from_dict(all_holdings, orient='index').fillna(0)
    holdings_df.sort_index(inplace=True)
    
    sector_exposure_over_time = {}
    for a_date, weights in holdings_df.iterrows():
        portfolio_data = { s: master_raw_data[s] for s in weights.index if weights[s] > 0 and s in master_raw_data }
        sector_exposure_over_time[a_date] = get_portfolio_sector_exposure(portfolio_data, weights)
    sector_exposure_df = pd.DataFrame.from_dict(sector_exposure_over_time, orient='index').fillna(0)

    price_df = pd.DataFrame({ symbol: master_raw_data[symbol]['Close'] for symbol in holdings_df.columns if symbol in master_raw_data }).loc[start_date_str:end_date_str]
    price_df.sort_index(inplace=True)

    returns_df = price_df.pct_change(fill_method=None)
    aligned_holdings = holdings_df.reindex(returns_df.index, method='ffill').fillna(0)

    TRANSACTION_COST_BPS = 15
    turnover = (aligned_holdings.shift(1).fillna(0) - aligned_holdings).abs().sum(axis=1) / 2
    transaction_costs = turnover * (TRANSACTION_COST_BPS / 10000)
    portfolio_returns = (aligned_holdings * returns_df).sum(axis=1) - transaction_costs
    portfolio_returns.name = 'Strategy'
    
    benchmark_data_final = get_historical_data('^NSEI', start_date_str, end_date_str)
    benchmark_returns = benchmark_data_final['Close'].pct_change(fill_method=None)
    benchmark_returns.name = 'Benchmark'
    
    portfolio_returns.fillna(0, inplace=True)
    benchmark_returns.fillna(0, inplace=True)
    
    combined = pd.merge(portfolio_returns, benchmark_returns, left_index=True, right_index=True, how='inner')
    
    if combined.empty or 'Strategy' not in combined.columns or combined['Strategy'].abs().sum() < 1e-9:
        log_progress("--- [Backtest Engine] No valid overlapping trading days or returns were zero. Returning zeroed stats. ---")
        full_benchmark_equity = (1 + benchmark_returns).cumprod()
        empty_series = pd.Series([0.0], index=pd.to_datetime([start_date_str]))
        empty_monthly = qs.stats.monthly_returns(empty_series).fillna(0)
        empty_yearly = portfolio_returns.resample('YE').apply(lambda x: (1 + x).prod() - 1).to_frame(name='Strategy') * 0
        empty_yearly.index = empty_yearly.index.year
        
        results_payload = {
            "kpis": {"CAGR": "0.00%", "Sharpe": "0.00", "Max Drawdown": "0.00%", "Calmar": "0.00", "Beta": "0.00", "Sortino": "0.00", "VaR": "0.00%", "CVaR": "0.00%"},
            "charts": {
                "equity": { "dates": full_benchmark_equity.index.strftime('%Y-%m-%d').tolist(), "portfolio": [1.0] * len(full_benchmark_equity), "benchmark": full_benchmark_equity.values.tolist() },
                "drawdown": { "dates": full_benchmark_equity.index.strftime('%Y-%m-%d').tolist(), "values": [0.0] * len(full_benchmark_equity) },
                "historical_weights": {"data": [], "layout": {}},
                "historical_sectors": {"data": [], "layout": {}}
            },
            "tables": { "monthly_returns": empty_monthly.to_json(orient='split'), "yearly_returns": empty_yearly.to_json(orient='split') },
            "logs": rebalance_logs
        }
    else:
        portfolio_returns_clean = combined['Strategy']
        benchmark_returns_clean = combined['Benchmark']
        
        log_progress("--- [Backtest Engine] Generating QuantStats report... ---")
        kpis_df = qs.reports.metrics(portfolio_returns_clean, benchmark=benchmark_returns_clean, display=False)

        if 'Strategy' not in kpis_df.columns:
             raise ValueError("QuantStats failed to generate metrics for the strategy. Returns data might be invalid.")
        kpis = kpis_df.loc[:, 'Strategy']
        
        drawdown_series = qs.stats.to_drawdown_series(portfolio_returns_clean)
        monthly_returns_df = qs.stats.monthly_returns(portfolio_returns_clean, compounded=True)
        yearly_returns_df = portfolio_returns_clean.resample('YE').apply(lambda x: (1 + x).prod() - 1).to_frame(name='Strategy')
        yearly_returns_df.index = yearly_returns_df.index.year

        strategy_equity = (1 + portfolio_returns_clean).cumprod()
        benchmark_equity = (1 + benchmark_returns_clean).cumprod()
        
        stock_traces = [{'x': holdings_df.index.strftime('%Y-%m-%d').tolist(), 'y': (holdings_df[stock] * 100).tolist(), 'name': stock, 'type': 'bar'} for stock in holdings_df.columns if holdings_df[stock].sum() > 0]
        stock_layout = {'title': 'Historical Stock Weights (%)', 'barmode': 'stack', 'yaxis': {'ticksuffix': '%'}, 'legend': {'traceorder': 'reversed'}}
        
        sector_traces = [{'x': sector_exposure_df.index.strftime('%Y-%m-%d').tolist(), 'y': (sector_exposure_df[sector] * 100).tolist(), 'name': sector, 'type': 'bar'} for sector in sector_exposure_df.columns if sector_exposure_df[sector].sum() > 0]
        sector_layout = {'title': 'Historical Sector Exposure (%)', 'barmode': 'stack', 'yaxis': {'ticksuffix': '%'}, 'legend': {'traceorder': 'reversed'}}

        results_payload = {
            "kpis": kpis.to_dict(),
            "charts": {
                "equity": { "dates": strategy_equity.index.strftime('%Y-%m-%d').tolist(), "portfolio": strategy_equity.values.tolist(), "benchmark": benchmark_equity.values.tolist() },
                "drawdown": { "dates": drawdown_series.index.strftime('%Y-%m-%d').tolist(), "values": (drawdown_series.values * 100).tolist() },
                "historical_weights": {"data": stock_traces, "layout": stock_layout},
                "historical_sectors": {"data": sector_traces, "layout": sector_layout}
            },
            "tables": {
                "monthly_returns": monthly_returns_df.to_json(orient='split'),
                "yearly_returns": yearly_returns_df.to_json(orient='split')
            },
            "logs": rebalance_logs
        }
    
    final_json_safe_payload = json.loads(json.dumps(results_payload, default=to_json_safe))
    log_progress("--- [Backtest Engine] Complete. ---")
    return final_json_safe_payload
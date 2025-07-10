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
from .strategy import generate_all_features

# --- NEW HELPER FUNCTION ---
# This function will be used to clean the final dictionary of any non-JSON-serializable objects.
def to_json_safe(obj):
    if isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.Index):
        return obj.tolist() # Convert pandas Index to a simple list
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def run_backtest(start_date_str, end_date_str, universe_name, top_n, rebalance_freq='BMS', progress_callback=None):
    def log_progress(message):
        print(message)
        if progress_callback:
            progress_callback(message)

    log_progress("--- [Backtest Engine] Initializing ---")

    try:
        model = joblib.load('app/stock_selector_model.joblib')
        log_progress("--- [Backtest Engine] Production model loaded successfully. ---")
    except FileNotFoundError:
        log_progress("--- [Backtest Engine] FATAL ERROR: Model file not found! ---")
        raise FileNotFoundError("Could not find 'app/stock_selector_model.joblib'. Please run train_and_save_model.py first.")

    all_symbols = get_stock_universe(universe_name)
    earliest_date_for_features = pd.to_datetime(start_date_str) - relativedelta(days=400)

    log_progress(f"--- [Backtest Engine] Fetching historical data for {len(all_symbols)} stocks from DB... ---")
    master_raw_data = {}
    for symbol in tqdm(all_symbols, desc="Loading Data From DB"):
        df = get_historical_data(symbol, earliest_date_for_features, end_date_str)
        if not df.empty:
            master_raw_data[symbol] = df
    log_progress("--- [Backtest Engine] Data loading complete. ---")

    log_progress("\n--- [Backtest Engine] Starting rebalancing simulation... ---")
    rebalance_dates = pd.date_range(start=start_date_str, end=end_date_str, freq=rebalance_freq)
    all_holdings = {}
    
    rebalance_logs = []

    feature_cols = [
        'MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength',
        'Momentum_3M', 'Momentum_6M', 'Momentum_12M', 'Sharpe_3M'
    ]

    for i, rebalance_date in enumerate(tqdm(rebalance_dates, desc="Backtesting Progress")):
        log_progress(f"Processing rebalance date: {rebalance_date.date()}")
        nifty_data = get_historical_data('^NSEI', rebalance_date - pd.Timedelta(days=300), rebalance_date)

        current_log = {'Date': rebalance_date.strftime('%Y-%m-%d'), 'Action': 'Hold Cash', 'Details': {}}

        if nifty_data.empty or len(nifty_data) < 200:
            tqdm.write(f"--> Not enough NIFTY data in DB for {rebalance_date.date()}. Holding cash.")
            all_holdings[rebalance_date] = {}
            current_log['Details'] = "Not enough market data"
            rebalance_logs.append(current_log)
            continue

        nifty_ma_200 = nifty_data['Close'].rolling(window=200).mean().iloc[-1]
        nifty_current_price = nifty_data['Close'].iloc[-1]
        if nifty_current_price < nifty_ma_200:
            tqdm.write(f"--> Market in Downtrend on {rebalance_date.date()}. Holding cash.")
            all_holdings[rebalance_date] = {}
            current_log['Details'] = "Regime filter triggered (Market in Downtrend)"
            rebalance_logs.append(current_log)
            continue
            
        predictions = {}
        for symbol, raw_data in master_raw_data.items():
            data_for_features = raw_data.loc[raw_data.index < rebalance_date]
            if len(data_for_features) < 252: continue
            features_df = generate_all_features(data_for_features)
            latest_features = features_df[feature_cols].dropna()
            if not latest_features.empty:
                prediction = model.predict(latest_features.tail(1))[0]
                predictions[symbol] = prediction
        
        if not predictions:
            all_holdings[rebalance_date] = {}
            current_log['Details'] = "ML model returned no valid predictions"
            rebalance_logs.append(current_log)
            continue

        top_stocks = [s for s, p in sorted(predictions.items(), key=lambda item: item[1], reverse=True)[:top_n]]
        portfolio_data = { s: master_raw_data[s].loc[master_raw_data[s].index < rebalance_date] for s in top_stocks if s in master_raw_data }
        
        if len(portfolio_data) >= 2:
            weights = optimize_portfolio(portfolio_data, risk_free_rate=0.06)
            all_holdings[rebalance_date] = weights
            current_log['Action'] = 'Rebalanced Portfolio'
            current_log['Details'] = weights
        else:
            all_holdings[rebalance_date] = {}
            current_log['Details'] = "Not enough valid stocks to form a portfolio"
        
        rebalance_logs.append(current_log)

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
    
    benchmark_data = get_historical_data('^NSEI', start_date_str, end_date_str)
    benchmark_returns = benchmark_data['Close'].pct_change(fill_method=None)
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
            "kpis": {"CAGR": "0.00%", "Sharpe": "0.00", "Max_Drawdown": "0.00%", "Calmar": "0.00", "Beta": "0.00", "Sortino": "0.00", "VaR": "0.00%", "CVaR": "0.00%"},
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
        
        stock_traces = []
        for stock in holdings_df.columns:
            stock_traces.append({'x': holdings_df.index.strftime('%Y-%m-%d').tolist(), 'y': (holdings_df[stock] * 100).tolist(), 'name': stock, 'type': 'bar'})
        stock_layout = {'title': 'Historical Stock Weights (%)', 'barmode': 'stack', 'yaxis': {'ticksuffix': '%'}}
        
        sector_traces = []
        for sector in sector_exposure_df.columns:
            sector_traces.append({'x': sector_exposure_df.index.strftime('%Y-%m-%d').tolist(), 'y': (sector_exposure_df[sector] * 100).tolist(), 'name': sector, 'type': 'bar'})
        sector_layout = {'title': 'Historical Sector Exposure (%)', 'barmode': 'stack', 'yaxis': {'ticksuffix': '%'}}

        results_payload = {
            "kpis": kpis.to_dict(), # Convert KPI series to a simple dictionary
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
    
    # --- FINAL JSON SERIALIZATION FIX ---
    # Use our custom default encoder to handle any remaining numpy/pandas types
    # This ensures the final dictionary is 100% JSON-safe.
    final_json_safe_payload = json.loads(json.dumps(results_payload, default=to_json_safe))

    log_progress("--- [Backtest Engine] Complete. ---")
    return final_json_safe_payload
import pandas as pd
import numpy as np
import quantstats as qs
from tqdm import tqdm
from datetime import date
from dateutil.relativedelta import relativedelta
import joblib
import json
import lightgbm as lgb

from .data_fetcher import get_stock_universe, get_historical_data
from .ml_models import optimize_portfolio, get_portfolio_sector_exposure
from .strategy import generate_all_features
from .reporting import generate_gemini_report # Import the new AI function

def to_json_safe(obj):
    if isinstance(obj, np.generic): return obj.item()
    if isinstance(obj, (np.ndarray,)): return obj.tolist()
    if isinstance(obj, pd.Timestamp): return obj.isoformat()
    if isinstance(obj, pd.Index): return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def run_backtest(start_date_str, end_date_str, universe_name, top_n, risk_free_rate, rebalance_freq='BMS', progress_callback=None):
    def log_progress(message):
        if progress_callback: progress_callback(message)

    log_progress("--- [Backtest Engine] Initializing (Walk-Forward Mode) ---")
    
    # We no longer load a single model. The model will be trained on the fly.
    all_symbols = get_stock_universe(universe_name)
    earliest_date = pd.to_datetime(start_date_str) - relativedelta(years=5) # Need 5 years for initial training

    log_progress("--- [Backtest Engine] Loading all raw data from DB... ---")
    master_raw_data = {
        symbol: get_historical_data(symbol, earliest_date, end_date_str)
        for symbol in tqdm(all_symbols, desc="Loading Stock Data")
    }
    master_raw_data = {k: v for k, v in master_raw_data.items() if not v.empty}
    
    benchmark_master_df = get_historical_data('^NSEI', earliest_date, end_date_str)
    if benchmark_master_df.empty:
        raise ValueError("Could not load master benchmark data. Backtest cannot proceed.")
    
    log_progress("--- [Backtest Engine] Starting Walk-Forward Simulation... ---")
    rebalance_dates = pd.date_range(start=start_date_str, end=end_date_str, freq=rebalance_freq)
    all_holdings = {}
    rebalance_logs = []
    model = None
    last_train_date = pd.Timestamp.min

    feature_cols = ['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength', 'Momentum_3M', 'Momentum_6M', 'Momentum_12M', 'Sharpe_3M']

    for rebalance_date in tqdm(rebalance_dates, desc="Backtesting Progress"):
        # --- WALK-FORWARD MODEL TRAINING ---
        # Retrain the model every year
        if model is None or (rebalance_date - last_train_date).days > 365:
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
                if not training_ready_df.empty:
                    all_training_data.append(training_ready_df)

            if all_training_data:
                full_dataset = pd.concat(all_training_data)
                X_train = full_dataset[feature_cols]
                y_train = full_dataset['Target']
                model = lgb.LGBMRegressor(objective='regression_l1', n_estimators=500, n_jobs=-1, random_state=42)
                model.fit(X_train, y_train)
                last_train_date = rebalance_date
                log_progress("--- Model retraining complete. ---")
            else:
                log_progress("--- Not enough data for retraining, using previous model. ---")

        # --- REBALANCING LOGIC (Unchanged, but now uses the freshly trained model) ---
        nifty_past_data = benchmark_master_df.loc[benchmark_master_df.index < rebalance_date]
        current_log = {'Date': rebalance_date.strftime('%Y-%m-%d'), 'Action': 'Hold Cash', 'Details': {}}

        if len(nifty_past_data) < 200:
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue
        
        nifty_ma_200 = nifty_past_data['Close'].rolling(window=200).mean().iloc[-1]
        if nifty_past_data['Close'].iloc[-1] < nifty_ma_200:
            current_log['Details'] = "Regime filter triggered (Market in Downtrend)"
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        if model is None:
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        predictions = {}
        for symbol, raw_data in master_raw_data.items():
            stock_past_data = raw_data.loc[raw_data.index < rebalance_date]
            if len(stock_past_data) < 252: continue
            features_df = generate_all_features(stock_past_data, nifty_past_data)
            if features_df.empty: continue
            latest_features = features_df[feature_cols].dropna()
            if not latest_features.empty:
                predictions[symbol] = model.predict(latest_features.tail(1))[0]
        
        if not predictions:
            all_holdings[rebalance_date] = {}; rebalance_logs.append(current_log); continue

        top_stocks = [s for s, p in sorted(predictions.items(), key=lambda item: item[1], reverse=True)[:top_n]]
        portfolio_data = {s: master_raw_data[s].loc[master_raw_data[s].index < rebalance_date] for s in top_stocks}
        
        if len(portfolio_data) >= 2:
            weights = optimize_portfolio(portfolio_data, risk_free_rate); all_holdings[rebalance_date] = weights
            current_log['Action'] = 'Rebalanced Portfolio'; current_log['Details'] = weights
        else: all_holdings[rebalance_date] = {}
        rebalance_logs.append(current_log)

    # --- FINAL REPORTING ---
    log_progress("\n--- Calculating final performance metrics... ---")
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
        log_progress("--- Generating AI Analysis Report... ---")
        ai_report = generate_gemini_report(kpis.to_dict(), {}, yearly_returns_df['Strategy'].to_dict(), rebalance_logs)
        log_progress("--- AI Report Generated. ---")
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
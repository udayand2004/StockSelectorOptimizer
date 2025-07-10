import pandas as pd
import numpy as np
# yfinance is no longer needed here for the main logic
import quantstats as qs
from tqdm import tqdm
from datetime import date
from dateutil.relativedelta import relativedelta
import joblib

from .data_fetcher import get_stock_universe, get_historical_data
from .ml_models import optimize_portfolio
from .strategy import generate_all_features

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

    feature_cols = [
        'MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength',
        'Momentum_3M', 'Momentum_6M', 'Momentum_12M', 'Sharpe_3M'
    ]

    for i, rebalance_date in enumerate(tqdm(rebalance_dates, desc="Backtesting Progress")):
        log_progress(f"Processing rebalance date: {rebalance_date.date()}")
        nifty_data = get_historical_data('^NSEI', rebalance_date - pd.Timedelta(days=300), rebalance_date)

        if nifty_data.empty or len(nifty_data) < 200:
            tqdm.write(f"--> Not enough NIFTY data in DB for {rebalance_date.date()}. Holding cash.")
            all_holdings[rebalance_date] = {}
            continue

        nifty_ma_200 = nifty_data['Close'].rolling(window=200).mean().iloc[-1]
        nifty_current_price = nifty_data['Close'].iloc[-1]
        if nifty_current_price < nifty_ma_200:
            tqdm.write(f"--> Market in Downtrend on {rebalance_date.date()}. Holding cash.")
            all_holdings[rebalance_date] = {}
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
            continue
        top_stocks = [s for s, p in sorted(predictions.items(), key=lambda item: item[1], reverse=True)[:top_n]]
        portfolio_data = {
            s: master_raw_data[s].loc[master_raw_data[s].index < rebalance_date]
            for s in top_stocks if s in master_raw_data
        }
        if len(portfolio_data) >= 2:
            weights = optimize_portfolio(portfolio_data, risk_free_rate=0.06)
            all_holdings[rebalance_date] = weights
        else:
            all_holdings[rebalance_date] = {}


    log_progress("\n--- [Backtest Engine] Calculating final performance metrics... ---")
    if not all_holdings:
        raise ValueError("No holdings were generated during the entire backtest period.")

    holdings_df = pd.DataFrame.from_dict(all_holdings, orient='index').fillna(0)
    holdings_df.sort_index(inplace=True)

    price_df = pd.DataFrame({
        symbol: master_raw_data[symbol]['Close']
        for symbol in holdings_df.columns if symbol in master_raw_data
    }).loc[start_date_str:end_date_str]
    price_df.sort_index(inplace=True)

    returns_df = price_df.pct_change(fill_method=None)
    aligned_holdings = holdings_df.reindex(returns_df.index, method='ffill').fillna(0)

    common_cols = aligned_holdings.columns.intersection(returns_df.columns)
    portfolio_returns = (aligned_holdings[common_cols] * returns_df[common_cols]).sum(axis=1)
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
        # Use the same logic for empty yearly returns
        empty_yearly = empty_monthly.resample('Y').apply(lambda x: (1 + x).prod() - 1).T
        empty_yearly.columns = empty_yearly.columns.year
        
        results_payload = {
            "kpis": {"CAGR": "0.00%", "Sharpe": "0.00", "Max_Drawdown": "0.00%", "Calmar": "0.00", "Beta": "0.00", "Sortino": "0.00", "VaR": "0.00%", "CVaR": "0.00%"},
            "charts": {
                "equity": { "dates": full_benchmark_equity.index.strftime('%Y-%m-%d').tolist(), "portfolio": [1.0] * len(full_benchmark_equity), "benchmark": full_benchmark_equity.values.tolist() },
                "drawdown": { "dates": full_benchmark_equity.index.strftime('%Y-%m-%d').tolist(), "values": [0.0] * len(full_benchmark_equity) }
            },
            "tables": { "monthly_returns": empty_monthly.to_json(orient='split'), "yearly_returns": empty_yearly.to_json(orient='split') }
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
        
        # --- THIS IS THE FIX ---
        # Calculate yearly returns manually from the daily returns series
        yearly_returns_df = portfolio_returns_clean.resample('Y').apply(lambda x: (1 + x).prod() - 1).to_frame(name='Strategy')
        yearly_returns_df.index = yearly_returns_df.index.year
        # --- END OF FIX ---

        strategy_equity = (1 + portfolio_returns_clean).cumprod()
        benchmark_equity = (1 + benchmark_returns_clean).cumprod()

        results_payload = {
            "kpis": {
                "CAGR": f"{kpis.get('CAGR (%)', 0.0):.2f}%", "Sharpe": f"{kpis.get('Sharpe', 0.0):.2f}",
                "Max_Drawdown": f"{kpis.get('Max Drawdown [%]', 0.0):.2f}%", "Calmar": f"{kpis.get('Calmar', 0.0):.2f}",
                "Beta": f"{kpis.get('Beta', 0.0):.2f}", "Sortino": f"{kpis.get('Sortino', 0.0):.2f}",
                "VaR": f"{kpis.get('Daily VaR', 0.0) * 100:.2f}%", "CVaR": f"{kpis.get('Daily CVaR', 0.0) * 100:.2f}%"
            },
            "charts": {
                "equity": { "dates": strategy_equity.index.strftime('%Y-%m-%d').tolist(), "portfolio": strategy_equity.values.tolist(), "benchmark": benchmark_equity.values.tolist() },
                "drawdown": { "dates": drawdown_series.index.strftime('%Y-%m-%d').tolist(), "values": (drawdown_series.values * 100).tolist() }
            },
            "tables": {
                "monthly_returns": monthly_returns_df.to_json(orient='split'),
                "yearly_returns": yearly_returns_df.to_json(orient='split')
            }
        }

    log_progress("--- [Backtest Engine] Complete. ---")
    return results_payload
import pandas as pd
import numpy as np
import yfinance as yf
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
        raise FileNotFoundError("Could not find 'app/stock_selector_model.joblib'. Please run train_and_save_model.py first.")

    all_symbols = get_stock_universe(universe_name)
    earliest_date_for_features = pd.to_datetime(start_date_str) - relativedelta(days=400) # Buffer for 252-day momentum

    log_progress(f"--- [Backtest Engine] Fetching historical data for {len(all_symbols)} stocks... ---")
    master_raw_data = {}
    for symbol in tqdm(all_symbols, desc="Fetching Raw Data"):
        df = get_historical_data(symbol, earliest_date_for_features, end_date_str)
        if not df.empty:
            master_raw_data[symbol] = df
    log_progress("--- [Backtest Engine] Data fetching complete. ---")

    log_progress("\n--- [Backtest Engine] Starting rebalancing simulation... ---")
    rebalance_dates = pd.date_range(start=start_date_str, end=end_date_str, freq=rebalance_freq)
    all_holdings = {}
    
    # --- UPDATED FEATURE LIST ---
    feature_cols = [
        'MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength',
        'Momentum_3M', 'Momentum_6M', 'Momentum_12M', 'Sharpe_3M'
    ]
    # --- END UPDATED FEATURE LIST ---

# ... inside the run_backtest function, in the main loop ...

    for i, rebalance_date in enumerate(tqdm(rebalance_dates, desc="Backtesting Progress")):
        
        # --- REGIME FILTER (CORRECTED TICKER) ---
        # The correct ticker for NIFTY 50 is ^NSEI, not ^NSEI.NS
        nifty_data = get_historical_data('^NSEI', rebalance_date - pd.Timedelta(days=300), rebalance_date)
        # --- END OF CORRECTION ---
        
        if len(nifty_data) < 200:
            tqdm.write(f"--> Not enough NIFTY data on {rebalance_date.date()}. Holding cash.")
            all_holdings[rebalance_date] = {}
            continue
# ... rest of the file is the same
        nifty_ma_200 = nifty_data['Close'].rolling(window=200).mean().iloc[-1]
        nifty_current_price = nifty_data['Close'].iloc[-1]
        if nifty_current_price < nifty_ma_200:
            tqdm.write(f"--> Market in Downtrend on {rebalance_date.date()}. Holding cash.")
            all_holdings[rebalance_date] = {}
            continue
        # --- END REGIME FILTER ---

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

    returns_df = price_df.pct_change().fillna(0)
    
    aligned_holdings = holdings_df.reindex(returns_df.index, method='ffill').fillna(0)
    
    # ... at the end of the run_backtest function ...
    
    common_cols = aligned_holdings.columns.intersection(returns_df.columns)
    portfolio_returns = (aligned_holdings[common_cols] * returns_df[common_cols]).sum(axis=1)
    portfolio_returns.name = 'Strategy'

    benchmark_returns = yf.download('^NSEI', start=start_date_str, end=end_date_str, auto_adjust=True, progress=False)['Close'].pct_change()
    benchmark_returns.name = 'Benchmark'

    # --- START OF NEW, ROBUST FIX ---
    # If the strategy never traded, portfolio_returns will be all zeros.
    # In this case, quantstats can fail. We handle this gracefully.
    if portfolio_returns.abs().sum() == 0:
        log_progress("--- [Backtest Engine] No trades were made. Returning zeroed stats. ---")
        # Create an empty results payload
        results_payload = {
            "kpis": { "CAGR": "0.00%", "Sharpe": "0.00", "Max Drawdown": "0.00%", "Calmar": "0.00" },
            "charts": {
                "equity": { "dates": benchmark_returns.index.strftime('%Y-%m-%d').tolist(), "portfolio": [1.0] * len(benchmark_returns), "benchmark": (1 + benchmark_returns.fillna(0)).cumprod().values.tolist() },
                "drawdown": { "dates": benchmark_returns.index.strftime('%Y-%m-%d').tolist(), "values": [0.0] * len(benchmark_returns) }
            }
        }
    else:
        # If there were trades, run quantstats as normal.
        log_progress("--- [Backtest Engine] Generating QuantStats report... ---")
        kpis_df = qs.reports.metrics(portfolio_returns, display=False)
        kpis = kpis_df['Strategy']
        drawdown_series = qs.stats.to_drawdown_series(portfolio_returns)

        results_payload = {
            "kpis": { 
                "CAGR": f"{kpis.get('CAGR (%)', 0.0):.2f}%", 
                "Sharpe": f"{kpis.get('Sharpe', 0.0):.2f}", 
                "Max Drawdown": f"{kpis.get('Max Drawdown [%]', 0.0):.2f}%",
                "Calmar": f"{kpis.get('Calmar', 0.0):.2f}",
            },
            "charts": {
                "equity": { "dates": portfolio_returns.index.strftime('%Y-%m-%d').tolist(), "portfolio": (1 + portfolio_returns).cumprod().values.tolist(), "benchmark": (1 + benchmark_returns).cumprod().reindex(portfolio_returns.index, method='ffill').fillna(1.0).values.tolist() },
                "drawdown": { "dates": drawdown_series.index.strftime('%Y-%m-%d').tolist(), "values": (drawdown_series.values * 100).tolist() }
            }
        }
    # --- END OF NEW, ROBUST FIX ---

    log_progress("--- [Backtest Engine] Complete. ---")
    return results_payload
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from pypfopt import HRPOpt
from .data_fetcher import get_historical_data
from datetime import date, timedelta
from .strategy import generate_all_features # Using the single, unified strategy function

def predict_top_stocks(model, symbols, top_n=10):
    """
    Predicts top stocks using the unified and robust strategy function.
    This version is consistent with the backtester and training script.
    """
    if model is None: return []

    end_date = date.today()
    start_date = end_date - timedelta(days=200)
    
    predictions = {}
    for symbol in symbols:
        # Step 1: Get the self-contained data for the stock.
        data = get_historical_data(symbol, start_date, end_date)
        if data.empty:
            continue

        # Step 2: Use the single, definitive strategy function to get all features.
        all_features_df = generate_all_features(data)
        
        # Step 3: Prepare the data for prediction.
        # We need the last row with a complete set of features (ignoring the 'Target' column).
        feature_cols = ['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']
        latest_features = all_features_df[feature_cols].dropna()

        if latest_features.empty:
            print(f"--> Skipping {symbol}: not enough data to compute all features for prediction.")
            continue
        
        # Step 4: Predict using the most recent valid feature set.
        prediction = model.predict(latest_features.tail(1))[0]
        predictions[symbol] = prediction
    
    if not predictions:
        return []

    sorted_stocks = sorted(predictions.items(), key=lambda item: item[1], reverse=True)
    return [stock[0] for stock in sorted_stocks[:top_n]]

# --- The rest of the file is correct and does not need to be changed ---

def get_portfolio_data(symbols):
    end_date = date.today()
    start_date = end_date - timedelta(days=365)
    portfolio_data = {}
    for symbol in symbols:
        data = get_historical_data(symbol, start_date, end_date)
        if not data.empty:
            portfolio_data[symbol] = data
    return portfolio_data

def optimize_portfolio(portfolio_data, risk_free_rate):
    symbols = list(portfolio_data.keys())
    if len(symbols) < 2: return {symbols[0]: 1.0} if symbols else {}
    close_prices = {symbol: data['Close'] for symbol, data in portfolio_data.items()}
    portfolio_df = pd.DataFrame(close_prices).ffill().bfill()
    returns = portfolio_df.pct_change().dropna()
    mean_returns = returns.mean()
    cov_matrix = returns.cov()
    num_assets = len(symbols)
    def neg_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate):
        p_ret = np.sum(mean_returns * weights) * 252
        p_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
        return -(p_ret - risk_free_rate) / p_std if p_std != 0 else -np.inf
    args = (mean_returns, cov_matrix, risk_free_rate)
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    max_weight = 0.25 
    bounds = tuple((0, max_weight) for _ in range(num_assets))
    initial_weights = num_assets * [1. / num_assets,]
    result = minimize(neg_sharpe_ratio, initial_weights, args=args, method='SLSQP', bounds=bounds, constraints=constraints)
    weights = result.x
    weights[weights < 0.001] = 0
    weights /= np.sum(weights)
    return dict(zip(symbols, np.round(weights, 4)))

def optimize_hrp_portfolio(portfolio_data):
    symbols = list(portfolio_data.keys())
    if len(symbols) < 2: return {symbols[0]: 1.0} if symbols else {}
    close_prices = {symbol: data['Close'] for symbol, data in portfolio_data.items()}
    portfolio_df = pd.DataFrame(close_prices).ffill().bfill()
    returns = portfolio_df.pct_change().dropna()
    hrp = HRPOpt(returns)
    hrp_weights = hrp.optimize()
    return {k: round(v, 4) for k, v in hrp_weights.items()}

def get_portfolio_sector_exposure(portfolio_data, weights):
    sector_exposure = {}
    for symbol, weight in weights.items():
        if symbol in portfolio_data and not portfolio_data[symbol].empty:
            sector = portfolio_data[symbol]['Sector'].iloc[0]
            sector_exposure[sector] = sector_exposure.get(sector, 0) + weight
    return sector_exposure

def generate_portfolio_rationale(weights, sector_exposure):
    if not weights or not sector_exposure:
        return "<p class='text-danger'>Could not generate rationale due to insufficient data.</p>"
    top_holdings = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
    top_sectors = sorted(sector_exposure.items(), key=lambda x: x[1], reverse=True)[:2]
    holdings_str = ", ".join([f"<strong>{s} ({w*100:.1f}%)</strong>" for s, w in top_holdings if w > 0])
    sectors_str = ", ".join([f"<strong>{s} ({w*100:.1f}%)</strong>" for s, w in top_sectors if w > 0])
    rationale = f"""
    <h4>Portfolio Rationale:</h4>
    <p>This portfolio has been constructed by selecting stocks with the highest predicted forward returns from our ML model, and then optimizing their weights according to the chosen methodology.</p>
    <h5>Key Characteristics:</h5>
    <ul>
        <li><strong>Primary Holdings:</strong> The portfolio is led by {holdings_str}.</li>
        <li><strong>Sector Concentration:</strong> The allocation is primarily focused on the {sectors_str} sectors.</li>
    </ul>
    <p class="text-muted small"><em>Disclaimer: This is an AI-generated analysis for illustrative purposes. Not investment advice.</em></p>
    """
    return rationale
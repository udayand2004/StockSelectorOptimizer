# app/ml_models.py

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from scipy.optimize import minimize
from .data_fetcher import get_historical_data
from datetime import date, timedelta

def create_features_for_training(df):
    if df.empty or len(df) < 80: # Need enough data for 50-day MA + 22-day target
        return pd.DataFrame()

    df_feat = df.copy()
    
    df_feat['MA_20'] = df_feat['Close'].rolling(window=20).mean()
    df_feat['MA_50'] = df_feat['Close'].rolling(window=50).mean()
    df_feat['ROC_20'] = df_feat['Close'].pct_change(20)
    df_feat['Volatility_20D'] = df_feat['Close'].rolling(window=20).std()
    
    delta = df_feat['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9)
    df_feat['RSI'] = 100 - (100 / (1 + rs))

    df_feat['Target'] = df_feat['Close'].pct_change(periods=22).shift(-22)
    
    return df_feat.dropna()

def create_features_for_prediction(df):
    if df.empty or len(df) < 50:
        return pd.DataFrame()
        
    df_feat = df.copy()
    df_feat['MA_20'] = df_feat['Close'].rolling(window=20).mean()
    df_feat['MA_50'] = df_feat['Close'].rolling(window=50).mean()
    df_feat['ROC_20'] = df_feat['Close'].pct_change(20)
    df_feat['Volatility_20D'] = df_feat['Close'].rolling(window=20).std()
    
    delta = df_feat['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9)
    df_feat['RSI'] = 100 - (100 / (1 + rs))
    
    return df_feat[['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']]


def train_stock_selector(symbols):
    end_date = date.today()
    start_date = end_date - timedelta(days=5 * 365)
    all_features = []
    
    for symbol in symbols:
        data = get_historical_data(symbol, start_date, end_date)
        if not data.empty:
            features = create_features_for_training(data)
            if not features.empty:
                all_features.append(features)
    
    if not all_features: 
        print("Could not generate any training features.")
        return None

    full_dataset = pd.concat(all_features)
    if full_dataset.empty:
        print("Training dataset is empty after combining features.")
        return None
        
    X = full_dataset[['MA_20', 'MA_50', 'ROC_20', 'Volatility_20D', 'RSI', 'Relative_Strength']]
    y = full_dataset['Target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Gradient Boosting model...")
    model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)
    model.fit(X_train, y_train)
    
    score = model.score(X_test, y_test)
    print(f"Model R^2 score: {score}")
    return model

def predict_top_stocks(model, symbols, top_n=10):
    if model is None: return []

    end_date = date.today()
    start_date = end_date - timedelta(days=150)
    
    predictions = {}
    for symbol in symbols:
        data = get_historical_data(symbol, start_date, end_date)
        if data.empty or len(data) < 50:
            continue

        features = create_features_for_prediction(data)
        latest_features = features.iloc[-1:]

        if latest_features.isnull().values.any():
            print(f"--> Skipping {symbol}: insufficient recent data for feature calculation.")
            continue
            
        prediction = model.predict(latest_features)[0]
        predictions[symbol] = prediction
    
    if not predictions:
        return []

    sorted_stocks = sorted(predictions.items(), key=lambda item: item[1], reverse=True)
    return [stock[0] for stock in sorted_stocks[:top_n]]

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
    portfolio_df = pd.DataFrame(close_prices).ffill().bfill() # Fill missing values
    
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
    bounds = tuple((0, 1) for _ in range(num_assets))
    initial_weights = num_assets * [1. / num_assets,]
    
    result = minimize(neg_sharpe_ratio, initial_weights, args=args, method='SLSQP', bounds=bounds, constraints=constraints)
    return dict(zip(symbols, np.round(result.x, 4)))

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
    
    holdings_str = ", ".join([f"<strong>{s} ({w*100:.1f}%)</strong>" for s, w in top_holdings])
    sectors_str = ", ".join([f"<strong>{s} ({w*100:.1f}%)</strong>" for s, w in top_sectors])

    rationale = f"""
    <h4>Portfolio Rationale:</h4>
    <p>This portfolio has been constructed by selecting stocks with the highest predicted forward returns from our ML model, and then optimizing their weights to maximize the risk-adjusted return (Sharpe Ratio).</p>
    <h5>Key Characteristics:</h5>
    <ul>
        <li><strong>Primary Holdings:</strong> The portfolio is led by {holdings_str}. These stocks were identified as having the strongest positive momentum and technical indicators.</li>
        <li><strong>Sector Concentration:</strong> The allocation is primarily focused on the {sectors_str} sectors, indicating a strategic bet on these areas of the market.</li>
    </ul>
    <p class="text-muted small"><em>Disclaimer: This is an AI-generated analysis for illustrative purposes. Not investment advice.</em></p>
    """
    return rationale
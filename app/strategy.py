import pandas as pd
import numpy as np

def generate_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    The single, definitive function to generate all features for a stock.
    This version includes standard indicators plus advanced momentum and 
    risk-adjusted return features.
    
    Returns:
        A DataFrame with all feature columns and the 'Target' column.
    """
    # We need at least 252 days of data for the 12-month momentum feature
    if df.empty or len(df) < 252:
        return pd.DataFrame()

    df_feat = df.copy()
    
    # --- Standard Technical Indicators ---
    df_feat['MA_20'] = df_feat['Close'].rolling(window=20).mean()
    df_feat['MA_50'] = df_feat['Close'].rolling(window=50).mean()
    df_feat['ROC_20'] = df_feat['Close'].pct_change(20)
    df_feat['Volatility_20D'] = df_feat['Close'].rolling(window=20).std()
    
    delta = df_feat['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9)
    df_feat['RSI'] = 100 - (100 / (1 + rs))

    # --- NEW: Advanced Momentum Features ---
    # Captures longer-term trends, which are powerful predictors.
    df_feat['Momentum_3M'] = df_feat['Close'].pct_change(66)
    df_feat['Momentum_6M'] = df_feat['Close'].pct_change(132)
    df_feat['Momentum_12M'] = df_feat['Close'].pct_change(252)

    # --- NEW: Risk-Adjusted Return Feature ---
    # Calculates a rolling 3-month Sharpe ratio to favor "smoother" returns.
    rolling_returns = df_feat['Close'].pct_change()
    rolling_sharpe = rolling_returns.rolling(window=66).mean() / rolling_returns.rolling(window=66).std()
    df_feat['Sharpe_3M'] = rolling_sharpe * np.sqrt(252) # Annualized

    # --- Target Variable (for training) ---
    # The forward-looking 22-day return we want the model to predict.
    df_feat['Target'] = df_feat['Close'].pct_change(periods=22).shift(-22)
    
    return df_feat
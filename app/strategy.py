import pandas as pd
import numpy as np

def generate_all_features(df: pd.DataFrame, benchmark_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generates all features for a stock, requiring benchmark data to correctly
    calculate relative strength without lookahead bias and using modern pandas syntax.
    """
    if df.empty or benchmark_df.empty or len(df) < 252:
        return pd.DataFrame()

    df_feat = df.copy()
    
    # --- Correct Relative Strength Calculation (Bias-Free) ---
    temp_df = df_feat.join(benchmark_df['Close'].rename('Benchmark_Close'), how='left')
    # FIX: Avoid inplace=True on a slice
    temp_df['Benchmark_Close'] = temp_df['Benchmark_Close'].ffill()
    df_feat['Relative_Strength'] = temp_df['Close'] / temp_df['Benchmark_Close']
    
    # --- Standard Technical Indicators ---
    df_feat['MA_20'] = df_feat['Close'].rolling(window=20).mean()
    df_feat['MA_50'] = df_feat['Close'].rolling(window=50).mean()
    df_feat['ROC_20'] = df_feat['Close'].pct_change(20)
    df_feat['Volatility_20D'] = df_feat['Close'].rolling(window=20).std()
    
    delta = df_feat['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    with np.errstate(divide='ignore', invalid='ignore'):
        rs = gain / loss
        df_feat['RSI'] = 100 - (100 / (1 + rs))
    # FIX: Avoid inplace=True
    df_feat['RSI'] = df_feat['RSI'].fillna(50)

    # --- Advanced Momentum Features ---
    df_feat['Momentum_3M'] = df_feat['Close'].pct_change(66)
    df_feat['Momentum_6M'] = df_feat['Close'].pct_change(132)
    df_feat['Momentum_12M'] = df_feat['Close'].pct_change(252)

    # --- Risk-Adjusted Return Feature ---
    rolling_returns = df_feat['Close'].pct_change()
    with np.errstate(divide='ignore', invalid='ignore'):
        rolling_sharpe = rolling_returns.rolling(window=66).mean() / rolling_returns.rolling(window=66).std()
        df_feat['Sharpe_3M'] = rolling_sharpe * np.sqrt(252)
    
    # --- Target Variable (for training) ---
    df_feat['Target'] = df_feat['Close'].pct_change(periods=22).shift(-22)
    
    return df_feat
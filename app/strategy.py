import pandas as pd

def generate_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    The single, definitive function to generate all features and the target variable.
    It takes a DataFrame that is assumed to already have a 'Relative_Strength' column.
    
    Returns:
        A DataFrame with all features and the 'Target' column.
        Note: The 'Target' for the last 22 rows will be NaN.
    """
    if df.empty or len(df) < 50:
        return pd.DataFrame()

    df_feat = df.copy()
    
    # Technical Indicators
    df_feat['MA_20'] = df_feat['Close'].rolling(window=20).mean()
    df_feat['MA_50'] = df_feat['Close'].rolling(window=50).mean()
    df_feat['ROC_20'] = df_feat['Close'].pct_change(20)
    df_feat['Volatility_20D'] = df_feat['Close'].rolling(window=20).std()
    
    delta = df_feat['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9)
    df_feat['RSI'] = 100 - (100 / (1 + rs))

    # Target Variable (for training)
    df_feat['Target'] = df_feat['Close'].pct_change(periods=22).shift(-22)
    
    return df_feat
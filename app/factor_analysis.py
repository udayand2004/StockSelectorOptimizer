import pandas as pd
import sqlite3
import statsmodels.api as sm
from datetime import datetime, timedelta
import os
from tqdm import tqdm

# App Imports
from .config import DB_FILE

# --- NEW SOURCE: Local CSV file provided by the user ---
# This is the exact name of the file you have in your project's root directory.
INDIAN_FACTORS_FILENAME = "2025-03_FourFactors_and_Market_Returns_Daily_SurvivorshipBiasAdjusted.csv"


def ingest_fama_french_data():
    """
    Ingests the daily Indian market factors from the LOCAL CSV file
    downloaded from the IIM Ahmedabad data library.
    """
    print("--- Ingesting Indian market factor data from local file... ---")
    
    # Construct the full path to the file.
    # This assumes your script is run from the project's root directory.
    file_path = INDIAN_FACTORS_FILENAME

    if not os.path.exists(file_path):
        print(f"--> FATAL ERROR: The required factor file '{INDIAN_FACTORS_FILENAME}' was not found.")
        print("Please ensure the file is in the same directory as 'run.py' and 'add_factors.py'.")
        return

    try:
        print(f"--- Reading local file: {file_path} ---")
        ff_df = pd.read_csv(file_path)

        print("--- Cleaning and processing factor data... ---")

        # Rename columns for consistency with our regression model.
        # WML (Winners-Minus-Losers) is Momentum, so we rename it to UMD.
        # MF (Market Factor) is the Market Premium, so we rename it to Mkt-RF.
        ff_df.rename(columns={
            'WML': 'UMD',
            'MF': 'Mkt-RF'
        }, inplace=True)
        
        # Ensure the date column is in datetime format and drop any invalid rows
        ff_df['Date'] = pd.to_datetime(ff_df['Date'], errors='coerce')
        ff_df.dropna(subset=['Date'], inplace=True)

        # Define the final set of columns we need for the regression
        factor_cols = ['Mkt-RF', 'SMB', 'HML', 'UMD', 'RF']

        # Check if all required columns exist after renaming
        if not all(col in ff_df.columns for col in factor_cols):
             raise ValueError("One or more required factor columns (Mkt-RF, SMB, HML, UMD, RF) are missing from the CSV file after renaming.")

        # Convert factor columns to numeric, changing any errors to NaN
        for col in factor_cols:
            ff_df[col] = pd.to_numeric(ff_df[col], errors='coerce')

        # Drop any rows that have missing values in our key factor columns
        ff_df.dropna(subset=factor_cols, inplace=True)
        ff_df['Date'] = ff_df['Date'].dt.strftime('%Y-%m-%d')

        # Store the cleaned data in the database, replacing any old data
        with sqlite3.connect(DB_FILE) as conn:
            ff_df[['Date'] + factor_cols].to_sql('fama_french_factors', conn, if_exists='replace', index=False)
        
        print("--- Successfully ingested Indian market factor data from local file. ---")

    except Exception as e:
        print(f"--> ERROR: Failed to ingest Indian factor data. Factor analysis will not be available. Error: {e}")


def analyze_factor_exposure(portfolio_returns: pd.Series):
    """
    Performs a multiple linear regression to determine the portfolio's exposure
    to common Indian market risk factors (Market, Size, Value, Momentum).
    """
    if portfolio_returns.empty or len(portfolio_returns) < 60:
        return {"error": "Not enough data points (<60) to perform factor analysis."}

    try:
        with sqlite3.connect(DB_FILE) as conn:
            ff_factors = pd.read_sql_query("SELECT * FROM fama_french_factors", conn, index_col='Date', parse_dates=['Date'])

        data = pd.merge(portfolio_returns.rename('Portfolio'), ff_factors, left_index=True, right_index=True, how='inner')
        
        if len(data) < 60:
            return {"error": f"Not enough overlapping data points (<60) between portfolio and factors to perform analysis."}

        y = data['Portfolio'] - data['RF']
        X = data[['Mkt-RF', 'SMB', 'HML', 'UMD']]
        X = sm.add_constant(X)
        
        model = sm.OLS(y, X).fit()
        
        betas, p_values, t_stats = model.params, model.pvalues, model.tvalues
        
        results = {
            'alpha_annualized_pct': betas.get('const', 0) * 252 * 100,
            'r_squared': model.rsquared,
            'betas': {
                'Market (Mkt-RF)': betas.get('Mkt-RF'),
                'Size (SMB)': betas.get('SMB'),
                'Value (HML)': betas.get('HML'),
                'Momentum (UMD)': betas.get('UMD'),
            },
            'p_values': {
                'Alpha': p_values.get('const'),
                'Market (Mkt-RF)': p_values.get('Mkt-RF'),
                'Size (SMB)': p_values.get('SMB'),
                'Value (HML)': p_values.get('HML'),
                'Momentum (UMD)': p_values.get('UMD'),
            },
            't_stats': {
                'Alpha': t_stats.get('const'),
                'Market (Mkt-RF)': t_stats.get('Mkt-RF'),
                'Size (SMB)': t_stats.get('SMB'),
                'Value (HML)': t_stats.get('HML'),
                'Momentum (UMD)': t_stats.get('UMD'),
            }
        }
        return results

    except Exception as e:
        print(f"--> FACTOR ANALYSIS ERROR: {e}")
        return {"error": str(e)}
def analyze_rolling_factor_exposure(portfolio_returns: pd.Series, window: int = 252):
    """
    Performs a rolling regression to get time-varying factor exposures.
    The window is in days (default 252 is approx. 1 year).
    """
    if portfolio_returns.empty or len(portfolio_returns) < window:
        return {"error": f"Not enough data for a rolling factor analysis (need > {window} days)."}

    try:
        with sqlite3.connect(DB_FILE) as conn:
            ff_factors = pd.read_sql_query("SELECT * FROM fama_french_factors", conn, index_col='Date', parse_dates=['Date'])

        data = pd.merge(portfolio_returns.rename('Portfolio'), ff_factors, left_index=True, right_index=True, how='inner')
        
        if len(data) < window:
            return {"error": "Not enough overlapping data for rolling analysis."}

        y = data['Portfolio'] - data['RF']
        X = data[['Mkt-RF', 'SMB', 'HML', 'UMD']]
        X = sm.add_constant(X)

        rolling_betas = {}

        # This can be slow, so we iterate manually with tqdm
        print("--- [Factor Analysis] Starting rolling factor regression... ---")
        for i in tqdm(range(window, len(X)), desc="Rolling Betas"):
            window_X = X.iloc[i-window:i]
            window_y = y.iloc[i-window:i]
            
            model = sm.OLS(window_y, window_X).fit()
            # We only store the betas (coefficients)
            rolling_betas[X.index[i]] = model.params
        
        if not rolling_betas:
            return {"error": "Could not generate any rolling beta results."}

        # Convert dictionary to DataFrame
        betas_df = pd.DataFrame.from_dict(rolling_betas, orient='index')
        betas_df.rename(columns={
            'const': 'Alpha',
            'Mkt-RF': 'Market (Mkt-RF)',
            'SMB': 'Size (SMB)',
            'HML': 'Value (HML)',
            'UMD': 'Momentum (UMD)'
        }, inplace=True)
        
        print("--- [Factor Analysis] Rolling regression complete. ---")
        # Return as JSON string in 'split' orientation for easy JS parsing
        return betas_df.to_json(orient='split')

    except Exception as e:
        print(f"--> ROLLING FACTOR ANALYSIS ERROR: {e}")
        return {"error": str(e)}
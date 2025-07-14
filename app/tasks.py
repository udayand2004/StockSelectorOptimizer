from celery import shared_task
from .backtesting import run_backtest, run_custom_portfolio_backtest
import traceback
import sqlite3
import json
from .config import PORTFOLIOS_DB_FILE

@shared_task(bind=True)
def run_backtest_task(self, start_date_str, end_date_str, universe_name, top_n, risk_free_rate):
    """Celery task for the ML-driven strategy."""
    def progress_callback(message):
        self.update_state(state='PROGRESS', meta={'status': message})
    try:
        # The function in backtesting.py is now correctly named run_backtest
        results = run_backtest(
            start_date_str=start_date_str, 
            end_date_str=end_date_str, 
            universe_name=universe_name, 
            top_n=top_n, 
            risk_free_rate=risk_free_rate, 
            progress_callback=progress_callback
        )
        return results
    except Exception as e:
        traceback.print_exc()
        raise e

@shared_task(bind=True)
def run_custom_backtest_task(self, portfolio_id, start_date_str, end_date_str, risk_free_rate):
    """Celery task for custom user-defined portfolios."""
    def progress_callback(message):
        self.update_state(state='PROGRESS', meta={'status': message})
    try:
        # Fetch portfolio details from the database
        with sqlite3.connect(PORTFOLIOS_DB_FILE) as conn:
            cursor = conn.cursor()
            res = cursor.execute("SELECT stocks_json FROM custom_portfolios WHERE id = ?", (portfolio_id,)).fetchone()
            if not res:
                raise ValueError(f"Portfolio with ID {portfolio_id} not found.")
            holdings = json.loads(res[0])

        results = run_custom_portfolio_backtest(
            holdings=holdings, 
            start_date_str=start_date_str, 
            end_date_str=end_date_str, 
            risk_free_rate=risk_free_rate, 
            progress_callback=progress_callback
        )
        return results
    except Exception as e:
        traceback.print_exc()
        raise e
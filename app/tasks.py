from celery import shared_task
from .backtesting import run_backtest as run_backtest_logic
import traceback

@shared_task(bind=True)
def run_backtest_task(self, start_date_str, end_date_str, universe_name, top_n, rebalance_freq):
    """Celery task to run the backtest and return a JSON payload."""
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Fetching and processing historical data...'})
        
        # run_backtest_logic now returns a dictionary
        results_dict = run_backtest_logic(start_date_str, end_date_str, universe_name, top_n, rebalance_freq)
        
        # The dictionary is passed as the result
        return {'state': 'SUCCESS', 'status': 'Backtest complete!', 'result': results_dict}
    except Exception as e:
        traceback.print_exc()
        return {'state': 'FAILURE', 'status': str(e)}
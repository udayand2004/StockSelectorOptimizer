from celery import shared_task
from .backtesting import run_backtest as run_backtest_logic
import traceback

@shared_task(bind=True)
def run_backtest_task(self, start_date_str, end_date_str, universe_name, top_n, rebalance_freq):
    """Celery task that reports progress back to the frontend."""
    
    # <<< ADDED: Define a callback function that updates the task state
    def progress_callback(message):
        self.update_state(state='PROGRESS', meta={'status': message})

    try:
        # Pass the callback to the backtesting engine
        results_dict = run_backtest_logic(
            start_date_str, end_date_str, universe_name, top_n, rebalance_freq,
            progress_callback=progress_callback
        )
        
        # The task is successful. The entire dictionary is the result.
        return {'state': 'SUCCESS', 'status': 'Backtest complete!', 'result': results_dict}
    
    except Exception as e:
        traceback.print_exc()
        return {'state': 'FAILURE', 'status': str(e)}
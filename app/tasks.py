from celery import shared_task
from .backtesting import run_backtest as run_backtest_logic
import traceback

# --- THIS IS THE FIX ---
# Add 'risk_free_rate' to the function's arguments
@shared_task(bind=True)
def run_backtest_task(self, start_date_str, end_date_str, universe_name, top_n, risk_free_rate):
# --- END OF FIX ---
    """Celery task that reports progress back to the frontend."""
    
    def progress_callback(message):
        self.update_state(state='PROGRESS', meta={'status': message})

    try:
        # Pass the new argument down to the backtesting logic
        results_dict = run_backtest_logic(
            start_date_str=start_date_str, 
            end_date_str=end_date_str, 
            universe_name=universe_name, 
            top_n=top_n,
            risk_free_rate=risk_free_rate, # This line was already correct
            progress_callback=progress_callback
        )
        return results_dict
    
    except Exception as e:
        traceback.print_exc()
        raise e
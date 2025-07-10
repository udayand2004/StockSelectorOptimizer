from flask import current_app as app, render_template, jsonify, request
from . import data_fetcher
from . import ml_models
from .tasks import run_backtest_task
from celery.result import AsyncResult
from datetime import date
import joblib
import os

@app.route('/')
def index():
    model_ready = os.path.exists(app.model_path)
    universes = list(data_fetcher.STOCK_UNIVERSES.keys())
    current_date = date.today().strftime('%Y-%m-%d')
    return render_template('index.html', model_ready=model_ready, universes=universes, current_date=current_date)

@app.route('/api/analyze_and_optimize', methods=['POST'])
def analyze_and_optimize():
    if app.stock_model is None:
        if not os.path.exists(app.model_path):
             return jsonify({'error': 'Model file not found. Please train the model.'}), 500
        print("--- [Live Analysis] Loading model on-demand... ---")
        app.stock_model = joblib.load(app.model_path)
        print("--- [Live Analysis] Model loaded. ---")

    config = request.get_json()
    universe_name = config.get('universe', 'NIFTY_50')
    top_n = int(config.get('top_n', 10))
    risk_free_rate = float(config.get('risk_free', 0.06))
    optimization_method = config.get('optimization_method', 'sharpe')

    symbols_in_universe = data_fetcher.get_stock_universe(universe_name)
    top_stocks = ml_models.predict_top_stocks(app.stock_model, symbols_in_universe, top_n)
    
    if not top_stocks:
        return jsonify({'error': f'ML model did not return any stock picks for the {universe_name} universe.'}), 404

    portfolio_data = ml_models.get_portfolio_data(top_stocks)
    
    if not portfolio_data:
        return jsonify({'error': 'Could not fetch portfolio data for the selected top stocks.'}), 500

    if optimization_method == 'hrp':
        optimal_weights = ml_models.optimize_hrp_portfolio(portfolio_data)
    else:
        optimal_weights = ml_models.optimize_portfolio(portfolio_data, risk_free_rate)
        
    sector_exposure = ml_models.get_portfolio_sector_exposure(portfolio_data, optimal_weights)
    rationale = ml_models.generate_portfolio_rationale(optimal_weights, sector_exposure)

    return jsonify({
        'top_stocks': top_stocks,
        'optimal_weights': optimal_weights,
        'sector_exposure': sector_exposure,
        'rationale': rationale
    })

# --- THIS IS THE SINGLE, CORRECTED VERSION OF THE BACKTEST ROUTE ---
@app.route('/api/run_backtest', methods=['POST'])
def start_backtest():
    config = request.get_json()
    
    # Correctly get the risk_free_rate from the config object sent by the JS
    risk_free_rate = float(config.get('risk_free', 0.06)) 

    task = run_backtest_task.delay(
        start_date_str=config.get('start_date'),
        end_date_str=config.get('end_date'),
        universe_name=config.get('universe'),
        top_n=int(config.get('top_n', 10)),
        risk_free_rate=risk_free_rate
    )
    return jsonify({"task_id": task.id}), 202
# --- END OF THE CORRECTED VERSION ---

@app.route('/api/backtest_status/<task_id>')
def backtest_status(task_id):
    task_result = AsyncResult(task_id, app=app.extensions["celery"])
    response = {}
    if task_result.state == 'PENDING':
        response = {'state': task_result.state, 'status': 'Pending...'}
    elif task_result.state == 'PROGRESS':
        response = {'state': task_result.state, 'status': task_result.info.get('status', '')}
    elif task_result.state == 'SUCCESS':
        # The result from a successful task is already JSON-safe
        response = {'state': 'SUCCESS', 'result': task_result.result}
    else: # FAILURE
        response = {'state': task_result.state, 'status': str(task_result.info)}
    return jsonify(response)
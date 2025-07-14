from flask import current_app as app, render_template, jsonify, request
from . import data_fetcher
from . import ml_models
from .tasks import run_backtest_task, run_custom_backtest_task
from celery.result import AsyncResult
from datetime import date
import joblib
import os
import sqlite3
import json
from .config import PORTFOLIOS_DB_FILE, STOCK_UNIVERSES

@app.route('/')
def index():
    model_ready = os.path.exists(app.model_path)
    universes = list(STOCK_UNIVERSES.keys())
    current_date = date.today().strftime('%Y-%m-%d')
    
    # --- THIS IS THE FIX FOR THE PORTFOLIO STUDIO ---
    # Get all stocks from the NIFTY 100 universe to populate the selector
    all_stocks_for_studio = sorted(list(set(
        STOCK_UNIVERSES.get("NIFTY_50", []) + 
        STOCK_UNIVERSES.get("NIFTY_NEXT_50", [])
    )))
    # --- END OF FIX ---
    
    return render_template(
        'index.html', 
        model_ready=model_ready, 
        universes=universes, 
        current_date=current_date,
        all_stocks_for_studio=all_stocks_for_studio # Pass the list to the template
    )

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


@app.route('/api/portfolios', methods=['GET'])
def get_portfolios():
    try:
        with sqlite3.connect(PORTFOLIOS_DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            portfolios = cursor.execute("SELECT id, name FROM custom_portfolios ORDER BY name").fetchall()
            return jsonify([dict(p) for p in portfolios])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/portfolios', methods=['POST'])
def save_portfolio():
    data = request.get_json()
    name = data.get('name')
    stocks = data.get('stocks')
    optimize = data.get('optimize', False)
    manual_weights = data.get('weights', {})

    if not name or not stocks:
        return jsonify({"error": "Portfolio name and stock list are required."}), 400

    weights = {}
    if optimize:
        portfolio_data = ml_models.get_portfolio_data(stocks)
        if len(portfolio_data) < 2:
            return jsonify({"error": "Need at least 2 valid stocks to optimize."}), 400
        weights = ml_models.optimize_hrp_portfolio(portfolio_data)
    else:
        total_weight = sum(manual_weights.values())
        if not (0.99 < total_weight < 1.01):
            return jsonify({"error": f"Weights must sum to 100%. Current sum: {total_weight*100:.1f}%"}), 400
        weights = {k: v for k, v in manual_weights.items() if k in stocks}

    try:
        with sqlite3.connect(PORTFOLIOS_DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO custom_portfolios (name, stocks_json) VALUES (?, ?)",
                (name, json.dumps(weights))
            )
            conn.commit()
        return jsonify({"success": True, "name": name, "weights": weights}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "A portfolio with this name already exists."}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/run_backtest', methods=['POST'])
def start_backtest():
    config = request.get_json()
    backtest_type = config.get('type', 'ml_strategy')
    risk_free_rate = float(config.get('risk_free', 0.06)) 

    if backtest_type == 'custom':
        portfolio_id = config.get('portfolio_id')
        if not portfolio_id:
            return jsonify({"error": "Portfolio ID is required for custom backtest."}), 400
        
        task = run_custom_backtest_task.delay(
            portfolio_id=portfolio_id,
            start_date_str=config.get('start_date'),
            end_date_str=config.get('end_date'),
            risk_free_rate=risk_free_rate
        )
    else: 
        task = run_backtest_task.delay(
            start_date_str=config.get('start_date'),
            end_date_str=config.get('end_date'),
            universe_name=config.get('universe'),
            top_n=int(config.get('top_n', 10)),
            risk_free_rate=risk_free_rate
        )
        
    return jsonify({"task_id": task.id}), 202

@app.route('/api/backtest_status/<task_id>')
def backtest_status(task_id):
    task_result = AsyncResult(task_id, app=app.extensions["celery"])
    response = {}
    if task_result.state == 'PENDING':
        response = {'state': task_result.state, 'status': 'Pending...'}
    elif task_result.state == 'PROGRESS':
        response = {'state': task_result.state, 'status': task_result.info.get('status', '')}
    elif task_result.state == 'SUCCESS':
        response = {'state': 'SUCCESS', 'result': task_result.result}
    else: 
        response = {'state': task_result.state, 'status': str(task_result.info)}
    return jsonify(response)
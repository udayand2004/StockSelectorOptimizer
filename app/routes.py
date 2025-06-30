# app/routes.py

from flask import current_app as app, render_template, jsonify, request
from . import data_fetcher
from . import ml_models

@app.route('/')
def index():
    model_ready = app.stock_model is not None
    universes = list(data_fetcher.STOCK_UNIVERSES.keys())
    return render_template('index.html', model_ready=model_ready, universes=universes)

@app.route('/api/analyze_and_optimize', methods=['POST'])
def analyze_and_optimize():
    if app.stock_model is None:
        return jsonify({'error': 'Model is not loaded. Please train the model and restart the server.'}), 500

    config = request.get_json()
    universe_name = config.get('universe', 'NIFTY_50')
    top_n = int(config.get('top_n', 10))
    risk_free_rate = float(config.get('risk_free', 0.06))

    symbols_in_universe = data_fetcher.get_stock_universe(universe_name)
    top_stocks = ml_models.predict_top_stocks(app.stock_model, symbols_in_universe, top_n)
    
    # --- ROBUSTNESS FIX: Handle case where model returns no stocks ---
    if not top_stocks:
        return jsonify({
            'error': f'ML model did not return any stock picks for the {universe_name} universe. This can happen due to recent market data quality issues. Please try again later or select a different universe.'
        }), 404 # 404 Not Found is an appropriate error code

    portfolio_data = ml_models.get_portfolio_data(top_stocks)
    
    if not portfolio_data:
        return jsonify({'error': 'Could not fetch portfolio data for the selected top stocks.'}), 500

    optimal_weights = ml_models.optimize_portfolio(portfolio_data, risk_free_rate)
    sector_exposure = ml_models.get_portfolio_sector_exposure(portfolio_data, optimal_weights)
    rationale = ml_models.generate_portfolio_rationale(optimal_weights, sector_exposure)

    return jsonify({
        'top_stocks': top_stocks,
        'optimal_weights': optimal_weights,
        'sector_exposure': sector_exposure,
        'rationale': rationale
    })
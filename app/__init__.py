# app/__init__.py

from flask import Flask
import joblib
import os
from .data_fetcher import cache

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'a-very-secret-key-that-you-should-change'
    app.config['CACHE_TYPE'] = 'FileSystemCache'
    app.config['CACHE_DIR'] = 'flask_cache'

    cache.init_app(app)

    with app.app_context():
        from . import routes

        model_path = 'app/stock_selector_model.joblib'
        if os.path.exists(model_path):
            print("Loading pre-trained model...")
            app.stock_model = joblib.load(model_path)
            print("Model loaded successfully.")
        else:
            print("WARNING: Model file not found. Please run 'train_and_save_model.py' first.")
            app.stock_model = None
            
    return app
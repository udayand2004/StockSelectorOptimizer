import os
import joblib
from flask import Flask
from .data_fetcher import cache
from celery import Celery, Task

def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app

def create_app():
    app = Flask(__name__)
    
    # Celery Configuration
    app.config.from_mapping(
        CELERY=dict(
            broker_url="redis://localhost:6379/0",
            result_backend="redis://localhost:6379/0",
            task_ignore_result=False,
        ),
    )

    # Load the production ML model
    model_path = 'app/stock_selector_model.joblib'
    if os.path.exists(model_path):
        app.stock_model = joblib.load(model_path)
        print("Production ML model loaded successfully.")
    else:
        app.stock_model = None
        print("WARNING: Production ML model not found. Live analysis will be disabled.")

    # Initialize extensions
    cache.init_app(app)
    celery_init_app(app)

    with app.app_context():
        from . import routes
        from . import tasks # This import registers the tasks with Celery
        return app
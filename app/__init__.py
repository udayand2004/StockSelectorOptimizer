import os
import joblib
from flask import Flask
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
    
    # We no longer need to initialize the cache here.
    
    model_path = 'app/stock_selector_model.joblib'
    app.stock_model = None 
    app.model_path = model_path 
    if not os.path.exists(model_path):
        print("WARNING: Production ML model not found. Live analysis will be disabled.")

    # Initialize Celery
    celery_init_app(app)

    with app.app_context():
        from . import routes
        from . import tasks 
        return app
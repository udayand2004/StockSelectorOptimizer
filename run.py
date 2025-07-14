# run.py
from app import create_app

# The application factory is called to create the Flask app instance.
app = create_app()

# Extract the Celery instance from the application extensions for the worker to use.
# The command `celery -A run.celery worker` will look for this 'celery' object.
celery = app.extensions["celery"]

if __name__ == '__main__':
    # This block is for running the Flask development server directly.
    # It will not be executed when the Celery worker starts.
    # The host='0.0.0.0' makes it accessible from your local network.
    app.run(debug=True, host='0.0.0.0')
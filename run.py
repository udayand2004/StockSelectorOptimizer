from app import create_app

# Create the Flask application instance
app = create_app()

# Extract the Celery instance from the application extensions
celery = app.extensions["celery"]

if __name__ == '__main__':
    # This block is for running the Flask development server
    # It will not be executed when the Celery worker starts
    app.run(debug=True)
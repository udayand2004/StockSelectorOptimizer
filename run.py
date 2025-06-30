# run.py

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Setting debug=False is better for production, but True is fine for development
    app.run(debug=True)
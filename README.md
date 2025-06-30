# AI-Powered Quantitative Investment Platform

This project is an advanced, end-to-end web application for quantitative stock selection and portfolio optimization. It leverages machine learning to predict stock returns and employs modern financial modeling techniques to construct optimized portfolios, providing a tool suitable for sophisticated investment analysis.

## Key Features

- **Interactive Web Interface:** Built with Flask and Bootstrap, allowing users to configure analysis parameters dynamically.
- **ML-Powered Stock Selection:** Uses a pre-trained Gradient Boosting model to predict one-month forward returns and select top-performing stocks from a given universe (e.g., NIFTY 50).
- **Markowitz Portfolio Optimization:** Calculates the optimal portfolio weights to maximize the Sharpe Ratio based on the selected stocks.
- **Data-Driven Visualizations:** Renders the results using Plotly.js, including portfolio allocation pie charts and sector exposure bar charts.
- **AI-Generated Rationale:** Provides a qualitative, human-readable summary explaining the constructed portfolio's characteristics.
- **High-Performance Architecture:** Employs an offline training script and server-side caching (`Flask-Caching`) to ensure a fast and responsive user experience.

## Technology Stack

- **Backend:** Python, Flask
- **Machine Learning:** Scikit-learn, Pandas, NumPy, XGBoost, LightGBM, Optuna
- **Financial Modeling:** SciPy, PyPortfolioOpt
- **Data Sourcing:** `yfinance`
- **Frontend:** HTML, Bootstrap 5, JavaScript, Plotly.js
- **Caching:** Flask-Caching (FileSystemCache)

## How to Run

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/DipayanDasgupta/StockSelectorOptimizer
    cd your-repo-name
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the offline training script:**
    (This only needs to be done once, or whenever you want to retrain the model)
    ```bash
    python train_and_save_model.py
    ```

5.  **Run the Flask application:**
    ```bash
    flask run
    ```

6.  Open your browser and navigate to `http://127.0.0.1:5000`.

---
*This project is for educational and illustrative purposes only and does not constitute investment advice.*
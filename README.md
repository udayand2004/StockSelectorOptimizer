AI-Powered Quantitative Investment Platform
This project is a professional-grade, end-to-end web application for quantitative investment strategy development. It moves beyond simple analysis by providing a robust, bias-free backtesting engine and a suite of tools for creating, testing, and analyzing custom portfolios.
The platform's core is a machine learning model that uses a walk-forward training methodology to prevent overfitting. It leverages a local database for high-speed data access and provides AI-powered analysis to interpret complex backtest results, making it a powerful tool for serious quantitative research.
Key Features
Two Powerful Backtesting Modes:
ML-Driven Strategy: A dynamic strategy that retrains its model periodically and selects top stocks based on predictive features.
Custom Portfolio Studio: An interactive interface to build, save, and backtest your own portfolios with either optimized or manually set weights.
Methodologically Sound Backtesting:
Walk-Forward Training: Eliminates lookahead bias and overfitting by periodically retraining the ML model on historical data, simulating a real-world scenario.
Regime Filter: An optional 200-day moving average filter on the NIFTY 50 to automatically switch to cash during market downturns.
Realistic Costs: Incorporates transaction costs (brokerage, slippage) to provide a more accurate picture of real-world performance.
Comprehensive Reporting & Visualization:
Detailed KPI Dashboard: Tracks over 30 performance metrics, including CAGR, Sharpe Ratio, Sortino Ratio, Max Drawdown, and Beta.
Interactive Charts: Uses Plotly.js to render equity curves, drawdown charts, and historical allocation breakdowns by stock and sector.
Downloadable Logs: Export detailed rebalancing logs as a CSV file for external analysis in Excel or other tools.
AI-Powered Analysis (Gemini):
Integrates with Google's Gemini AI to provide a qualitative, human-readable summary of the backtest results, highlighting performance, risks, and potential red flags.
High-Performance Architecture:
Local Database: All market data is ingested into a local SQLite database for instantaneous access during backtests, eliminating API calls and network latency.
Asynchronous Tasks: Uses Celery and Redis to run long backtests in the background without freezing the user interface.
Technology Stack
Backend: Python, Flask
Machine Learning: Scikit-learn, LightGBM, Pandas, NumPy
Financial Modeling: PyPortfolioOpt, SciPy
AI Integration: Google Generative AI (Gemini)
Data Stack: yfinance (for ingestion), SQLite (for local storage)
Asynchronous Tasks: Celery, Redis
Frontend: HTML, Bootstrap 5, JavaScript, Plotly.js
Setup and Installation Guide
Follow these steps precisely to get the entire platform running locally.
Step 1: Clone the Repository
Generated bash
git clone https://github.com/YourUsername/Your-Repo-Name.git
cd Your-Repo-Name
Use code with caution.
Bash
Step 2: Set Up Python Environment and Install Dependencies
Generated bash
# Create a virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all required packages
pip install -r requirements.txt
Use code with caution.
Bash
Step 3: Configure the AI Reporting (Optional but Recommended)
Visit Google AI Studio to get a free API key for the Gemini model.
Open the app/reporting.py file.
Set your API key using one of these two methods:
(Recommended) Set an environment variable in your terminal:
Generated bash
export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
Use code with caution.
Bash
(Alternative) Directly paste the key into the file (uncomment the line):
Generated python
# In app/reporting.py
# genai.configure(api_key="YOUR_API_KEY_HERE")
Use code with caution.
Python
Step 4: Build the Local Market Database (One-Time Setup)
This crucial step downloads 10 years of stock data and saves it locally for high-speed access. This will take 15-30 minutes to run the first time.
Generated bash
# Make sure your virtual environment is active
python data_ingestion.py
Use code with caution.
Bash
This script will create two new files in your project directory: market_data.db and user_portfolios.db. You only need to run this script once. To update the data with the latest prices later, simply run it again.
Step 5: Train the Initial Machine Learning Model
The backtester uses a walk-forward approach, but the "Live Analysis" tab needs a pre-trained model to start with.
Generated bash
# Make sure your virtual environment is active
python train_and_save_model.py
Use code with caution.
Bash
This will create the app/stock_selector_model.joblib file.
Step 6: Run the Application (All Components)
You need to run three separate processes in three different terminals.
Terminal 1: Start the Redis Server
(Redis acts as the message queue for background tasks)
Generated bash
redis-server
Use code with caution.
Bash
Terminal 2: Start the Celery Worker
(This process listens for and executes the backtests)
Generated bash
# Make sure your virtual environment is active
source venv/bin/activate
celery -A run.celery worker -l info
Use code with caution.
Bash
Terminal 3: Start the Flask Web Server
(This is the main web application)
Generated bash
# Make sure your virtual environment is active
source venv/bin/activate
flask run
Use code with caution.
Bash
Step 7: Access the Platform
Once all three components are running, open your web browser and navigate to:
http://127.0.0.1:5000
You can now use the "Portfolio Studio" to create custom portfolios and the "Strategy Backtesting" tab to test them or the ML-driven strategy.
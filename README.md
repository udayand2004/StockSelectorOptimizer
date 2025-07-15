# AI-Powered Quantitative Investment Platform

**A professional-grade, end-to-end web application for quantitative investment strategy development and bias-free backtesting.**

This platform provides a robust environment for creating, analyzing, and backtesting quantitative trading strategies. It moves beyond simple scripts by offering a complete web UI, a powerful walk-forward backtesting engine to prevent lookahead bias, and AI-powered analysis to interpret complex results.

The core of the platform is a machine learning model that is retrained periodically on historical data, simulating a real-world trading scenario. With a high-speed local database and asynchronous task execution, it's a powerful tool for serious quantitative research.

---

## 🚀 Key Features

- **Two Powerful Backtesting Modes**:
  - **ML-Driven Strategy**: A dynamic strategy that retrains its model periodically and selects top stocks based on predictive features.
  - **Custom Portfolio Studio**: An interactive UI to build, save, and backtest your own portfolios with either optimized or manual weights.
- **Methodologically Sound Backtesting**:
  - **Walk-Forward Training**: Eliminates lookahead bias and overfitting by simulating a real-world periodic retraining schedule.
  - **Indian Market Factor Analysis**: Decomposes portfolio returns using Fama-French & Momentum factors specifically for the Indian market for deeper risk/return attribution.
  - **Realistic Costs & Regime Filter**: Incorporates transaction costs and an optional market regime filter to automatically switch to cash during downturns.
- **Comprehensive Reporting & Visualization**:
  - **Interactive KPI Dashboard**: Tracks over 30 performance metrics including CAGR, Sharpe/Sortino Ratios, Max Drawdown, and factor-based Alpha.
  - **Rich Plotly.js Charts**: Renders dynamic equity curves, drawdown charts, and historical allocation breakdowns by stock and sector.
- **AI-Powered Analysis (Gemini)**:
  - Integrates with Google's Gemini Pro to provide a qualitative, human-readable summary of backtest results, highlighting performance, risks, and potential areas for improvement.
- **High-Performance Architecture**:
  - **Local SQLite Database**: All market data is ingested locally for instantaneous access during backtests, eliminating API latency.
  - **Asynchronous Backtesting**: Uses Celery and Redis to run long backtests in the background without freezing the UI.

---

## 🛠️ Technology Stack

| Category            | Technologies                                          |
|---------------------|-------------------------------------------------------|
| **Backend**         | Python, Flask                                         |
| **Frontend**        | HTML, Bootstrap 5, JavaScript, Plotly.js              |
| **Machine Learning**| Scikit-learn, LightGBM, Pandas, NumPy, Statsmodels    |
| **Data Stack**      | yfinance (for ingestion), SQLite (local storage), openpyxl |
| **Async Tasks**     | Celery, Redis                                         |
| **AI Integration**  | Google Generative AI (Gemini)                         |
| **Installation**    | uv (A high-speed Python package manager)              |

---

## ⚙️ Installation & Setup

This guide uses `uv`, an extremely fast Python package installer and resolver, to simplify setup.

### Prerequisites

You need to have **Git**, **Python 3.10+**, and **Redis** installed. You also need to install **`uv`**.

- **Install `uv` (macOS/Linux):**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh

Install uv (Windows):powershell

irm https://astral.sh/uv/install.ps1 | iex

Step-by-Step GuideClone the Repositorybash

git clone https://github.com/DipayanDasgupta/StockSelectorOptimizer.git
cd StockSelectorOptimizer

Create and Activate Virtual Environment using uv
This single command creates the .venv folder and activates it for your current shell session.bash

uv venv
source .venv/bin/activate  # On macOS/Linux
.venv\Scripts\activate     # On Windows

Install Dependencies using uv
This is significantly faster than using pip. The requirements.txt file includes all necessary dependencies, including openpyxl for factor ingestion.bash

uv pip install -r requirements.txt

Configure AI Reporting (Optional but Recommended)
Get a free API key for the Gemini model from Google AI Studio. Then, set it as an environment variable.On macOS/Linux:bash

export GOOGLE_API_KEY="YOUR_API_KEY_HERE"

On Windows (Command Prompt):bash

set GOOGLE_API_KEY="YOUR_API_KEY_HERE"

Note: You'll need to set this every time you open a new terminal, or add it to your shell's profile file like .zshrc or .bashrc.
Build Local Database & Train Initial Model
This crucial one-time step downloads all necessary market data for stocks and Indian market factors, saves it to a local database, and trains the initial ML model.Note: This will take 15-30 minutes to run the first time.bash

python data_ingestion.py
python train_and_save_model.py

requirements.txtThe requirements.txt file includes all Python dependencies required for the project, including openpyxl for factor ingestion. A sample structure of the file is shown below (ensure openpyxl is included at the end):

Flask
scikit-learn
lightgbm
pandas
numpy
statsmodels
yfinance
Flask-Caching
openpyxl

Note: The actual requirements.txt file may include additional dependencies or specific versions. Ensure all listed packages are included, with openpyxl added at the end if not already present. Running the ApplicationThe application requires three separate processes to run simultaneously. You must open three different terminals for this.Start the Redis Server
Redis acts as the message queue for background tasks.bash

redis-server

Start the Celery Worker
This process listens for and executes long-running backtests. Ensure your virtual environment is active before running this command.bash

source .venv/bin/activate  # On macOS/Linux
.venv\Scripts\activate     # On Windows
celery -A run.celery worker -l info

Start the Flask Web Server
This is the main web application you will interact with. Ensure your virtual environment is active before running this command.bash

source .venv/bin/activate  # On macOS/Linux
.venv\Scripts\activate     # On Windows
flask run

 You're all set! Open your web browser and navigate to:
**http://127.0.0.1:5000** Project Structure

.
├── app/                    # Core application source code
│   ├── static/             # CSS and JavaScript files
│   ├── templates/          # HTML templates
│   ├── __init__.py         # Application factory
│   ├── backtesting.py      # Main backtesting engine and reporting logic
│   ├── config.py           # Shared configuration (stock universes, DB names)
│   ├── data_fetcher.py     # Fetches data from the local database
│   ├── factor_analysis.py  # Logic for Indian market factor analysis
│   ├── ml_models.py        # ML prediction and portfolio optimization logic
│   ├── reporting.py        # AI report generation with Gemini
│   ├── routes.py           # Flask routes and API endpoints
│   └── tasks.py            # Celery task definitions
├── data_ingestion.py       # Script to build the stock and factor database
├── add_factors.py          # Utility script to add/update factor data only
├── train_and_save_model.py # Script to train the initial ML model
├── requirements.txt        # Python dependencies
├── run.py                  # Main entry point to run the Flask app
└── README.md               # This file

 RoadmapAdd more risk factors (e.g., Quality, Low Volatility) for analysis.
Dockerize the entire application for one-command setup.
Implement user authentication to save portfolios per user.
Add support for more international markets and their corresponding factors.
Integrate with a broker API for paper/live trading.

 ContributingContributions are welcome! Please feel free to open an issue or submit a pull request.Fork the Project
Create your Feature Branch (git checkout -b feature/AmazingFeature)
Commit your Changes (git commit -m 'Add some AmazingFeature')
Push to the Branch (git push origin feature/AmazingFeature)
Open a Pull Request

 LicenseDistributed under the MIT License. See LICENSE file for more information. ContactProject Link: https://github.com/DipayanDasgupta/StockSelectorOptimizer


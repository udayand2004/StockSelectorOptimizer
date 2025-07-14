# app/reporting.py
import google.generativeai as genai
import os

# --- THIS IS THE CORRECT AND ONLY PLACE FOR GENAI CONFIGURATION ---
try:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        print("--- Configuring Gemini using GOOGLE_API_KEY environment variable. ---")
        genai.configure(api_key=api_key)
    else:
        print("--- Configuring Gemini using hardcoded API key from app/reporting.py. ---")
        hardcoded_api_key = "AIzaSyANBOTpHkdlpISgG6BLWuUmoKiB8t6ugJo" # Replace with your actual key
        if "YOUR_API_KEY" in hardcoded_api_key or len(hardcoded_api_key) < 30:
             print("--- WARNING: The hardcoded API key seems to be a placeholder. AI reports may fail. ---")
        genai.configure(api_key=hardcoded_api_key)
except Exception as e:
    print(f"--- WARNING: Google AI SDK could not be configured. AI reports will be disabled. Error: {e} ---")


def generate_gemini_report(kpis, monthly_returns, yearly_returns, rebalance_logs):
    """
    Uses Google's Gemini model to generate a detailed analysis of the backtest report.
    """
    try:
        print("--- Generating AI-powered report with Gemini... ---")
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        kpi_summary = f"""
        - CAGR: {kpis.get('CAGR﹪', 0) * 100:.2f}%
        - Sharpe Ratio: {kpis.get('Sharpe', 0):.2f}
        - Max Drawdown: {kpis.get('Max Drawdown', 0) * 100:.2f}%
        - Sortino Ratio: {kpis.get('Sortino', 0):.2f}
        - Beta: {kpis.get('Beta', 0):.2f}
        """
        yearly_summary = "\n".join([f"- {year}: {ret:.2f}%" for year, ret in yearly_returns.items()])
        active_months = sum(1 for log in rebalance_logs if log['Action'] == 'Rebalanced Portfolio')
        total_months = len(rebalance_logs)
        
        prompt = f"""
        As a professional quantitative analyst, provide a detailed and critical analysis of the following backtest report for an ML-based stock selection strategy. The strategy uses a market regime filter (200-day moving average on the NIFTY 50).

        **Key Performance Indicators:**
        {kpi_summary}

        **Yearly Returns (%):**
        {yearly_summary}
        
        **Activity Log Summary:**
        - The strategy was actively invested for {active_months} out of {total_months} rebalancing periods. The rest of the time it held cash due to the regime filter.

        **Your analysis should cover the following points in structured markdown format:**
        1.  **Performance Overview:** Give a summary of the strategy's performance. Is the CAGR impressive given the risk? How does the Sharpe ratio reflect risk-adjusted returns?
        2.  **Risk Analysis:** Critically evaluate the Max Drawdown. Is it acceptable? How does the Sortino ratio compare to the Sharpe ratio, and what does this imply about downside risk? Comment on the Beta.
        3.  **Consistency and Regime Filter:** Analyze the yearly returns. Are they consistent? Comment on the effectiveness of the market regime filter based on the activity log. Did it successfully avoid major market downturns?
        4.  **Potential Concerns & Red Flags:** Based on all the data, what are the potential red flags? Is a Sharpe ratio of {kpis.get('Sharpe', 0):.2f} realistic? Could there still be overfitting?
        5.  **Conclusion & Recommendations:** Provide a concluding paragraph on whether this strategy is promising and suggest next steps for improvement or validation.
        """
        response = model.generate_content(prompt)
        print("--- AI report successfully generated. ---")
        return response.text

    except Exception as e:
        print(f"--- Gemini AI Report Failed: {e} ---")
        if "API key" in str(e).lower() or "permission" in str(e).lower():
            return f"<p class='text-danger small'><b>AI report failed to generate.</b><br>Error: The Google AI API key is not configured or is invalid. Please check your environment variables or the `app/reporting.py` file.</p>"
        return f"<p class='text-danger small'><b>AI report failed to generate.</b><br>Error: {e}</p>"
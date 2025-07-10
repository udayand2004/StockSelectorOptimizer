import google.generativeai as genai

# --- IMPORTANT: CONFIGURE YOUR API KEY ---
# Option 1: Set environment variable GOOGLE_API_KEY
# Option 2: Uncomment and paste your key below
genai.configure(api_key="AIzaSyANBOTpHkdlpISgG6BLWuUmoKiB8t6ugJo")

def generate_gemini_report(kpis, monthly_returns, yearly_returns, rebalance_logs):
    """
    Uses Google's Gemini model to generate a detailed analysis of the backtest report.
    """
    try:
        if not genai.get_key():
            return "<p class='text-warning small'>AI report generation skipped: GOOGLE_API_KEY is not configured.</p>"

        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # Create a concise summary of the data for the prompt
        kpi_summary = f"""
        - CAGR: {kpis.get('CAGR﹪', 0)*100:.2f}%
        - Sharpe Ratio: {kpis.get('Sharpe', 0):.2f}
        - Max Drawdown: {kpis.get('Max Drawdown', 0)*100:.2f}%
        - Sortino Ratio: {kpis.get('Sortino', 0):.2f}
        - Beta: {kpis.get('Beta', 0):.2f}
        """

        yearly_summary = "\n".join([f"- {year}: {ret:.2f}%" for year, ret in yearly_returns.items()])
        
        # Count how many months the strategy was active vs. in cash
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
        3.  **Consistency and Regime Filter:** Analyze the yearly returns. Are they consistent? Comment on the effectiveness of the market regime filter based on the activity log. Did it successfully avoid major downturns (e.g., 2020 crash, 2022 bear market)?
        4.  **Potential Concerns & Red Flags:** Based on all the data, what are the potential red flags? Is a Sharpe ratio of {kpis.get('Sharpe', 0):.2f} realistic? Could there still be overfitting?
        5.  **Conclusion & Recommendations:** Provide a concluding paragraph on whether this strategy is promising and suggest next steps for improvement or validation.
        """

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"--- Gemini AI Report Failed: {e} ---")
        return f"<p class='text-danger small'>AI report failed to generate. Error: {e}</p>"
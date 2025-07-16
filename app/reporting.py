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
        time_in_market_pct = (active_months / total_months * 100) if total_months > 0 else 0
        
        prompt = f"""
        As a quantitative analyst reviewing a new strategy for an internal team presentation, provide a constructive and objective evaluation of the following backtest report. The goal is to analyze the current results and identify key areas for refinement. Maintain a professional, forward-looking tone.

        **Key Performance Indicators:**
        {kpi_summary}

        **Yearly Returns (%):**
        {yearly_summary}
        
        **Activity Log Summary:**
        - The strategy was invested in the market for approximately {time_in_market_pct:.0f}% of the rebalancing periods ({active_months} out of {total_months}).

        **Your evaluation should be structured as follows:**

        1.  **Performance Summary:**
            - Objectively state the strategy's CAGR and Sharpe Ratio from the report.
            - Briefly comment on the relationship between the absolute return (CAGR) and the risk-adjusted return (Sharpe Ratio).

        2.  **Risk & Volatility Profile:**
            - Discuss the observed Max Drawdown. What does this metric suggest about the strategy's risk during the backtest period?
            - Comment on the reported Beta. What does a Beta of {kpis.get('Beta', 0):.2f} imply about the strategy's correlation to the market based on these results?

        3.  **Strategy Behavior & Regime Filter:**
            - Analyze the yearly returns for patterns or consistency.
            - Based on the activity log ({time_in_market_pct:.0f}% time in market), comment on the behavior of the market regime filter. How did it influence the strategy's exposure during this specific historical period?

        4.  **Observations & Key Areas for Improvement:**
            - Based on the analysis, what are the most important observations?
            - Point out any inconsistencies between different metrics (e.g., between CAGR and yearly returns, or Beta and strategy type) as areas for further validation in the backtesting engine.
            - Suggest clear, actionable next steps for the team. Frame these as refinements rather than failures. For example:
                - "Refine the regime filter to potentially improve market entry/exit timing."
                - "Conduct a sensitivity analysis on the model's features."
                - "Validate the calculation of key metrics like Beta and CAGR in the backtesting module to ensure they align with portfolio activity."
                - "Incorporate a benchmark comparison (e.g., NIFTY 50) in future reports to better quantify alpha."

        5.  **Overall Conclusion:**
            - Provide a brief, forward-looking summary. Conclude that this backtest provides a valuable baseline and highlights specific areas for development to enhance the strategy's performance and robustness.
        """
        response = model.generate_content(prompt)
        print("--- AI report successfully generated. ---")
        return response.text

    except Exception as e:
        print(f"--- Gemini AI Report Failed: {e} ---")
        if "API key" in str(e).lower() or "permission" in str(e).lower():
            return f"<p class='text-danger small'><b>AI report failed to generate.</b><br>Error: The Google AI API key is not configured or is invalid. Please check your environment variables or the `app/reporting.py` file.</p>"
        return f"<p class='text-danger small'><b>AI report failed to generate.</b><br>Error: {e}</p>"


def generate_factor_explanation():
    """Uses Gemini to generate an explanation of the Fama-French-Carhart factors."""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest') # Use a capable model
        prompt = """
        As a finance professor, please provide a clear and concise explanation of the four factors used in this portfolio analysis: Market (Mkt-RF), Size (SMB), Value (HML), and Momentum (UMD).

        Structure your explanation for an investor who is intelligent but may not be a quantitative expert. For each factor, explain:
        1.  What it represents (the underlying economic idea).
        2.  How it is calculated (e.g., Small-Minus-Big for SMB).
        3.  What a positive or negative beta to this factor implies about the portfolio's strategy.

        Keep the language accessible and focus on the intuition behind each factor. Format the output using simple Markdown (e.g., **bold** for titles, bullet points).
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"<p class='text-danger'><b>AI explanation failed.</b><br>Error: {e}</p>"   
# File: app/reporting.py

# ... (keep all existing functions: generate_gemini_report, generate_factor_explanation) ...

def answer_user_question(question, context_data):
    """Uses Gemini to answer a user's question based on backtest context."""
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # Serialize the context data into a readable string for the prompt
        context_str = "Key Performance Indicators:\n"
        for key, value in context_data.get('kpis', {}).items():
            context_str += f"- {key}: {value}\n"
        
        context_str += "\nFull Metrics:\n"
        for key, value in context_data.get('full_metrics', {}).items():
            context_str += f"- {key}: {value}\n"

        context_str += f"\nAI Analysis Summary:\n{context_data.get('ai_summary', 'Not available.')}"

        prompt = f"""
        You are a specialized Quantitative Finance AI assistant. Your sole purpose is to answer questions about a specific backtest report. You must use ONLY the data provided below as your context.

        --- CONTEXT: BACKTEST REPORT DATA ---
        {context_str}
        --- END OF CONTEXT ---

        The user has asked the following question: "{question}"

        Your Task:
        1.  Analyze the user's question.
        2.  Formulate an answer based *strictly* on the provided context data.
        3.  If the question is a general definition of a metric present in the context (e.g., "What is Sharpe Ratio?"), you can provide a standard financial definition.
        4.  If the question refers to a specific value (e.g., "Why is the CAGR 7%?"), refer to the data in your answer (e.g., "The report shows a CAGR of 7.00%...").
        5.  If the user's question cannot be answered from the provided context, you MUST respond with: "I'm sorry, but I can only answer questions directly related to the provided backtest report data."
        6.  Keep your answers concise, clear, and professional. Use simple Markdown for formatting if needed (like **bolding**).
        """
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"--- Gemini Chatbot Failed: {e} ---")
        return f"<p class='text-danger small'><b>AI Assistant Error.</b><br>Could not generate a response. Please check the server logs. Error: {e}</p>"
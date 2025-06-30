// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const loader = document.getElementById('loader');

    const stockPicksDiv = document.getElementById('stockPicksDiv');
    const rationaleDiv = document.getElementById('rationaleDiv');
    const portfolioPieChart = document.getElementById('portfolioPieChart');
    const sectorBarChart = document.getElementById('sectorBarChart');

    runAnalysisBtn.addEventListener('click', runFullAnalysis);

    function showLoader() { loader.style.display = 'block'; }
    function hideLoader() { loader.style.display = 'none'; }
    
    function clearResults() {
        stockPicksDiv.innerHTML = '<p class="text-muted">Run analysis to see results.</p>';
        rationaleDiv.innerHTML = '<p class="text-muted">Run analysis to generate the portfolio rationale.</p>';
        Plotly.purge(portfolioPieChart);
        Plotly.purge(sectorBarChart);
    }

    // --- ROBUSTNESS FIX: Function to display errors in the UI ---
    function displayError(errorMsg) {
        const errorHtml = `<div class="error-message">${errorMsg}</div>`;
        stockPicksDiv.innerHTML = errorHtml;
        rationaleDiv.innerHTML = `<p class="text-danger">Analysis failed.</p>`;
    }

    async function runFullAnalysis() {
        showLoader();
        clearResults();

        const config = {
            universe: document.getElementById('universeSelector').value,
            top_n: document.getElementById('topNInput').value,
            risk_free: document.getElementById('riskFreeInput').value / 100,
        };

        try {
            const response = await fetch('/api/analyze_and_optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await response.json();

            // --- ROBUSTNESS FIX: Check for the 'error' key in the response ---
            if (!response.ok || data.error) {
                // If there's an error, display it and stop processing
                displayError(data.error || `An unknown error occurred (Status: ${response.status}).`);
                hideLoader();
                return;
            }
            
            // If we get here, the data is valid
            updateStockPicks(data.top_stocks);
            updateRationale(data.rationale);
            plotPortfolioPie(data.optimal_weights);
            plotSectorBar(data.sector_exposure);

        } catch (error) {
            console.error('Network or parsing error:', error);
            displayError('A network error occurred. Please check your connection and the server status.');
        } finally {
            hideLoader();
        }
    }

    function updateStockPicks(stocks) {
        if (!stocks || stocks.length === 0) {
            stockPicksDiv.innerHTML = '<p class="text-danger">No stocks were returned.</p>';
            return;
        }
        let tableHtml = '<table class="table table-sm table-hover"><tbody>';
        stocks.forEach(stock => {
            tableHtml += `<tr><td>${stock}</td></tr>`;
        });
        tableHtml += '</tbody></table>';
        stockPicksDiv.innerHTML = tableHtml;
    }

    function updateRationale(rationale) {
        rationaleDiv.innerHTML = rationale || '<p class="text-muted">No rationale generated.</p>';
    }

    function plotPortfolioPie(weights) {
        if (!weights || Object.keys(weights).length === 0) return;
        const labels = Object.keys(weights);
        const values = Object.values(weights);
        const data = [{
            values: values,
            labels: labels,
            type: 'pie',
            hole: .4,
            textinfo: 'label+percent',
            textposition: 'inside',
            automargin: true
        }];
        const layout = {
            title: '',
            showlegend: false,
            margin: { t: 10, b: 10, l: 10, r: 10 },
            height: 350
        };
        Plotly.newPlot(portfolioPieChart, data, layout, {responsive: true});
    }

    function plotSectorBar(exposure) {
        if (!exposure || Object.keys(exposure).length === 0) return;
        const labels = Object.keys(exposure);
        const values = Object.values(exposure).map(v => v * 100);
        const data = [{
            x: labels,
            y: values,
            type: 'bar',
            text: values.map(v => `${v.toFixed(1)}%`),
            textposition: 'auto'
        }];
        const layout = {
            title: '',
            yaxis: { title: 'Weight (%)' },
            xaxis: { tickangle: -45 },
            margin: { t: 10, b: 100, l: 50, r: 20 },
            height: 300
        };
        Plotly.newPlot(sectorBarChart, data, layout, {responsive: true});
    }
});
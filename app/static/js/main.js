document.addEventListener('DOMContentLoaded', function() {
    // --- LIVE ANALYSIS SECTION (Restored and Complete) ---
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const loader = document.getElementById('loader');
    const stockPicksDiv = document.getElementById('stockPicksDiv');
    const rationaleDiv = document.getElementById('rationaleDiv');
    const portfolioPieChart = document.getElementById('portfolioPieChart');
    const sectorBarChart = document.getElementById('sectorBarChart');

    if (runAnalysisBtn) {
        runAnalysisBtn.addEventListener('click', runFullAnalysis);
    }

    function showLoader() { loader.style.display = 'block'; }
    function hideLoader() { loader.style.display = 'none'; }
    
    function clearResults() {
        stockPicksDiv.innerHTML = '<p class="text-muted">Run analysis to see results.</p>';
        rationaleDiv.innerHTML = '<p class="text-muted">Run analysis to generate the portfolio rationale.</p>';
        Plotly.purge(portfolioPieChart);
        Plotly.purge(sectorBarChart);
    }

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
            optimization_method: document.querySelector('input[name="optMethod"]:checked').value
        };

        try {
            const response = await fetch('/api/analyze_and_optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await response.json();

            if (!response.ok || data.error) {
                displayError(data.error || `An unknown error occurred (Status: ${response.status}).`);
                return;
            }
            
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
        const labels = Object.keys(weights).filter(k => weights[k] > 0);
        const values = labels.map(l => weights[l]);
        if (labels.length === 0) return;
        const data = [{
            values: values, labels: labels, type: 'pie', hole: .4,
            textinfo: 'label+percent', textposition: 'inside', automargin: true
        }];
        const layout = { title: '', showlegend: false, margin: { t: 10, b: 10, l: 10, r: 10 }, height: 350 };
        Plotly.newPlot(portfolioPieChart, data, layout, {responsive: true});
    }

    function plotSectorBar(exposure) {
        if (!exposure || Object.keys(exposure).length === 0) return;
        const sortedSectors = Object.entries(exposure).sort((a, b) => b[1] - a[1]);
        const labels = sortedSectors.map(s => s[0]);
        const values = sortedSectors.map(s => s[1] * 100);
        const data = [{
            x: labels, y: values, type: 'bar',
            text: values.map(v => `${v.toFixed(1)}%`), textposition: 'auto'
        }];
        const layout = { title: '', yaxis: { title: 'Weight (%)' }, xaxis: { tickangle: -45 }, margin: { t: 10, b: 100, l: 50, r: 20 }, height: 300 };
        Plotly.newPlot(sectorBarChart, data, layout, {responsive: true});
    }

    // --- BACKTESTING LOGIC (NEW, INTEGRATED VERSION) ---
    const runBacktestBtn = document.getElementById('runBacktestBtn');
    let pollingInterval;

    if (runBacktestBtn) {
        runBacktestBtn.addEventListener('click', runBacktest);
    }
    
    function resetBacktestUI() {
        document.getElementById('backtestResultContainer').style.display = 'none';
        Plotly.purge('backtestEquityChart');
        Plotly.purge('backtestDrawdownChart');
        document.getElementById('cagrValue').innerText = '-';
        document.getElementById('sharpeValue').innerText = '-';
        document.getElementById('drawdownValue').innerText = '-';
        document.getElementById('calmarValue').innerText = '-';
    }

    function runBacktest() {
        const backtestStatusDiv = document.getElementById('backtestStatus');
        resetBacktestUI();
        
        backtestStatusDiv.innerHTML = `
            <div class="d-flex justify-content-center align-items-center">
                <div class="spinner-border text-primary" role="status"></div>
                <strong class="ms-3">Starting backtest... This may take several minutes.</strong>
            </div>`;
        backtestStatusDiv.style.display = 'block';
        
        if (pollingInterval) clearInterval(pollingInterval);
        
        const config = {
            universe: document.getElementById('backtestUniverse').value,
            start_date: document.getElementById('backtestStartDate').value,
            end_date: document.getElementById('backtestEndDate').value,
            top_n: document.getElementById('topNInput').value
        };
        
        fetch('/api/run_backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        })
        .then(response => response.ok ? response.json() : Promise.reject(response))
        .then(data => {
            backtestStatusDiv.innerHTML += `<p class="text-muted small mt-3">Task ID: ${data.task_id}</p>`;
            pollTaskStatus(data.task_id);
        })
        .catch(error => {
            console.error('Error starting backtest:', error);
            backtestStatusDiv.innerHTML = `<div class="error-message">Failed to start the backtest task. Check server logs.</div>`;
        });
    }

        function pollTaskStatus(taskId) {
        const backtestStatusDiv = document.getElementById('backtestStatus');

        pollingInterval = setInterval(() => {
            fetch(`/api/backtest_status/${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data.state === 'SUCCESS') {
                    clearInterval(pollingInterval);
                    backtestStatusDiv.style.display = 'none';
                    displayBacktestResults(data.result);
                } else if (data.state === 'FAILURE') {
                    clearInterval(pollingInterval);
                    backtestStatusDiv.innerHTML = `<div class="error-message"><strong>Backtest Failed:</strong><br><pre>${data.status}</pre></div>`;
                } else {
                    // <<< MODIFIED: This block now handles PENDING and PROGRESS states
                    let statusMessage = 'Processing...';
                    if (data.state === 'PROGRESS' && data.status) {
                        statusMessage = data.status;
                    } else if (data.status) {
                        statusMessage = data.status; // For PENDING state
                    }

                    backtestStatusDiv.innerHTML = `
                        <div class="d-flex justify-content-center align-items-center">
                           <div class="spinner-border text-primary" role="status"></div>
                           <strong class="ms-3">${statusMessage}</strong>
                        </div>
                        <p class="text-muted small mt-3">Task ID: ${taskId}</p>`;
                }
            })
            .catch(error => {
                clearInterval(pollingInterval);
                console.error('Error polling task status:', error);
                backtestStatusDiv.innerHTML = `<div class="error-message">Error checking backtest status. The connection may have been lost.</div>`;
            });
        }, 3000); // Poll every 3 seconds
    }

    function displayBacktestResults(results) {
        const container = document.getElementById('backtestResultContainer');
        if (!results || !results.kpis || !results.charts) {
            document.getElementById('backtestStatus').innerHTML = `<div class="error-message">Received invalid or empty results from the backtest.</div>`;
            document.getElementById('backtestStatus').style.display = 'block';
            return;
        }

        document.getElementById('cagrValue').innerText = results.kpis.CAGR;
        document.getElementById('sharpeValue').innerText = results.kpis.Sharpe;
        document.getElementById('drawdownValue').innerText = results.kpis.Max_Drawdown;
        document.getElementById('calmarValue').innerText = results.kpis.Calmar;
        
        const equityTrace = {
            x: results.charts.equity.dates,
            y: results.charts.equity.portfolio,
            mode: 'lines', name: 'Strategy',
            line: { color: '#0d6efd', width: 2 }
        };
        const benchmarkTrace = {
            x: results.charts.equity.dates,
            y: results.charts.equity.benchmark,
            mode: 'lines', name: 'Benchmark (NIFTY 50)',
            line: { color: '#6c757d', dash: 'dot', width: 1.5 }
        };
        const equityLayout = {
            title: 'Strategy vs. Benchmark Performance (Log Scale)',
            yaxis: { title: 'Cumulative Growth', type: 'log' },
            legend: { x: 0.01, y: 0.99 },
            margin: { t: 40, b: 40, l: 60, r: 20 }
        };
        Plotly.newPlot('backtestEquityChart', [equityTrace, benchmarkTrace], equityLayout, {responsive: true});

        const drawdownTrace = {
            x: results.charts.drawdown.dates,
            y: results.charts.drawdown.values,
            type: 'scatter', mode: 'lines', fill: 'tozeroy',
            name: 'Drawdown', line: { color: '#dc3545' }
        };
        const drawdownLayout = {
            title: 'Strategy Drawdowns',
            yaxis: { title: 'Drawdown (%)' },
            margin: { t: 40, b: 40, l: 60, r: 20 }
        };
        Plotly.newPlot('backtestDrawdownChart', [drawdownTrace], drawdownLayout, {responsive: true});

        container.style.display = 'block';
    }
});
document.addEventListener('DOMContentLoaded', function() {
    // --- LIVE ANALYSIS SECTION (NO CHANGES NEEDED HERE) ---
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const loader = document.getElementById('loader');
    const stockPicksDiv = document.getElementById('stockPicksDiv');
    const rationaleDiv = document.getElementById('rationaleDiv');
    const portfolioPieChart = document.getElementById('portfolioPieChart');
    const sectorBarChart = document.getElementById('sectorBarChart');

    if (runAnalysisBtn) { runAnalysisBtn.addEventListener('click', runFullAnalysis); }
    function showLoader() { loader.style.display = 'block'; }
    function hideLoader() { loader.style.display = 'none'; }
    function clearResults() {
        stockPicksDiv.innerHTML = '<p class="text-muted">Run analysis to see results.</p>';
        rationaleDiv.innerHTML = '<p class="text-muted">Run analysis to generate the portfolio rationale.</p>';
        if (Plotly) {
            Plotly.purge(portfolioPieChart);
            Plotly.purge(sectorBarChart);
        }
    }
    function displayError(errorMsg) {
        stockPicksDiv.innerHTML = `<div class="error-message">${errorMsg}</div>`;
        rationaleDiv.innerHTML = `<p class="text-danger">Analysis failed.</p>`;
    }
    async function runFullAnalysis() {
        showLoader(); clearResults();
        const config = { universe: document.getElementById('universeSelector').value, top_n: document.getElementById('topNInput').value, risk_free: document.getElementById('riskFreeInput').value / 100, optimization_method: document.querySelector('input[name="optMethod"]:checked').value };
        try {
            const response = await fetch('/api/analyze_and_optimize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) });
            const data = await response.json();
            if (!response.ok || data.error) { displayError(data.error || `An unknown error occurred (Status: ${response.status}).`); return; }
            updateStockPicks(data.top_stocks); updateRationale(data.rationale); plotPortfolioPie(data.optimal_weights); plotSectorBar(data.sector_exposure);
        } catch (error) { console.error('Network or parsing error:', error); displayError('A network error occurred.'); } finally { hideLoader(); }
    }
    function updateStockPicks(stocks) {
        if (!stocks || stocks.length === 0) { stockPicksDiv.innerHTML = '<p class="text-danger">No stocks were returned.</p>'; return; }
        let tableHtml = '<table class="table table-sm table-hover"><tbody>';
        stocks.forEach(stock => { tableHtml += `<tr><td>${stock}</td></tr>`; });
        stockPicksDiv.innerHTML = tableHtml + '</tbody></table>';
    }
    function updateRationale(rationale) { rationaleDiv.innerHTML = rationale || '<p class="text-muted">No rationale generated.</p>'; }
    function plotPortfolioPie(weights) {
        if (!weights || Object.keys(weights).length === 0) return;
        const labels = Object.keys(weights).filter(k => weights[k] > 0);
        if (labels.length === 0) return;
        const values = labels.map(l => weights[l]);
        const data = [{ values, labels, type: 'pie', hole: .4, textinfo: 'label+percent', textposition: 'inside', automargin: true }];
        const layout = { title: '', showlegend: false, margin: { t: 10, b: 10, l: 10, r: 10 }, height: 350 };
        Plotly.newPlot(portfolioPieChart, data, layout, {responsive: true});
    }
    function plotSectorBar(exposure) {
        if (!exposure || Object.keys(exposure).length === 0) return;
        const sortedSectors = Object.entries(exposure).sort((a, b) => b[1] - a[1]);
        const labels = sortedSectors.map(s => s[0]);
        const values = sortedSectors.map(s => s[1] * 100);
        const data = [{ x: labels, y: values, type: 'bar', text: values.map(v => `${v.toFixed(1)}%`), textposition: 'auto' }];
        const layout = { title: '', yaxis: { title: 'Weight (%)' }, xaxis: { tickangle: -45 }, margin: { t: 10, b: 100, l: 50, r: 20 }, height: 300 };
        Plotly.newPlot(sectorBarChart, data, layout, {responsive: true});
    }

    // --- BACKTESTING LOGIC ---
    const runBacktestBtn = document.getElementById('runBacktestBtn');
    const downloadCsvBtn = document.getElementById('downloadCsvBtn');
    let pollingInterval;
    let lastBacktestLogs = [];

    if (runBacktestBtn) { runBacktestBtn.addEventListener('click', runBacktest); }
    if (downloadCsvBtn) { downloadCsvBtn.addEventListener('click', downloadLogsAsCsv); }

    function createReturnsTable(tableDataJson, tableContainerId) { /* Unchanged from previous version */ }
    function createRebalanceLogTable(logs) { /* Unchanged from previous version */ }
    function downloadLogsAsCsv() { /* Unchanged from previous version */ }

    // NEW: Function to display the full metrics snapshot
    function createFullMetricsTable(kpis) {
        const container = document.getElementById('fullMetricsTableContainer');
        let tableHtml = '<table class="table table-sm table-striped"><tbody>';
        for (const [key, value] of Object.entries(kpis)) {
            let formattedValue = value;
            if (typeof value === 'number') {
                // Heuristic formatting for different types of metrics
                if (key.includes('﹪') || key.includes('%') || key.toLowerCase().includes('drawdown') || key.toLowerCase().includes('var')) {
                    formattedValue = (value * 100).toFixed(2) + '%';
                } else if (value > 1000) {
                     formattedValue = value.toLocaleString(undefined, {maximumFractionDigits: 0});
                }
                else {
                    formattedValue = value.toFixed(2);
                }
            }
            tableHtml += `<tr><th class="fw-normal">${key}</th><td class="text-end">${formattedValue}</td></tr>`;
        }
        tableHtml += '</tbody></table>';
        container.innerHTML = tableHtml;
    }

    function resetBacktestUI() {
        document.getElementById('backtestResultContainer').style.display = 'none';
        Plotly.purge('backtestEquityChart');
        Plotly.purge('backtestDrawdownChart');
        Plotly.purge('historicalWeightsChart');
        Plotly.purge('historicalSectorsChart');
        const kpiIds = ['cagrValue', 'sharpeValue', 'drawdownValue', 'calmarValue', 'betaValue', 'sortinoValue', 'varValue', 'cvarValue'];
        kpiIds.forEach(id => { document.getElementById(id).innerText = '-'; });
        document.getElementById('monthlyReturnsTable').innerHTML = '';
        document.getElementById('yearlyReturnsTable').innerHTML = '';
        document.getElementById('rebalanceLogContainer').innerHTML = '';
        document.getElementById('fullMetricsTableContainer').innerHTML = '<p class="text-muted small">Run a backtest to see the detailed metrics report.</p>';
        lastBacktestLogs = [];
    }

    function displayBacktestResults(results) {
        const container = document.getElementById('backtestResultContainer');
        if (!results || !results.kpis || !results.charts) { /* Unchanged */ return; }

        // --- THE KEY FIX: MAPPING THE CORRECT KPI NAMES ---
        const kpis = results.kpis;
        const kpiMapping = {
            cagrValue: kpis['CAGR﹪'] !== undefined ? (kpis['CAGR﹪'] * 100).toFixed(2) : '-',
            sharpeValue: kpis['Sharpe'] !== undefined ? kpis['Sharpe'].toFixed(2) : '-',
            drawdownValue: kpis['Max Drawdown'] !== undefined ? (kpis['Max Drawdown'] * 100).toFixed(2) : '-',
            calmarValue: kpis['Calmar'] !== undefined ? kpis['Calmar'].toFixed(2) : '-',
            betaValue: kpis['Beta'] !== undefined ? kpis['Beta'].toFixed(2) : '-',
            sortinoValue: kpis['Sortino'] !== undefined ? kpis['Sortino'].toFixed(2) : '-',
            varValue: kpis['Daily VaR'] !== undefined ? (kpis['Daily VaR'] * 100).toFixed(2) + '%' : '-',
            cvarValue: kpis['Daily CVaR'] !== undefined ? (kpis['Daily CVaR'] * 100).toFixed(2) + '%' : '-'
        };
        Object.entries(kpiMapping).forEach(([id, value]) => {
            document.getElementById(id).innerText = value;
        });

        // Plot main charts
        const equityTrace = { x: results.charts.equity.dates, y: results.charts.equity.portfolio, mode: 'lines', name: 'Strategy', line: { color: '#0d6efd', width: 2 }};
        const benchmarkTrace = { x: results.charts.equity.dates, y: results.charts.equity.benchmark, mode: 'lines', name: 'Benchmark (NIFTY 50)', line: { color: '#6c757d', dash: 'dot', width: 1.5 }};
        const equityLayout = { title: 'Strategy vs. Benchmark Performance', yaxis: { title: 'Cumulative Growth', type: 'log' }, legend: { x: 0.01, y: 0.99 }, margin: { t: 40, b: 40, l: 60, r: 20 } };
        Plotly.newPlot('backtestEquityChart', [equityTrace, benchmarkTrace], equityLayout, {responsive: true});

        const drawdownTrace = { x: results.charts.drawdown.dates, y: results.charts.drawdown.values, type: 'scatter', mode: 'lines', fill: 'tozeroy', name: 'Drawdown', line: { color: '#dc3545' }};
        const drawdownLayout = { title: 'Strategy Drawdowns', yaxis: { title: 'Drawdown (%)' }, margin: { t: 40, b: 40, l: 60, r: 20 } };
        Plotly.newPlot('backtestDrawdownChart', [drawdownTrace], drawdownLayout, {responsive: true});
        
        // Plot NEW historical charts
        Plotly.newPlot('historicalWeightsChart', results.charts.historical_weights.data, results.charts.historical_weights.layout, {responsive: true});
        Plotly.newPlot('historicalSectorsChart', results.charts.historical_sectors.data, results.charts.historical_sectors.layout, {responsive: true});
        
        // Render tables and logs
        createReturnsTable(results.tables.monthly_returns, 'monthlyReturnsTable');
        createReturnsTable(results.tables.yearly_returns, 'yearlyReturnsTable');
        createRebalanceLogTable(results.logs);
        createFullMetricsTable(results.kpis); // NEW

        container.style.display = 'block';
    }

    // --- UNCHANGED FUNCTIONS (Copying them here to make the file complete) ---
    function runBacktest() {
        const backtestStatusDiv = document.getElementById('backtestStatus');
        resetBacktestUI();
        backtestStatusDiv.innerHTML = `<div class="d-flex justify-content-center align-items-center"><div class="spinner-border text-primary" role="status"></div><strong class="ms-3">Starting backtest...</strong></div>`;
        backtestStatusDiv.style.display = 'block';
        if (pollingInterval) clearInterval(pollingInterval);
        const config = {
            universe: document.getElementById('backtestUniverse').value,
            start_date: document.getElementById('backtestStartDate').value,
            end_date: document.getElementById('backtestEndDate').value,
            top_n: document.getElementById('topNInput').value
        };
        fetch('/api/run_backtest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) })
        .then(response => response.ok ? response.json() : Promise.reject(response))
        .then(data => {
            backtestStatusDiv.innerHTML += `<p class="text-muted small mt-3">Task ID: ${data.task_id}</p>`;
            pollTaskStatus(data.task_id);
        })
        .catch(error => {
            console.error('Error starting backtest:', error);
            backtestStatusDiv.innerHTML = `<div class="error-message">Failed to start backtest.</div>`;
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
                    let statusMessage = (data.state === 'PROGRESS' && data.status) ? data.status : (data.status || 'Processing...');
                    backtestStatusDiv.innerHTML = `<div class="d-flex justify-content-center align-items-center"><div class="spinner-border text-primary" role="status"></div><strong class="ms-3">${statusMessage}</strong></div><p class="text-muted small mt-3">Task ID: ${taskId}</p>`;
                }
            })
            .catch(error => {
                clearInterval(pollingInterval);
                console.error('Error polling task status:', error);
                backtestStatusDiv.innerHTML = `<div class="error-message">Error checking status.</div>`;
            });
        }, 3000);
    }
    
    // Copy-pasting the helper functions again to ensure they are defined.
    function createReturnsTable(tableDataJson, tableContainerId) {
        const container = document.getElementById(tableContainerId);
        if (!tableDataJson) { container.innerHTML = '<p class="text-muted">No data.</p>'; return; }
        try {
            const tableData = JSON.parse(tableDataJson);
            let tableHtml = '<table class="table table-sm table-bordered table-hover text-center">';
            tableHtml += '<thead><tr><th>' + (tableData.index.name || 'Year') + '</th>';
            tableData.columns.forEach(col => { tableHtml += `<th>${col}</th>`; });
            tableHtml += '</tr></thead><tbody>';
            tableData.index.forEach((year, i) => {
                tableHtml += `<tr><th>${year}</th>`;
                tableData.data[i].forEach(val => {
                    const value = (val * 100).toFixed(2);
                    const colorClass = value > 0.01 ? 'text-success' : (value < -0.01 ? 'text-danger' : '');
                    tableHtml += `<td class="${colorClass}">${value}</td>`;
                });
                tableHtml += '</tr>';
            });
            container.innerHTML = tableHtml + '</tbody></table>';
        } catch(e) { console.error("Error building table:", e); container.innerHTML = '<p class="text-danger">Error rendering table.</p>'; }
    }
    function createRebalanceLogTable(logs) {
        lastBacktestLogs = logs;
        const container = document.getElementById('rebalanceLogContainer');
        if (!logs || logs.length === 0) { container.innerHTML = '<p class="text-muted">No logs.</p>'; return; }
        let tableHtml = '<table class="table table-sm table-hover"><thead><tr><th>Date</th><th>Action</th><th>Details</th></tr></thead><tbody>';
        logs.forEach(log => {
            let detailsHtml = (log.Action === 'Hold Cash') ? `<span class="text-muted">${log.Details}</span>` : Object.entries(log.Details).filter(([k, v]) => v > 0).sort((a,b) => b[1] - a[1]).map(([k, v]) => `${k}: ${(v * 100).toFixed(1)}%`).join('<br>');
            tableHtml += `<tr><td>${log.Date}</td><td>${log.Action}</td><td>${detailsHtml}</td></tr>`;
        });
        container.innerHTML = tableHtml + '</tbody></table>';
    }
    function downloadLogsAsCsv() {
        if (lastBacktestLogs.length === 0) { alert("No log data."); return; }
        let csvContent = "data:text/csv;charset=utf-8,Date,Action,Symbol,Weight,Comment\n";
        lastBacktestLogs.forEach(log => {
            if (log.Action === 'Hold Cash') {
                csvContent += `${log.Date},Hold Cash,,,${log.Details.replace(/,/g, ";")}\n`;
            } else {
                Object.entries(log.Details).forEach(([stock, weight]) => {
                    if (weight > 0) csvContent += `${log.Date},Rebalanced,${stock},${weight.toFixed(4)},\n`;
                });
            }
        });
        const link = document.createElement("a");
        link.setAttribute("href", encodeURI(csvContent));
        link.setAttribute("download", "backtest_rebalancing_log.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
});
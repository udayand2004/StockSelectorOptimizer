document.addEventListener('DOMContentLoaded', function() {
    
    // --- COMMON VARIABLES & INITIALIZATION ---
    let pollingInterval;
    let lastBacktestLogs = [];

    // --- LIVE ANALYSIS SECTION ---
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const loader = document.getElementById('loader');
    const stockPicksDiv = document.getElementById('stockPicksDiv');
    const rationaleDiv = document.getElementById('rationaleDiv');
    const portfolioPieChart = document.getElementById('portfolioPieChart');
    const sectorBarChart = document.getElementById('sectorBarChart');

    if (runAnalysisBtn) { runAnalysisBtn.addEventListener('click', runFullAnalysis); }
    function displayFactorExposure(data) {
    const chartContainer = document.getElementById('factorExposureChart');
    const tableContainer = document.getElementById('factorExposureTable');

    if (data.error) {
        chartContainer.innerHTML = `<p class="text-danger small">${data.error}</p>`;
        tableContainer.innerHTML = '';
        return;
    }

    // 1. Create the Bar Chart for Betas
    const betas = data.betas;
    const labels = Object.keys(betas);
    const values = Object.values(betas);
    const colors = values.map(v => v >= 0 ? 'rgba(13, 110, 253, 0.7)' : 'rgba(220, 53, 69, 0.7)');

    const plotData = [{
        x: labels,
        y: values,
        type: 'bar',
        marker: { color: colors },
        text: values.map(v => v.toFixed(3)),
        textposition: 'auto'
    }];
    const layout = {
        title: 'Factor Betas',
        yaxis: { title: 'Beta', zeroline: true },
        xaxis: { tickangle: -20 },
        margin: { t: 40, b: 80, l: 50, r: 20 },
        height: 350
    };
    Plotly.newPlot(chartContainer, plotData, layout, {responsive: true});

    // 2. Create the Statistics Table
    let tableHtml = `<table class="table table-sm table-borderless">`;
    tableHtml += `
        <tr>
            <th class="ps-0">Annualized Alpha:</th>
            <td class="text-end fw-bold ${data.alpha_annualized_pct > 0 ? 'text-success' : 'text-danger'}">
                ${data.alpha_annualized_pct.toFixed(2)}%
            </td>
        </tr>
        <tr>
            <th class="ps-0">R-Squared:</th>
            <td class="text-end">${(data.r_squared * 100).toFixed(1)}%</td>
        </tr>
    </table>`;

    tableHtml += '<table class="table table-sm table-hover"><thead><tr><th>Factor</th><th>Beta</th><th>T-Stat</th><th>P-Value</th></tr></thead><tbody>';
    for (const factor of labels) {
        const p_val = data.p_values[factor];
        // Highlight statistically significant results (p-value < 0.05)
        const significanceClass = p_val < 0.05 ? 'fw-bold' : '';
        tableHtml += `
            <tr class="${significanceClass}">
                <td>${factor}</td>
                <td>${data.betas[factor].toFixed(3)}</td>
                <td>${data.t_stats[factor].toFixed(2)}</td>
                <td>${p_val.toFixed(3)}</td>
            </tr>
        `;
    }
    tableHtml += '</tbody></table>';
    tableContainer.innerHTML = tableHtml;
}
    function showLoader() { loader.style.display = 'block'; }
    function hideLoader() { loader.style.display = 'none'; }
    
    function clearLiveAnalysisResults() {
        stockPicksDiv.innerHTML = '<p class="text-muted">Run analysis to see results.</p>';
        rationaleDiv.innerHTML = '<p class="text-muted">Run analysis to generate the portfolio rationale.</p>';
        if (typeof Plotly !== 'undefined' && portfolioPieChart && sectorBarChart) {
            Plotly.purge(portfolioPieChart);
            Plotly.purge(sectorBarChart);
        }
    }
    
    function displayLiveAnalysisError(errorMsg) {
        stockPicksDiv.innerHTML = `<div class="error-message">${errorMsg}</div>`;
        rationaleDiv.innerHTML = `<p class="text-danger">Analysis failed.</p>`;
    }

    async function runFullAnalysis() {
        showLoader(); 
        clearLiveAnalysisResults();
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
                displayLiveAnalysisError(data.error || `An unknown error occurred (Status: ${response.status}).`); 
                return; 
            }
            updateStockPicks(data.top_stocks); 
            updateRationale(data.rationale); 
            plotPortfolioPie(data.optimal_weights); 
            plotSectorBar(data.sector_exposure);
        } catch (error) { 
            console.error('Network or parsing error:', error); 
            displayLiveAnalysisError('A network error occurred.'); 
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
        stocks.forEach(stock => { tableHtml += `<tr><td>${stock}</td></tr>`; });
        stockPicksDiv.innerHTML = tableHtml + '</tbody></table>';
    }

    function updateRationale(rationale) { 
        rationaleDiv.innerHTML = rationale || '<p class="text-muted">No rationale generated.</p>'; 
    }

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


    // --- PORTFOLIO STUDIO SECTION ---
    const stockSelector = document.getElementById('stockSelector');
    const manualWeightsContainer = document.getElementById('manualWeightsContainer');
    const savePortfolioBtn = document.getElementById('savePortfolioBtn');

    if (document.querySelector('input[name="weightMethod"]')) {
        document.querySelectorAll('input[name="weightMethod"]').forEach(elem => {
            elem.addEventListener('change', function(event) {
                if (event.target.value === 'manual') {
                    updateManualWeightsUI();
                    manualWeightsContainer.style.display = 'block';
                } else {
                    manualWeightsContainer.style.display = 'none';
                }
            });
        });
    }

    if(stockSelector) stockSelector.addEventListener('change', updateManualWeightsUI);
    if(savePortfolioBtn) savePortfolioBtn.addEventListener('click', savePortfolio);

    function updateManualWeightsUI() {
        if (!stockSelector) return;
        const selectedStocks = Array.from(stockSelector.selectedOptions).map(opt => opt.value);
        let html = '<h6>Set Manual Weights (%)</h6>';
        selectedStocks.forEach(stock => {
            html += `
                <div class="input-group input-group-sm mb-2">
                    <span class="input-group-text" style="width: 120px;">${stock}</span>
                    <input type="number" class="form-control manual-weight-input" data-stock="${stock}" value="0" min="0" max="100" step="0.1">
                </div>
            `;
        });
        html += '<p class="text-end small text-muted mt-2">Total: <b id="manualWeightTotal">0.0</b>%</p>';
        manualWeightsContainer.innerHTML = html;
        document.querySelectorAll('.manual-weight-input').forEach(input => {
            input.addEventListener('input', updateTotalWeight);
        });
        updateTotalWeight();
    }

    function updateTotalWeight() {
        let total = 0;
        document.querySelectorAll('.manual-weight-input').forEach(input => {
            total += parseFloat(input.value) || 0;
        });
        const totalEl = document.getElementById('manualWeightTotal');
        if (totalEl) {
            totalEl.textContent = total.toFixed(1);
            totalEl.classList.remove('text-danger', 'text-success');
            if (Math.abs(total - 100.0) > 0.1 && total > 0) {
                totalEl.classList.add('text-danger');
            } else if (Math.abs(total - 100.0) < 0.1) {
                totalEl.classList.add('text-success');
            }
        }
    }
    
    async function savePortfolio() {
        const name = document.getElementById('portfolioName').value;
        const stocks = Array.from(stockSelector.selectedOptions).map(opt => opt.value);
        const method = document.querySelector('input[name="weightMethod"]:checked').value;
        const statusDiv = document.getElementById('portfolioSaveStatus');

        if (!name.trim()) { statusDiv.innerHTML = `<div class="alert alert-danger p-2">Portfolio name is required.</div>`; return; }
        if (stocks.length === 0) { statusDiv.innerHTML = `<div class="alert alert-danger p-2">Please select at least one stock.</div>`; return; }

        let payload = { name, stocks, optimize: method === 'hrp' };

        if (method === 'manual') {
            let weights = {};
            let total = 0;
            document.querySelectorAll('.manual-weight-input').forEach(input => {
                const weight = (parseFloat(input.value) || 0) / 100;
                weights[input.dataset.stock] = weight;
                total += weight;
            });
            if (Math.abs(total - 1.0) > 0.01) {
                statusDiv.innerHTML = `<div class="alert alert-danger p-2">Total weight must be exactly 100%.</div>`;
                return;
            }
            payload.weights = weights;
        }
        
        statusDiv.innerHTML = '<div class="text-muted">Saving...</div>';
        try {
            const response = await fetch('/api/portfolios', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
            const result = await response.json();
            if(response.ok) {
                statusDiv.innerHTML = `<div class="alert alert-success p-2">Portfolio '${result.name}' saved!</div>`;
                loadCustomPortfolios();
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger p-2">${result.error}</div>`;
            }
        } catch (e) {
            statusDiv.innerHTML = `<div class="alert alert-danger p-2">An unexpected error occurred.</div>`;
        }
    }


    // --- BACKTESTING SECTION ---
    const backtestBtn = document.getElementById('runBacktestBtn');
    const downloadCsvBtn = document.getElementById('downloadCsvBtn');
    const backtestTypeSelector = document.getElementById('backtestTypeSelector');

    if (backtestBtn) backtestBtn.addEventListener('click', runBacktest);
    if (downloadCsvBtn) downloadCsvBtn.addEventListener('click', downloadLogsAsCsv);
    if (backtestTypeSelector) {
        backtestTypeSelector.addEventListener('change', toggleBacktestOptions);
        loadCustomPortfolios();
    }

    function toggleBacktestOptions() {
        const type = backtestTypeSelector.value;
        document.getElementById('mlStrategyOptions').style.display = (type === 'ml_strategy') ? 'block' : 'none';
        document.getElementById('customPortfolioOptions').style.display = (type === 'custom') ? 'block' : 'none';
    }

    async function loadCustomPortfolios() {
        try {
            const selector = document.getElementById('customPortfolioSelector');
            const container = document.getElementById('savedPortfoliosContainer');
            const response = await fetch('/api/portfolios');
            const portfolios = await response.json();
            
            if (selector) {
                selector.innerHTML = '';
                if (portfolios && portfolios.length > 0) {
                    portfolios.forEach(p => {
                        selector.innerHTML += `<option value="${p.id}">${p.name}</option>`;
                    });
                } else {
                    selector.innerHTML = '<option disabled>No custom portfolios saved yet.</option>';
                }
            }

            if (container) {
                 if (portfolios && portfolios.length > 0) {
                    let listHtml = '<ul class="list-group">';
                    portfolios.forEach(p => {
                        listHtml += `<li class="list-group-item">${p.name}</li>`;
                    });
                    listHtml += '</ul>';
                    container.innerHTML = listHtml;
                 } else {
                    container.innerHTML = '<p class="text-muted">Your saved portfolios will appear here.</p>';
                 }
            }
        } catch (e) {
            console.error("Failed to load portfolios", e);
        }
    }
    
    function createReturnsTable(tableDataJson, tableContainerId) {
        const container = document.getElementById(tableContainerId);
        if (!tableDataJson) { container.innerHTML = '<p class="text-muted small">No data.</p>'; return; }
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
        } catch(e) { console.error("Error building table:", e); container.innerHTML = '<p class="text-danger small">Error rendering table.</p>'; }
    }
    
    function createRebalanceLogTable(logs) {
        lastBacktestLogs = logs;
        const container = document.getElementById('rebalanceLogContainer');
        if (!logs || logs.length === 0) { container.innerHTML = '<p class="text-muted small">No rebalancing logs.</p>'; return; }
        let tableHtml = '<table class="table table-sm table-hover"><thead><tr><th>Date</th><th>Action</th><th>Details</th></tr></thead><tbody>';
        logs.forEach(log => {
            let detailsHtml = '';
            if (log.Action.includes('Hold Cash')) {
                detailsHtml = `<span class="text-muted">${log.Details}</span>`;
            } else {
                detailsHtml = Object.entries(log.Details).filter(([k, v]) => v > 0).sort((a,b) => b[1] - a[1]).map(([k, v]) => `${k}: ${(v * 100).toFixed(1)}%`).join('<br>');
            }
            tableHtml += `<tr><td>${log.Date}</td><td>${log.Action}</td><td>${detailsHtml}</td></tr>`;
        });
        container.innerHTML = tableHtml + '</tbody></table>';
    }
    
    function downloadLogsAsCsv() {
        if (lastBacktestLogs.length === 0) { alert("No log data to download."); return; }
        let csvContent = "data:text/csv;charset=utf-8,Date,Action,Symbol,Weight,Comment\n";
        lastBacktestLogs.forEach(log => {
            if (log.Action.includes('Hold Cash')) {
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
    
    function createFullMetricsTable(kpis) {
        const container = document.getElementById('fullMetricsTableContainer');
        if (!kpis || Object.keys(kpis).length === 0) { container.innerHTML = '<p class="text-muted small">No metrics data.</p>'; return; }
        let tableHtml = '<table class="table table-sm table-striped"><tbody>';
        for (const [key, value] of Object.entries(kpis)) {
            let formattedValue = value;
            if (typeof value === 'number') {
                if (key.toLowerCase().includes('cagr') || key.includes('﹪') || key.includes('%') || key.toLowerCase().includes('drawdown') || key.toLowerCase().includes('var')) {
                    formattedValue = (value * 100).toFixed(2) + '%';
                } else if (value > 1000) {
                     formattedValue = value.toLocaleString(undefined, {maximumFractionDigits: 0});
                } else {
                    formattedValue = value.toFixed(2);
                }
            }
            tableHtml += `<tr><th class="fw-normal small">${key}</th><td class="text-end">${formattedValue}</td></tr>`;
        }
        container.innerHTML = tableHtml + '</tbody></table>';
    }

    function resetBacktestUI() {
        document.getElementById('backtestResultContainer').style.display = 'none';
        if (typeof Plotly !== 'undefined') {
            Plotly.purge('backtestEquityChart');
            Plotly.purge('backtestDrawdownChart');
            Plotly.purge('historicalWeightsChart');
            Plotly.purge('historicalSectorsChart');
        }
        const kpiIds = ['cagrValue', 'sharpeValue', 'drawdownValue', 'calmarValue', 'betaValue', 'sortinoValue', 'varValue', 'cvarValue'];
        kpiIds.forEach(id => { if(document.getElementById(id)) document.getElementById(id).innerText = '-'; });
        document.getElementById('monthlyReturnsTable').innerHTML = '';
        document.getElementById('yearlyReturnsTable').innerHTML = '';
        document.getElementById('rebalanceLogContainer').innerHTML = '';
        document.getElementById('fullMetricsTableContainer').innerHTML = '<p class="text-muted small">Run a backtest to see the detailed metrics report.</p>';
        document.getElementById('aiReportContainer').innerHTML = '<p class="text-muted small">Run a backtest to generate an AI-powered analysis of the results.</p>';
        lastBacktestLogs = [];
    }

    function displayBacktestResults(results) {
        const container = document.getElementById('backtestResultContainer');
        if (!results || !results.kpis) {
            document.getElementById('backtestStatus').innerHTML = `<div class="error-message">Received invalid or empty results from the backtest.</div>`;
            document.getElementById('backtestStatus').style.display = 'block';
            return;
        }

        const kpis = results.kpis;
        if (kpis.Error) {
             document.getElementById('backtestStatus').innerHTML = `<div class="error-message">${kpis.Error}</div>`;
             document.getElementById('backtestStatus').style.display = 'block';
             return;
        }

        const kpiMapping = {
            cagrValue: kpis['CAGR﹪'] !== undefined ? (kpis['CAGR﹪'] * 100).toFixed(2) : (kpis['CAGR (%)'] ? kpis['CAGR (%)'].toFixed(2) : '-'),
            sharpeValue: kpis['Sharpe'] !== undefined ? kpis['Sharpe'].toFixed(2) : '-',
            drawdownValue: kpis['Max Drawdown'] !== undefined ? (kpis['Max Drawdown'] * 100).toFixed(2) : (kpis['Max Drawdown [%]'] ? kpis['Max Drawdown [%]'].toFixed(2) : '-'),
            calmarValue: kpis['Calmar'] !== undefined ? kpis['Calmar'].toFixed(2) : '-',
            betaValue: kpis['Beta'] !== undefined ? kpis['Beta'].toFixed(2) : '-',
            sortinoValue: kpis['Sortino'] !== undefined ? kpis['Sortino'].toFixed(2) : '-',
            varValue: kpis['Daily VaR'] !== undefined ? (kpis['Daily VaR'] * 100).toFixed(2) + '%' : '-',
            cvarValue: kpis['Daily CVaR'] !== undefined ? (kpis['Daily CVaR'] * 100).toFixed(2) + '%' : '-'
        };
        Object.entries(kpiMapping).forEach(([id, value]) => {
            if(document.getElementById(id)) document.getElementById(id).innerText = value;
        });
        
        const plotConfig = {responsive: true};
        if (results.charts && results.charts.equity && results.charts.equity.data && results.charts.equity.layout) {
            Plotly.newPlot('backtestEquityChart', results.charts.equity.data, results.charts.equity.layout, plotConfig);
        }
        if (results.charts && results.charts.drawdown && results.charts.drawdown.data && results.charts.drawdown.layout) {
            Plotly.newPlot('backtestDrawdownChart', results.charts.drawdown.data, results.charts.drawdown.layout, plotConfig);
        }
        if (results.charts && results.charts.historical_weights && results.charts.historical_weights.data && results.charts.historical_weights.layout) {
            Plotly.newPlot('historicalWeightsChart', results.charts.historical_weights.data, results.charts.historical_weights.layout, plotConfig);
        }
        if (results.charts && results.charts.historical_sectors && results.charts.historical_sectors.data && results.charts.historical_sectors.layout) {
            Plotly.newPlot('historicalSectorsChart', results.charts.historical_sectors.data, results.charts.historical_sectors.layout, plotConfig);
        }
        
        if(results.tables) {
            createReturnsTable(results.tables.monthly_returns, 'monthlyReturnsTable');
            createReturnsTable(results.tables.yearly_returns, 'yearlyReturnsTable');
        }
        if(results.logs) createRebalanceLogTable(results.logs);
        if(results.kpis) createFullMetricsTable(results.kpis);
        
        const aiReportContainer = document.getElementById('aiReportContainer');
        if (results.ai_report) {
            aiReportContainer.innerHTML = results.ai_report.replace(/\n\n/g, '<p>').replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
        } else {
            aiReportContainer.innerHTML = '<p class="text-muted small">AI report was not generated.</p>';
        }
        if (results.factor_exposure && !results.factor_exposure.error) {
        displayFactorExposure(results.factor_exposure);
        } else {
        const chartContainer = document.getElementById('factorExposureChart');
        const tableContainer = document.getElementById('factorExposureTable');
        chartContainer.innerHTML = ''; // Clear stale charts
        const errorMessage = results.factor_exposure ? results.factor_exposure.error : "Factor data not available.";
        tableContainer.innerHTML = `<div class="alert alert-warning p-2 small"><b>Factor Analysis Failed:</b><br>${errorMessage}</div>`;
       }

        container.style.display = 'block';
    }

    function runBacktest() {
        const backtestStatusDiv = document.getElementById('backtestStatus');
        resetBacktestUI();
        backtestStatusDiv.innerHTML = `<div class="d-flex justify-content-center align-items-center"><div class="spinner-border text-primary" role="status"></div><strong class="ms-3">Starting backtest...</strong></div>`;
        backtestStatusDiv.style.display = 'block';
        if (pollingInterval) clearInterval(pollingInterval);

        const backtestType = document.getElementById('backtestTypeSelector').value;
        let config = {
            type: backtestType,
            start_date: document.getElementById('backtestStartDate').value,
            end_date: document.getElementById('backtestEndDate').value,
            risk_free: document.getElementById('riskFreeInput').value / 100
        };

        if (backtestType === 'custom') {
            config.portfolio_id = document.getElementById('customPortfolioSelector').value;
        } else {
            config.universe = document.getElementById('backtestUniverse').value;
            config.top_n = document.getElementById('topNInput').value;
        }

        fetch('/api/run_backtest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) })
        .then(response => response.ok ? response.json() : Promise.reject(response))
        .then(data => {
            if (data.task_id) {
                backtestStatusDiv.innerHTML += `<p class="text-muted small mt-3">Task ID: ${data.task_id}</p>`;
                pollTaskStatus(data.task_id);
            } else {
                 backtestStatusDiv.innerHTML = `<div class="error-message">${data.error || 'Failed to start backtest task.'}</div>`;
            }
        })
        .catch(error => {
            console.error('Error starting backtest:', error);
            backtestStatusDiv.innerHTML = `<div class="error-message">Failed to start backtest task. Check server logs.</div>`;
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
});
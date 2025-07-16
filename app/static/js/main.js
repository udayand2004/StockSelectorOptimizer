document.addEventListener('DOMContentLoaded', function() {
    
    // --- COMMON VARIABLES & INITIALIZATION ---
    let currentBacktestResults = null;
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
    const importCsvBtn = document.getElementById('importCsvBtn');
    const csvFileInput = document.getElementById('csvFileInput');

    if(importCsvBtn) { importCsvBtn.addEventListener('click', handleCsvImport); }
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

    function handleCsvImport() {
        const file = csvFileInput.files[0];
        if (!file) {
            alert("Please select a CSV file to import.");
            return;
        }

        const reader = new FileReader();
        reader.onload = function(event) {
            try {
                const csv = event.target.result;
                const lines = csv.split('\n').filter(line => line.trim() !== '');
                const header = lines.shift().trim().toLowerCase().split(',');

                const symbolIndex = header.indexOf('symbol');
                const weightIndex = header.indexOf('weight');

                if (symbolIndex === -1 || weightIndex === -1) {
                    throw new Error('CSV must contain "Symbol" and "Weight" columns.');
                }

                const portfolio = lines.map(line => {
                    const values = line.trim().split(',');
                    return {
                        symbol: values[symbolIndex].trim().toUpperCase(),
                        weight: parseFloat(values[weightIndex])
                    };
                });
                
                populatePortfolioFromCsv(portfolio);

            } catch (e) {
                alert("Failed to parse CSV file. Error: " + e.message);
            }
        };
        reader.readAsText(file);
    }

    function populatePortfolioFromCsv(portfolio) {
        // 1. Set weighting method to manual
        document.getElementById('manualWeights').checked = true;
        manualWeightsContainer.style.display = 'block';

        // 2. Clear current selections and select stocks from CSV
        for(let i=0; i<stockSelector.options.length; i++) {
            stockSelector.options[i].selected = false;
        }
        portfolio.forEach(item => {
            const option = Array.from(stockSelector.options).find(opt => opt.value === item.symbol);
            if(option) {
                option.selected = true;
            } else {
                console.warn(`Symbol ${item.symbol} from CSV not found in stock list.`);
            }
        });

        // 3. Update the manual weights UI
        updateManualWeightsUI();
        
        // 4. Populate the weights from the CSV
        portfolio.forEach(item => {
            const input = document.querySelector(`.manual-weight-input[data-stock="${item.symbol}"]`);
            if(input) {
                input.value = item.weight.toFixed(2);
            }
        });

        // 5. Recalculate the total
        updateTotalWeight();
        alert("Portfolio imported successfully! Please review and save.");
    }

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
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');
    const explainFactorsBtn = document.getElementById('explainFactorsBtn');
    const backtestTypeSelector = document.getElementById('backtestTypeSelector');
    const showSectorBoxplotBtn = document.getElementById('showSectorBoxplotBtn'); 
    if (backtestBtn) backtestBtn.addEventListener('click', runBacktest);
    if (downloadCsvBtn) downloadCsvBtn.addEventListener('click', downloadLogsAsCsv);
    if (downloadPdfBtn) downloadPdfBtn.addEventListener('click', generatePdf);
    if (explainFactorsBtn) explainFactorsBtn.addEventListener('click', handleExplainFactors);
    if (backtestTypeSelector) {
        backtestTypeSelector.addEventListener('change', toggleBacktestOptions);
        loadCustomPortfolios();
    }
    if (showSectorBoxplotBtn) { showSectorBoxplotBtn.addEventListener('click', showSectorBoxplot); } // <<< --- ADD THIS LINE
    if (showFactorBoxplotBtn) { showFactorBoxplotBtn.addEventListener('click', showFactorBoxplot); } 
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
        currentBacktestResults = null;
        document.getElementById('backtestResultContainer').style.display = 'none';
        document.getElementById('aiChatbotContainer').style.display = 'none';
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
        currentBacktestResults = results;
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

        // Show the chatbot container now that there are results
        document.getElementById('aiChatbotContainer').style.display = 'block';
        // Clear any previous chat history
        const chatDisplay = document.getElementById('chatDisplay');
        chatDisplay.innerHTML = '<div class="chat-message bot-message">Hello! Ask me about this backtest report.</div>';
        
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
    // --- ADD THIS ENTIRE NEW FUNCTION ---
    function showSectorBoxplot() {
        if (!currentBacktestResults || !currentBacktestResults.charts || !currentBacktestResults.charts.historical_sectors) {
            alert("No backtest data available. Please run a backtest first.");
            return;
        }

        const sourceData = currentBacktestResults.charts.historical_sectors.data;

        // Transform the stacked bar data into box plot data
        const boxplotTraces = sourceData.map(trace => {
            // For a box plot, the 'y' is the array of all weight observations for that sector
            return {
                x: trace.y, // Convert weights to percentages
                type: 'box',
                name: trace.name,
                orientation: 'h',
                boxpoints: 'false', // Show all the individual rebalance points
                jitter: 0.4,      // Add some horizontal noise to see points better
                pointpos: -1.8,   // Position points to the left of the box
                marker: {
                    size: 4
                }
            };
        });

        const layout = {
            title: 'Distribution of Sector Weights Over Time',
            xaxis: {
                title: 'Allocation Weight (%)',
                zeroline: true,
                range: [0, 100]
            },
            yaxis: {                  // SWAPPED: y-axis is now the categorical axis
            autorange: 'reversed', // This keeps the order consistent with the original chart
            automargin: true       // Ensures long labels are not cut off
            },
            margin: { t: 50, b: 50, l: 150, r: 20 },
            showlegend: false // Legend is redundant as names are on x-axis
        };

        const modalEl = document.getElementById('sectorBoxplotModal');
        const boxplotModal = new bootstrap.Modal(modalEl);
    
        // We need to plot *after* the modal is shown to ensure Plotly can get the correct div size
        modalEl.addEventListener('shown.bs.modal', function () {
        Plotly.newPlot('sectorBoxplotChart', boxplotTraces, layout, {responsive: true});
    }, { once: true }); // Use 'once' to prevent this from firing multiple times.

        boxplotModal.show();
    }
    function showFactorBoxplot() {
        if (!currentBacktestResults || !currentBacktestResults.charts || !currentBacktestResults.charts.rolling_factor_betas) {
            alert("No rolling factor data available. Please run a backtest first.");
            return;
        }

        const rawData = currentBacktestResults.charts.rolling_factor_betas;
        if (rawData.error) {
             alert(`Could not generate plot: ${rawData.error}`);
             return;
        }

        // Parse the JSON data from the 'split' format
        const factorData = JSON.parse(rawData);
        const df = {};
        factorData.columns.forEach((col, i) => {
            df[col] = factorData.data.map(row => row[i]);
        });

        const boxplotTraces = [];
        // Loop through the columns (factors) to create a box trace for each
        for (const factorName in df) {
            // We don't typically create a box plot for Alpha, just the betas
            if (factorName.toLowerCase() === 'alpha') continue;

            boxplotTraces.push({
                x: df[factorName],
                type: 'box',
                name: factorName,
                orientation: 'h',
                boxpoints: 'false',
                hovertemplate: 
                `<b>%{y}</b><br>` + // Use {y} for the categorical name in horizontal plots
                `Max: %{x.max:.4f}<br>` +
                `Upper Fence: %{x.upperfence:.4f}<br>` +
                `Q3: %{x.q3:.4f}<br>` +
                `Median: %{x.median:.4f}<br>` +
                `Q1: %{x.q1:.4f}<br>` +
                `Lower Fence: %{x.lowerfence:.4f}<br>` +
                `Min: %{x.min:.4f}` +
                `<extra></extra>`, // The <extra> tag removes the default trace name from the tooltip
            });
        }
        
        const layout = {
            title: 'Distribution of Rolling Factor Betas',
            xaxis: {
                title: 'Beta',
                zeroline: true,
            },
            yaxis: {                  // SWAPPED: y-axis is now the categorical axis
            autorange: 'reversed',
            automargin: true
            },
            margin: { t: 50, b: 50, l: 120, r: 20 },
            showlegend: false
        };

        const modalEl = document.getElementById('factorBoxplotModal');
        const boxplotModal = new bootstrap.Modal(modalEl);
        
        modalEl.addEventListener('shown.bs.modal', function () {
            Plotly.newPlot('factorBoxplotChart', boxplotTraces, layout, {responsive: true});
        }, { once: true });

        boxplotModal.show();
    } 

    // --- AI CHATBOT SECTION ---
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const chatDisplay = document.getElementById('chatDisplay');

    if (chatForm) {
        chatForm.addEventListener('submit', handleChatSubmit);
    }

    function getBacktestContext() {
        const context = {
            kpis: {},
            full_metrics: {},
            ai_summary: ''
        };

        // 1. Scrape KPIs from the top cards
        const kpiIds = ['cagrValue', 'sharpeValue', 'drawdownValue', 'calmarValue', 'betaValue', 'sortinoValue', 'varValue', 'cvarValue'];
        kpiIds.forEach(id => {
            const el = document.getElementById(id);
            if(el) {
                // Get the text label from the sibling p tag
                const label = el.nextElementSibling.textContent;
                context.kpis[label] = el.textContent;
            }
        });

        // 2. Scrape the full metrics table
        const metricsTable = document.getElementById('fullMetricsTableContainer');
        metricsTable.querySelectorAll('tr').forEach(row => {
            const key = row.querySelector('th')?.textContent;
            const value = row.querySelector('td')?.textContent;
            if (key && value) {
                context.full_metrics[key] = value;
            }
        });

        // 3. Get the AI summary report
        context.ai_summary = document.getElementById('aiReportContainer').textContent;

        return context;
    }
    
    function appendChatMessage(message, sender) {
        const messageEl = document.createElement('div');
        messageEl.classList.add('chat-message', `${sender}-message`);
        messageEl.innerHTML = message; // Use innerHTML to render bold/breaks from AI
        chatDisplay.appendChild(messageEl);
        chatDisplay.scrollTop = chatDisplay.scrollHeight; // Auto-scroll to bottom
        return messageEl;
    }

    async function handleChatSubmit(e) {
        e.preventDefault();
        const userMessage = chatInput.value.trim();
        if (!userMessage) return;

        appendChatMessage(userMessage, 'user');
        chatInput.value = '';

        const thinkingEl = appendChatMessage('<i>Assistant is thinking...</i>', 'bot');
        thinkingEl.classList.add('thinking');

        try {
            const context = getBacktestContext();
            
            const response = await fetch('/api/ask_chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: userMessage,
                    context: context
                })
            });

            const data = await response.json();
            thinkingEl.remove(); // Remove the "thinking" message

            if (!response.ok) {
                throw new Error(data.answer || 'An unknown error occurred.');
            }
            
            appendChatMessage(data.answer, 'bot');

        } catch (error) {
            thinkingEl.remove();
            appendChatMessage(`<strong>Error:</strong> ${error.message}`, 'bot');
        }
    }

    // --- AI FACTOR EXPLANATION LOGIC ---
    const factorExplanationContainer = document.getElementById('factorExplanationContainer');

    async function handleExplainFactors(e) {
        e.preventDefault();
        
        // Show loader and hide previous text
        factorExplanationContainer.style.display = 'block';
        factorExplanationContainer.innerHTML = `
            <div class="d-flex align-items-center">
                <strong>Generating explanation with AI...</strong>
                <div class="spinner-border ms-auto" role="status" aria-hidden="true"></div>
            </div>`;

        try {
            const response = await fetch('/api/explain_factors', { method: 'POST' });
            const data = await response.json();
            if(response.ok) {
                factorExplanationContainer.innerHTML = data.explanation;
            } else {
                throw new Error(data.error || 'Failed to fetch explanation.');
            }
        } catch (error) {
            factorExplanationContainer.innerHTML = `<p class="text-danger">${error.message}</p>`;
        }
    }
});

async function generatePdf() {
    const reportContainer = document.getElementById('backtestResultContainer');
    if (!reportContainer || reportContainer.style.display === 'none') {
        alert("Please run a backtest first to generate a report.");
        return;
    }

    const originalTitle = document.title;
    document.title = "Backtest_Report"; // Set a good filename

    // Temporarily hide buttons for a cleaner PDF
    const pdfBtn = document.getElementById('downloadPdfBtn');
    const csvBtn = document.getElementById('downloadCsvBtn');
    const factorBtn = document.getElementById('explainFactorsBtn');
    pdfBtn.style.display = 'none';
    csvBtn.style.display = 'none';
    if(factorBtn) factorBtn.style.display = 'none';

    const loader = document.getElementById('loader');
    loader.style.display = 'block'; // Show loader

    try {
        // Get the HTML of the report section
        const reportHtml = reportContainer.innerHTML;

        const response = await fetch('/api/generate_pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'text/plain' },
            body: reportHtml
        });

        if (!response.ok) {
            throw new Error('PDF generation failed on the server.');
        }

        // Get the PDF blob and create a download link
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'backtest_report.pdf';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error("Error generating PDF:", error);
        alert("Could not generate PDF. See console for details.");
    } finally {
         // Restore buttons and title
        pdfBtn.style.display = 'inline-block';
        csvBtn.style.display = 'inline-block';
        if(factorBtn) factorBtn.style.display = 'inline-block';
        document.title = originalTitle;
        loader.style.display = 'none'; // Hide loader
    }
}
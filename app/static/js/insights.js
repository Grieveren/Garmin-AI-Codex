/**
 * Training Analytics Dashboard - Interactive Plotly Charts
 * Implements 5 analytics visualizations with responsive design and dark mode support
 */

// Global state
const state = {
    dateRange: 30,
    customStartDate: null,
    customEndDate: null,
    selectedMetric: 'hrv',
    isDarkMode: false,
    charts: {},
};

// Debounce utility for API calls
let debounceTimer;
function debounce(func, delay = 300) {
    return function(...args) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => func.apply(this, args), delay);
    };
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initializeControls();
    checkDarkMode();
    loadAllCharts();
    setupExportButtons();
});

/**
 * Initialize event listeners for controls
 */
function initializeControls() {
    // Date range selector
    const dateRangeSelect = document.getElementById('date-range');
    if (dateRangeSelect) {
        dateRangeSelect.addEventListener('change', handleDateRangeChange);
    }

    // Custom date inputs
    const applyCustomBtn = document.getElementById('apply-custom-range');
    if (applyCustomBtn) {
        applyCustomBtn.addEventListener('click', applyCustomDateRange);
    }

    // Recovery metric selector
    const metricSelector = document.getElementById('metric-selector');
    if (metricSelector) {
        metricSelector.addEventListener('change', handleMetricChange);
    }

    // Load saved preference from localStorage
    const savedRange = localStorage.getItem('analytics-date-range');
    if (savedRange && dateRangeSelect) {
        dateRangeSelect.value = savedRange;
        state.dateRange = parseInt(savedRange);
    }
}

/**
 * Check and apply dark mode preference
 */
function checkDarkMode() {
    // Check if dark mode is active (from base.js)
    state.isDarkMode = document.body.classList.contains('dark-mode') ||
                       localStorage.getItem('theme') === 'dark';
}

/**
 * Handle date range selection changes
 */
function handleDateRangeChange(event) {
    const value = event.target.value;
    const customInputs = document.getElementById('custom-date-inputs');

    if (value === 'custom') {
        customInputs.style.display = 'flex';
    } else {
        customInputs.style.display = 'none';
        state.dateRange = parseInt(value);
        localStorage.setItem('analytics-date-range', value);
        debounce(() => loadAllCharts(), 300)();
    }
}

/**
 * Apply custom date range
 */
function applyCustomDateRange() {
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;

    if (!startDate || !endDate) {
        showError('Please select both start and end dates');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        showError('Start date must be before end date');
        return;
    }

    state.customStartDate = startDate;
    state.customEndDate = endDate;
    loadAllCharts();
}

/**
 * Handle recovery metric selector change
 */
function handleMetricChange(event) {
    state.selectedMetric = event.target.value;
    loadRecoveryCorrelationChart();
}

/**
 * Load all charts
 */
async function loadAllCharts() {
    showLoading(true);
    hideError();

    try {
        await Promise.all([
            loadReadinessTrendChart(),
            loadTrainingLoadChart(),
            loadSleepPerformanceChart(),
            loadActivityBreakdownChart(),
            loadRecoveryCorrelationChart(),
        ]);

        // Update weekly summary
        await updateWeeklySummary();
    } catch (error) {
        console.error('Failed to load charts:', error);
        showError('Failed to load analytics data. Please try again.');
    } finally {
        showLoading(false);
    }
}

/**
 * Chart 1: Readiness Trend Line Chart
 */
async function loadReadinessTrendChart() {
    const chartDiv = 'readiness-chart';
    showChartLoading(chartDiv, true);

    try {
        const params = buildQueryParams();
        const response = await fetch(`/api/analytics/readiness-trend?${params}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data || data.length === 0) {
            showEmptyState(chartDiv, 'No readiness data available');
            return;
        }

        // Prepare data for plotting
        const dates = data.map(d => d.date);
        const scores = data.map(d => d.score);
        const recommendations = data.map(d => d.recommendation);
        const hoverText = data.map(d =>
            `Score: ${d.score}<br>` +
            `Recommendation: ${d.recommendation}<br>` +
            `HRV: ${d.hrv || 'N/A'}<br>` +
            `Sleep: ${d.sleep_score || 'N/A'}`
        );

        // Color zones for readiness
        const colors = scores.map(score => {
            if (score >= 70) return getColor('green');
            if (score >= 40) return getColor('yellow');
            return getColor('red');
        });

        const trace = {
            x: dates,
            y: scores,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Readiness Score',
            line: {
                color: getColor('primary'),
                width: 2,
            },
            marker: {
                size: 8,
                color: colors,
            },
            hovertext: hoverText,
            hoverinfo: 'text',
        };

        // Add zone shapes
        const shapes = [
            {
                type: 'rect',
                xref: 'paper',
                yref: 'y',
                x0: 0,
                x1: 1,
                y0: 70,
                y1: 100,
                fillcolor: getColor('green'),
                opacity: 0.1,
                line: { width: 0 },
            },
            {
                type: 'rect',
                xref: 'paper',
                yref: 'y',
                x0: 0,
                x1: 1,
                y0: 40,
                y1: 70,
                fillcolor: getColor('yellow'),
                opacity: 0.1,
                line: { width: 0 },
            },
            {
                type: 'rect',
                xref: 'paper',
                yref: 'y',
                x0: 0,
                x1: 1,
                y0: 0,
                y1: 40,
                fillcolor: getColor('red'),
                opacity: 0.1,
                line: { width: 0 },
            },
        ];

        const layout = {
            ...getBaseLayout('Readiness Score Over Time'),
            yaxis: {
                title: 'Readiness Score',
                range: [0, 100],
                gridcolor: getColor('grid'),
            },
            xaxis: {
                title: 'Date',
                gridcolor: getColor('grid'),
            },
            shapes,
        };

        Plotly.newPlot(chartDiv, [trace], layout, getConfig());
        state.charts[chartDiv] = true;
    } catch (error) {
        console.error('Failed to load readiness trend:', error);
        showEmptyState(chartDiv, 'Failed to load chart');
    } finally {
        showChartLoading(chartDiv, false);
    }
}

/**
 * Chart 2: Training Load Multi-line Chart
 */
async function loadTrainingLoadChart() {
    const chartDiv = 'training-load-chart';
    showChartLoading(chartDiv, true);

    try {
        const params = new URLSearchParams({ days: state.dateRange });
        const response = await fetch(`/api/analytics/training-load?${params}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data || data.length === 0) {
            showEmptyState(chartDiv, 'No training load data available');
            return;
        }

        const dates = data.map(d => d.date);

        // ACWR trace
        const acwrTrace = {
            x: dates,
            y: data.map(d => d.acwr || 0),
            type: 'scatter',
            mode: 'lines',
            name: 'ACWR',
            line: { color: getColor('primary'), width: 2 },
        };

        // Fitness trace
        const fitnessTrace = {
            x: dates,
            y: data.map(d => d.fitness || 0),
            type: 'scatter',
            mode: 'lines',
            name: 'Fitness',
            line: { color: getColor('blue'), width: 2 },
        };

        // Fatigue trace
        const fatigueTrace = {
            x: dates,
            y: data.map(d => d.fatigue || 0),
            type: 'scatter',
            mode: 'lines',
            name: 'Fatigue',
            line: { color: getColor('orange'), width: 2 },
        };

        // Form trace
        const formTrace = {
            x: dates,
            y: data.map(d => d.form || 0),
            type: 'scatter',
            mode: 'lines',
            name: 'Form',
            line: { color: getColor('purple'), width: 2 },
        };

        // Optimal ACWR zone (0.8-1.3)
        const shapes = [
            {
                type: 'rect',
                xref: 'paper',
                yref: 'y',
                x0: 0,
                x1: 1,
                y0: 0.8,
                y1: 1.3,
                fillcolor: getColor('green'),
                opacity: 0.1,
                line: { width: 0 },
            },
            {
                type: 'rect',
                xref: 'paper',
                yref: 'y',
                x0: 0,
                x1: 1,
                y0: 1.5,
                y1: 3,
                fillcolor: getColor('red'),
                opacity: 0.1,
                line: { width: 0 },
            },
        ];

        const layout = {
            ...getBaseLayout('Training Load Metrics'),
            yaxis: {
                title: 'Value',
                gridcolor: getColor('grid'),
            },
            xaxis: {
                title: 'Date',
                gridcolor: getColor('grid'),
            },
            shapes,
            showlegend: true,
        };

        Plotly.newPlot(
            chartDiv,
            [acwrTrace, fitnessTrace, fatigueTrace, formTrace],
            layout,
            getConfig()
        );
        state.charts[chartDiv] = true;
    } catch (error) {
        console.error('Failed to load training load:', error);
        showEmptyState(chartDiv, 'Failed to load chart');
    } finally {
        showChartLoading(chartDiv, false);
    }
}

/**
 * Chart 3: Sleep-Performance Correlation Scatter Plot
 */
async function loadSleepPerformanceChart() {
    const chartDiv = 'sleep-performance-chart';
    showChartLoading(chartDiv, true);

    try {
        const params = buildQueryParams();
        const response = await fetch(`/api/analytics/sleep-performance?${params}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data || data.length === 0) {
            showEmptyState(chartDiv, 'No sleep performance data available');
            return;
        }

        const sleepScores = data.map(d => d.sleep_score || 0);
        const readinessScores = data.map(d => d.readiness || 0);
        const hrvValues = data.map(d => d.hrv || 30);
        const hoverText = data.map(d =>
            `Date: ${d.date}<br>` +
            `Sleep Score: ${d.sleep_score || 'N/A'}<br>` +
            `Readiness: ${d.readiness || 'N/A'}<br>` +
            `HRV: ${d.hrv || 'N/A'}`
        );

        const trace = {
            x: sleepScores,
            y: readinessScores,
            type: 'scatter',
            mode: 'markers',
            name: 'Sleep vs Readiness',
            marker: {
                size: hrvValues.map(hrv => Math.max(5, hrv / 4)), // Size based on HRV
                color: getColor('primary'),
                opacity: 0.6,
                line: {
                    color: getColor('border'),
                    width: 1,
                },
            },
            hovertext: hoverText,
            hoverinfo: 'text',
        };

        // Calculate and add trendline
        const trendline = calculateTrendline(sleepScores, readinessScores);
        const trendTrace = {
            x: [Math.min(...sleepScores), Math.max(...sleepScores)],
            y: [
                trendline.slope * Math.min(...sleepScores) + trendline.intercept,
                trendline.slope * Math.max(...sleepScores) + trendline.intercept,
            ],
            type: 'scatter',
            mode: 'lines',
            name: `Trendline (R² = ${trendline.r2.toFixed(2)})`,
            line: {
                color: getColor('orange'),
                width: 2,
                dash: 'dash',
            },
        };

        const layout = {
            ...getBaseLayout('Sleep Quality vs Readiness'),
            xaxis: {
                title: 'Sleep Score',
                gridcolor: getColor('grid'),
            },
            yaxis: {
                title: 'Readiness Score',
                gridcolor: getColor('grid'),
            },
            showlegend: true,
        };

        Plotly.newPlot(chartDiv, [trace, trendTrace], layout, getConfig());
        state.charts[chartDiv] = true;
    } catch (error) {
        console.error('Failed to load sleep performance:', error);
        showEmptyState(chartDiv, 'Failed to load chart');
    } finally {
        showChartLoading(chartDiv, false);
    }
}

/**
 * Chart 4: Activity Breakdown Pie and Bar Charts
 */
async function loadActivityBreakdownChart() {
    const chartDiv = 'activity-breakdown-chart';
    showChartLoading(chartDiv, true);

    try {
        const params = buildQueryParams();
        const response = await fetch(`/api/analytics/activity-breakdown?${params}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data || Object.keys(data).length === 0) {
            showEmptyState(chartDiv, 'No activity data available');
            return;
        }

        // Prepare data
        const activityTypes = Object.keys(data);
        const durations = activityTypes.map(type => data[type].duration_min);
        const distances = activityTypes.map(type => data[type].distance_km);

        // Create pie chart for time distribution
        const pieTrace = {
            labels: activityTypes,
            values: durations,
            type: 'pie',
            hole: 0.4,
            marker: {
                colors: generateColors(activityTypes.length),
            },
            textinfo: 'label+percent',
            hoverinfo: 'label+value+percent',
            domain: { x: [0, 0.45], y: [0, 1] },
        };

        // Create bar chart for distance
        const barTrace = {
            x: activityTypes,
            y: distances,
            type: 'bar',
            marker: {
                color: getColor('primary'),
            },
            xaxis: 'x2',
            yaxis: 'y2',
        };

        const layout = {
            ...getBaseLayout('Activity Distribution'),
            grid: { rows: 1, columns: 2 },
            showlegend: false,
            xaxis2: {
                title: 'Activity Type',
                domain: [0.55, 1],
                gridcolor: getColor('grid'),
            },
            yaxis2: {
                title: 'Distance (km)',
                domain: [0, 1],
                anchor: 'x2',
                gridcolor: getColor('grid'),
            },
        };

        Plotly.newPlot(chartDiv, [pieTrace, barTrace], layout, getConfig());
        state.charts[chartDiv] = true;
    } catch (error) {
        console.error('Failed to load activity breakdown:', error);
        showEmptyState(chartDiv, 'Failed to load chart');
    } finally {
        showChartLoading(chartDiv, false);
    }
}

/**
 * Chart 5: Recovery Metric Correlation
 */
async function loadRecoveryCorrelationChart() {
    const chartDiv = 'recovery-correlation-chart';
    showChartLoading(chartDiv, true);

    try {
        const params = buildQueryParams();
        params.append('metric', state.selectedMetric);

        const response = await fetch(`/api/analytics/recovery-correlation?${params}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        const data = result.data || [];

        if (data.length === 0) {
            showEmptyState(chartDiv, 'No correlation data available');
            return;
        }

        const metricValues = data.map(d => d.metric_value);
        const readinessValues = data.map(d => d.readiness);
        const hoverText = data.map(d =>
            `Date: ${d.date}<br>` +
            `${getMetricLabel(state.selectedMetric)}: ${d.metric_value}<br>` +
            `Readiness: ${d.readiness}`
        );

        const trace = {
            x: metricValues,
            y: readinessValues,
            type: 'scatter',
            mode: 'markers',
            name: 'Data Points',
            marker: {
                size: 8,
                color: getColor('primary'),
                opacity: 0.6,
            },
            hovertext: hoverText,
            hoverinfo: 'text',
        };

        // Add trendline
        const trendline = calculateTrendline(metricValues, readinessValues);
        const trendTrace = {
            x: [Math.min(...metricValues), Math.max(...metricValues)],
            y: [
                trendline.slope * Math.min(...metricValues) + trendline.intercept,
                trendline.slope * Math.max(...metricValues) + trendline.intercept,
            ],
            type: 'scatter',
            mode: 'lines',
            name: `Trendline (r = ${result.correlation_coefficient || 0})`,
            line: {
                color: getColor('orange'),
                width: 2,
                dash: 'dash',
            },
        };

        const layout = {
            ...getBaseLayout(`${getMetricLabel(state.selectedMetric)} vs Readiness`),
            xaxis: {
                title: getMetricLabel(state.selectedMetric),
                gridcolor: getColor('grid'),
            },
            yaxis: {
                title: 'Readiness Score',
                gridcolor: getColor('grid'),
            },
            showlegend: true,
        };

        Plotly.newPlot(chartDiv, [trace, trendTrace], layout, getConfig());
        state.charts[chartDiv] = true;
    } catch (error) {
        console.error('Failed to load recovery correlation:', error);
        showEmptyState(chartDiv, 'Failed to load chart');
    } finally {
        showChartLoading(chartDiv, false);
    }
}

/**
 * Update weekly summary statistics
 */
async function updateWeeklySummary() {
    try {
        // Fetch last 7 days of data
        const params = new URLSearchParams({ days: 7 });

        const [activityData, readinessData] = await Promise.all([
            fetch(`/api/analytics/activity-breakdown?${params}`).then(r => r.json()),
            fetch(`/api/analytics/readiness-trend?${params}`).then(r => r.json()),
        ]);

        // Calculate totals
        let totalActivities = 0;
        let totalDistance = 0;
        let totalDuration = 0;

        Object.values(activityData).forEach(activity => {
            totalActivities += activity.count;
            totalDistance += activity.distance_km || 0;
            totalDuration += activity.duration_min || 0;
        });

        // Calculate average readiness
        const avgReadiness = readinessData.length > 0
            ? Math.round(readinessData.reduce((sum, d) => sum + d.score, 0) / readinessData.length)
            : 0;

        // Update UI
        document.getElementById('summary-activities').textContent = totalActivities;
        document.getElementById('summary-distance').textContent = `${totalDistance.toFixed(1)} km`;
        document.getElementById('summary-duration').textContent = `${Math.round(totalDuration)} min`;
        document.getElementById('summary-readiness').textContent = avgReadiness;
    } catch (error) {
        console.error('Failed to update weekly summary:', error);
    }
}

/**
 * Setup export buttons for charts
 */
function setupExportButtons() {
    const exportButtons = document.querySelectorAll('.btn-export');

    exportButtons.forEach(button => {
        button.addEventListener('click', () => {
            const chartId = button.getAttribute('data-chart');
            exportChartAsPNG(chartId);
        });
    });
}

/**
 * Export chart as PNG
 */
function exportChartAsPNG(chartId) {
    if (!state.charts[chartId]) {
        console.error('Chart not loaded:', chartId);
        return;
    }

    Plotly.downloadImage(chartId, {
        format: 'png',
        width: 1200,
        height: 800,
        filename: `${chartId}-${new Date().toISOString().split('T')[0]}`,
    });
}

// Helper Functions

/**
 * Build query parameters for API calls
 */
function buildQueryParams() {
    const params = new URLSearchParams();

    if (state.customStartDate && state.customEndDate) {
        params.append('start_date', state.customStartDate);
        params.append('end_date', state.customEndDate);
    } else {
        params.append('days', state.dateRange);
    }

    return params;
}

/**
 * Get base Plotly layout
 */
function getBaseLayout(title) {
    return {
        title: {
            text: title,
            font: {
                color: getColor('text'),
                size: 16,
            },
        },
        paper_bgcolor: getColor('background'),
        plot_bgcolor: getColor('background'),
        font: {
            color: getColor('text'),
            family: 'system-ui, -apple-system, sans-serif',
        },
        margin: { t: 50, r: 30, b: 50, l: 50 },
        hovermode: 'closest',
    };
}

/**
 * Get Plotly configuration
 */
function getConfig() {
    return {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    };
}

/**
 * Get color based on theme
 */
function getColor(name) {
    const colors = {
        light: {
            primary: '#4f46e5',
            blue: '#3b82f6',
            orange: '#f59e0b',
            purple: '#8b5cf6',
            green: '#10b981',
            yellow: '#fbbf24',
            red: '#ef4444',
            text: '#1f2937',
            background: '#ffffff',
            grid: '#e5e7eb',
            border: '#d1d5db',
        },
        dark: {
            primary: '#818cf8',
            blue: '#60a5fa',
            orange: '#fbbf24',
            purple: '#a78bfa',
            green: '#34d399',
            yellow: '#fcd34d',
            red: '#f87171',
            text: '#f9fafb',
            background: '#1f2937',
            grid: '#374151',
            border: '#4b5563',
        },
    };

    const theme = state.isDarkMode ? 'dark' : 'light';
    return colors[theme][name] || colors[theme].primary;
}

/**
 * Generate array of colors
 */
function generateColors(count) {
    const baseColors = [
        getColor('primary'),
        getColor('blue'),
        getColor('orange'),
        getColor('purple'),
        getColor('green'),
    ];

    const colors = [];
    for (let i = 0; i < count; i++) {
        colors.push(baseColors[i % baseColors.length]);
    }

    return colors;
}

/**
 * Calculate linear trendline
 */
function calculateTrendline(xValues, yValues) {
    const n = xValues.length;
    const sumX = xValues.reduce((a, b) => a + b, 0);
    const sumY = yValues.reduce((a, b) => a + b, 0);
    const sumXY = xValues.reduce((sum, x, i) => sum + x * yValues[i], 0);
    const sumXX = xValues.reduce((sum, x) => sum + x * x, 0);

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    // Calculate R²
    const yMean = sumY / n;
    const ssTotal = yValues.reduce((sum, y) => sum + Math.pow(y - yMean, 2), 0);
    const ssResidual = yValues.reduce(
        (sum, y, i) => sum + Math.pow(y - (slope * xValues[i] + intercept), 2),
        0
    );
    const r2 = 1 - ssResidual / ssTotal;

    return { slope, intercept, r2 };
}

/**
 * Get metric label
 */
function getMetricLabel(metric) {
    const labels = {
        hrv: 'HRV (ms)',
        sleep: 'Sleep Duration (hours)',
        rhr: 'Resting Heart Rate (bpm)',
    };

    return labels[metric] || metric;
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Show/hide chart loading spinner
 */
function showChartLoading(chartId, show) {
    const container = document.getElementById(chartId)?.parentElement;
    if (!container) return;

    const loader = container.querySelector('.chart-loading');
    if (loader) {
        loader.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Show error message
 */
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
}

/**
 * Hide error message
 */
function hideError() {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

/**
 * Show empty state for a chart
 */
function showEmptyState(chartId, message) {
    const chartDiv = document.getElementById(chartId);
    if (chartDiv) {
        chartDiv.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; height: 300px; color: ${getColor('text')};">
                <p>${message}</p>
            </div>
        `;
    }
}

// Listen for theme changes from base.js
window.addEventListener('storage', (event) => {
    if (event.key === 'theme') {
        checkDarkMode();
        // Reload charts with new theme
        loadAllCharts();
    }
});

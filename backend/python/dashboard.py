from flask import Flask, render_template_string, jsonify, request
import requests
import plotly.graph_objs as go
import plotly.utils
import json
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

# Configuration
GO_SERVER_URL = "http://localhost:8080"
ALERT_THRESHOLDS = {
    'cpu': 80.0,
    'memory': 85.0,
    'disk': 90.0
}

# Store active alerts
active_alerts = []
alerts_lock = threading.Lock()

def check_alerts():
    """Background thread to check for threshold violations"""
    while True:
        try:
            response = requests.get(f"{GO_SERVER_URL}/latest", timeout=5)
            if response.status_code == 200:
                latest_metrics = response.json()
                
                with alerts_lock:
                    active_alerts.clear()
                    
                    for hostname, metrics in latest_metrics.items():
                        if metrics['cpu_usage'] > ALERT_THRESHOLDS['cpu']:
                            active_alerts.append({
                                'hostname': hostname,
                                'type': 'CPU',
                                'value': metrics['cpu_usage'],
                                'threshold': ALERT_THRESHOLDS['cpu'],
                                'timestamp': datetime.now().isoformat()
                            })
                        
                        if metrics['memory_usage'] > ALERT_THRESHOLDS['memory']:
                            active_alerts.append({
                                'hostname': hostname,
                                'type': 'Memory',
                                'value': metrics['memory_usage'],
                                'threshold': ALERT_THRESHOLDS['memory'],
                                'timestamp': datetime.now().isoformat()
                            })
                        
                        if metrics['disk_usage'] > ALERT_THRESHOLDS['disk']:
                            active_alerts.append({
                                'hostname': hostname,
                                'type': 'Disk',
                                'value': metrics['disk_usage'],
                                'threshold': ALERT_THRESHOLDS['disk'],
                                'timestamp': datetime.now().isoformat()
                            })
        
        except Exception as e:
            print(f"Error checking alerts: {e}")
        
        time.sleep(10)

# Start alert monitoring thread
alert_thread = threading.Thread(target=check_alerts, daemon=True)
alert_thread.start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Watchtower</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .controls label {
            margin-right: 10px;
            font-weight: bold;
        }
        .controls select, .controls button {
            padding: 8px 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            margin-right: 10px;
        }
        .controls button {
            background: #667eea;
            color: white;
            cursor: pointer;
            border: none;
        }
        .controls button:hover {
            background: #5568d3;
        }
        .alerts {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .alert-item {
            background: #fee;
            border-left: 4px solid #f44;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .alert-item strong {
            color: #c33;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .metric-card h3 {
            margin-bottom: 10px;
            color: #333;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-ok { background: #4caf50; }
        .status-warning { background: #ff9800; }
        .status-critical { background: #f44336; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Watchtower by Ray Laboratories</h1>
        
        <div class="controls">
            <label for="hostname">Host:</label>
            <select id="hostname">
                <option value="">All Hosts</option>
            </select>
            
            <label for="timerange">Time Range:</label>
            <select id="timerange">
                <option value="1">Last Hour</option>
                <option value="6">Last 6 Hours</option>
                <option value="24" selected>Last 24 Hours</option>
            </select>
            
            <button onclick="refreshData()">Refresh</button>
            <button onclick="toggleAutoRefresh()">Auto-Refresh: <span id="auto-status">ON</span></button>
        </div>
        
        <div id="alerts" class="alerts">
            <h3>🚨 Active Alerts</h3>
            <div id="alerts-list">No active alerts</div>
        </div>
        
        <div class="metrics-grid" id="latest-metrics"></div>
        
        <div class="chart-container">
            <h3>CPU Usage Over Time</h3>
            <div id="cpu-chart"></div>
        </div>
        
        <div class="chart-container">
            <h3>Memory Usage Over Time</h3>
            <div id="memory-chart"></div>
        </div>
        
        <div class="chart-container">
            <h3>Disk Usage Over Time</h3>
            <div id="disk-chart"></div>
        </div>
    </div>
    
    <script>
        let autoRefresh = true;
        let refreshInterval;
        
        function getStatus(value, thresholds) {
            if (value > thresholds.critical) return 'status-critical';
            if (value > thresholds.warning) return 'status-warning';
            return 'status-ok';
        }
        
        function formatValue(value) {
            return value.toFixed(2);
        }
        
        async function refreshData() {
            const hostname = document.getElementById('hostname').value;
            const hours = document.getElementById('timerange').value;
            
            // Fetch latest metrics
            const latestResponse = await fetch('/api/latest');
            const latestData = await latestResponse.json();
            
            // Update latest metrics cards
            const metricsHtml = Object.entries(latestData).map(([host, metrics]) => `
                <div class="metric-card">
                    <h3>${host}</h3>
                    <div style="margin: 10px 0;">
                        <span class="${getStatus(metrics.cpu_usage, {warning: 70, critical: 80})} status-indicator"></span>
                        CPU: <span class="metric-value">${formatValue(metrics.cpu_usage)}%</span>
                    </div>
                    <div style="margin: 10px 0;">
                        <span class="${getStatus(metrics.memory_usage, {warning: 75, critical: 85})} status-indicator"></span>
                        Memory: <span class="metric-value">${formatValue(metrics.memory_usage)}%</span>
                    </div>
                    <div style="margin: 10px 0;">
                        <span class="${getStatus(metrics.disk_usage, {warning: 80, critical: 90})} status-indicator"></span>
                        Disk: <span class="metric-value">${formatValue(metrics.disk_usage)}%</span>
                    </div>
                </div>
            `).join('');
            document.getElementById('latest-metrics').innerHTML = metricsHtml;
            
            // Update hostname dropdown
            const hostnameSelect = document.getElementById('hostname');
            const currentValue = hostnameSelect.value;
            hostnameSelect.innerHTML = '<option value="">All Hosts</option>';
            Object.keys(latestData).forEach(host => {
                hostnameSelect.innerHTML += `<option value="${host}">${host}</option>`;
            });
            hostnameSelect.value = currentValue;
            
            // Fetch historical data
            let url = `/api/query?hours=${hours}`;
            if (hostname) url += `&hostname=${hostname}`;
            
            const response = await fetch(url);
            const data = await response.json();
            
            // Fetch alerts
            const alertsResponse = await fetch('/api/alerts');
            const alerts = await alertsResponse.json();
            
            const alertsHtml = alerts.length > 0 
                ? alerts.map(alert => `
                    <div class="alert-item">
                        <strong>${alert.hostname}</strong> - ${alert.type}: 
                        ${formatValue(alert.value)}% (threshold: ${alert.threshold}%)
                        <br><small>${new Date(alert.timestamp).toLocaleString()}</small>
                    </div>
                  `).join('')
                : '<p>No active alerts</p>';
            document.getElementById('alerts-list').innerHTML = alertsHtml;
            
            // Prepare chart data
            const chartData = {};
            
            if (hostname) {
                chartData[hostname] = data;
            } else {
                Object.assign(chartData, data);
            }
            
            // Create charts
            createChart('cpu-chart', chartData, 'cpu_usage', 'CPU Usage (%)');
            createChart('memory-chart', chartData, 'memory_usage', 'Memory Usage (%)');
            createChart('disk-chart', chartData, 'disk_usage', 'Disk Usage (%)');
        }
        
        function createChart(elementId, data, metric, title) {
            const traces = [];
            
            for (const [hostname, metrics] of Object.entries(data)) {
                const times = metrics.map(m => new Date(m.timestamp / 1000000));
                const values = metrics.map(m => m[metric]);
                
                traces.push({
                    x: times,
                    y: values,
                    name: hostname,
                    type: 'scatter',
                    mode: 'lines+markers'
                });
            }
            
            const layout = {
                title: title,
                xaxis: { title: 'Time' },
                yaxis: { title: 'Percentage (%)' },
                hovermode: 'closest'
            };
            
            Plotly.newPlot(elementId, traces, layout);
        }
        
        function toggleAutoRefresh() {
            autoRefresh = !autoRefresh;
            document.getElementById('auto-status').textContent = autoRefresh ? 'ON' : 'OFF';
            
            if (autoRefresh) {
                startAutoRefresh();
            } else {
                clearInterval(refreshInterval);
            }
        }
        
        function startAutoRefresh() {
            refreshInterval = setInterval(refreshData, 10000);
        }
        
        // Initial load
        refreshData();
        startAutoRefresh();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/query')
def api_query():
    hostname = request.args.get('hostname', '')
    hours = request.args.get('hours', '24')
    
    url = f"{GO_SERVER_URL}/query?hours={hours}"
    if hostname:
        url += f"&hostname={hostname}"
    
    try:
        response = requests.get(url, timeout=5)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/latest')
def api_latest():
    try:
        response = requests.get(f"{GO_SERVER_URL}/latest", timeout=5)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
def api_alerts():
    with alerts_lock:
        return jsonify(active_alerts)

@app.route('/api/alerts/config', methods=['GET', 'POST'])
def api_alerts_config():
    if request.method == 'POST':
        new_thresholds = request.json
        ALERT_THRESHOLDS.update(new_thresholds)
        return jsonify({'status': 'ok', 'thresholds': ALERT_THRESHOLDS})
    return jsonify(ALERT_THRESHOLDS)

if __name__ == '__main__':
    print("=" * 60)
    print("System Monitoring Dashboard Starting...")
    print("=" * 60)
    print(f"Dashboard URL: http://localhost:5000")
    print(f"Go Server URL: {GO_SERVER_URL}")
    print(f"\nAlert Thresholds:")
    print(f"  CPU: {ALERT_THRESHOLDS['cpu']}%")
    print(f"  Memory: {ALERT_THRESHOLDS['memory']}%")
    print(f"  Disk: {ALERT_THRESHOLDS['disk']}%")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

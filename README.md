<div align="center">

# RAYLABS Watchtower

### A simple, easy to use system resource monitoring solution

[![Version](https://img.shields.io/badge/version-1.0.0-purple)](https://github.com/mochacinno-dev/Tourmaline)
[![License](https://img.shields.io/badge/license-GNU%20GPL%20v3.0-magenta)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.6+-violet)](https://www.python.org/)
[![Go](https://img.shields.io/badge/go-1.20+-violet)](https://go.dev/)

**Perfect for servers** • **Powerful for everyone**

---

<div align="left">

## Installation & Setup

### Prerequisites

#### For C++ Collector:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install g++ libcurl4-openssl-dev libjsoncpp-dev

# Arch
sudo pacman -Syu
sudo pacman -S gcc curl jsoncpp

# macOS (requires Homebrew)
brew install curl jsoncpp
```

#### For Python Dashboard:
```bash
# Python 3.8 or higher required
pip install flask requests plotly
```

## Running the System

### Step 1: Start the Go Aggregation Server

```bash
cd backend/go
go run server.go
```


### Step 2: Start the Python Dashboard

```bash
cd backend/python
python dashboard.py
```


### Step 3: Start the C++ Collector

```bash
cd cpp-collector
g++ -std=c++17 -o metrics_collector metrics_collector.cpp -lcurl -ljsoncpp -lpthread
./metrics_collector http://localhost:8080/metrics 5
```

## Configuration

### Alert Thresholds (Python Dashboard)

Edit `dashboard.py` to modify alert thresholds:

```python
ALERT_THRESHOLDS = {
    'cpu': 80.0,      # CPU usage threshold (%)
    'memory': 85.0,   # Memory usage threshold (%)
    'disk': 90.0      # Disk usage threshold (%)
}
```

### Data Retention (Go Server)

Modify retention period in `server.go`:

```go
maxAge: 24 * time.Hour,  // Keep metrics for 24 hours
```

### Collection Interval (C++ Collector)

Pass interval as second argument when running:

```bash
./metrics_collector http://localhost:8080/metrics 10  # Collect every 10 seconds
```

## API Reference

### Go Server Endpoints

#### POST /metrics
Submit new metrics:
```json
{
  "hostname": "server-01",
  "timestamp": 1234567890000000,
  "cpu_usage": 45.2,
  "memory_usage": 62.8,
  "disk_usage": 34.5,
  "disk_io_read": 1024000
}
```

#### GET /query
Query historical metrics:
- `?hostname=server-01` - Filter by hostname
- `?hours=6` - Get last 6 hours of data

Response:
```json
[
  {
    "hostname": "server-01",
    "timestamp": 1234567890000000,
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 34.5,
    "disk_io_read": 1024000
  }
]
```

#### GET /latest
Get the most recent metrics for all hosts:
```json
{
  "server-01": {
    "hostname": "server-01",
    "timestamp": 1234567890000000,
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 34.5,
    "disk_io_read": 1024000
  }
}
```

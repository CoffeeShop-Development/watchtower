package main

import (
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "sync"
    "time"
)

type Metric struct {
    Hostname     string  `json:"hostname"`
    Timestamp    int64   `json:"timestamp"`
    CPUUsage     float64 `json:"cpu_usage"`
    MemoryUsage  float64 `json:"memory_usage"`
    DiskUsage    float64 `json:"disk_usage"`
    DiskIORead   int64   `json:"disk_io_read"`
}

type TimeSeriesDB struct {
    mu      sync.RWMutex
    metrics map[string][]Metric // hostname -> metrics
    maxAge  time.Duration
}

func NewTimeSeriesDB() *TimeSeriesDB {
    db := &TimeSeriesDB{
        metrics: make(map[string][]Metric),
        maxAge:  24 * time.Hour,
    }
    go db.cleanupOldMetrics()
    return db
}

func (db *TimeSeriesDB) Store(metric Metric) {
    db.mu.Lock()
    defer db.mu.Unlock()
    
    hostname := metric.Hostname
    db.metrics[hostname] = append(db.metrics[hostname], metric)
    
    log.Printf("Stored metric for %s: CPU=%.2f%% Memory=%.2f%% Disk=%.2f%%",
        hostname, metric.CPUUsage, metric.MemoryUsage, metric.DiskUsage)
}

func (db *TimeSeriesDB) Query(hostname string, start, end time.Time) []Metric {
    db.mu.RLock()
    defer db.mu.RUnlock()
    
    allMetrics, exists := db.metrics[hostname]
    if !exists {
        return []Metric{}
    }
    
    var result []Metric
    for _, m := range allMetrics {
        t := time.Unix(0, m.Timestamp)
        if t.After(start) && t.Before(end) {
            result = append(result, m)
        }
    }
    
    return result
}

func (db *TimeSeriesDB) QueryAll(start, end time.Time) map[string][]Metric {
    db.mu.RLock()
    defer db.mu.RUnlock()
    
    result := make(map[string][]Metric)
    for hostname, allMetrics := range db.metrics {
        var filtered []Metric
        for _, m := range allMetrics {
            t := time.Unix(0, m.Timestamp)
            if t.After(start) && t.Before(end) {
                filtered = append(filtered, m)
            }
        }
        if len(filtered) > 0 {
            result[hostname] = filtered
        }
    }
    
    return result
}

func (db *TimeSeriesDB) GetLatest(hostname string) *Metric {
    db.mu.RLock()
    defer db.mu.RUnlock()
    
    metrics, exists := db.metrics[hostname]
    if !exists || len(metrics) == 0 {
        return nil
    }
    
    return &metrics[len(metrics)-1]
}

func (db *TimeSeriesDB) GetAllLatest() map[string]Metric {
    db.mu.RLock()
    defer db.mu.RUnlock()
    
    result := make(map[string]Metric)
    for hostname, metrics := range db.metrics {
        if len(metrics) > 0 {
            result[hostname] = metrics[len(metrics)-1]
        }
    }
    
    return result
}

func (db *TimeSeriesDB) cleanupOldMetrics() {
    ticker := time.NewTicker(1 * time.Hour)
    defer ticker.Stop()
    
    for range ticker.C {
        db.mu.Lock()
        cutoff := time.Now().Add(-db.maxAge)
        
        for hostname, metrics := range db.metrics {
            var kept []Metric
            for _, m := range metrics {
                t := time.Unix(0, m.Timestamp)
                if t.After(cutoff) {
                    kept = append(kept, m)
                }
            }
            db.metrics[hostname] = kept
        }
        
        db.mu.Unlock()
        log.Println("Cleaned up old metrics")
    }
}

type Server struct {
    db *TimeSeriesDB
}

func NewServer() *Server {
    return &Server{
        db: NewTimeSeriesDB(),
    }
}

func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
        return
    }
    
    var metric Metric
    if err := json.NewDecoder(r.Body).Decode(&metric); err != nil {
        http.Error(w, "Invalid JSON", http.StatusBadRequest)
        return
    }
    
    s.db.Store(metric)
    
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (s *Server) handleQuery(w http.ResponseWriter, r *http.Request) {
    hostname := r.URL.Query().Get("hostname")
    hours := r.URL.Query().Get("hours")
    
    if hours == "" {
        hours = "1"
    }
    
    var duration time.Duration
    fmt.Sscanf(hours, "%d", &duration)
    duration = duration * time.Hour
    
    end := time.Now()
    start := end.Add(-duration)
    
    w.Header().Set("Content-Type", "application/json")
    w.Header().Set("Access-Control-Allow-Origin", "*")
    
    if hostname != "" {
        metrics := s.db.Query(hostname, start, end)
        json.NewEncoder(w).Encode(metrics)
    } else {
        metrics := s.db.QueryAll(start, end)
        json.NewEncoder(w).Encode(metrics)
    }
}

func (s *Server) handleLatest(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.Header().Set("Access-Control-Allow-Origin", "*")
    
    latest := s.db.GetAllLatest()
    json.NewEncoder(w).Encode(latest)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{
        "status": "healthy",
        "time":   time.Now().Format(time.RFC3339),
    })
}

func main() {
    server := NewServer()
    
    http.HandleFunc("/metrics", server.handleMetrics)
    http.HandleFunc("/query", server.handleQuery)
    http.HandleFunc("/latest", server.handleLatest)
    http.HandleFunc("/health", server.handleHealth)
    
    port := ":8080"
    log.Printf("Starting metrics aggregation server on port %s", port)
    log.Printf("Endpoints:")
    log.Printf("  POST /metrics - Receive metrics")
    log.Printf("  GET  /query?hostname=X&hours=Y - Query metrics")
    log.Printf("  GET  /latest - Get latest metrics for all hosts")
    log.Printf("  GET  /health - Health check")
    
    if err := http.ListenAndServe(port, nil); err != nil {
        log.Fatal(err)
    }
}
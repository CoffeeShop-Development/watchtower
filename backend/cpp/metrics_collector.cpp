#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <chrono>
#include <sys/statvfs.h>
#include <curl/curl.h>
#include <json/json.h>
#include <unistd.h>

class SystemMetrics {
private:
    std::string server_url;
    std::string hostname;

    struct CPUStats {
        long user, nice, system, idle, iowait, irq, softirq;
    };

    CPUStats prev_cpu;

    CPUStats getCPUStats() {
        CPUStats stats = {0};
        std::ifstream file("/proc/stat");
        std::string line;
        
        if (std::getline(file, line)) {
            std::istringstream ss(line);
            std::string cpu;
            ss >> cpu >> stats.user >> stats.nice >> stats.system >> stats.idle 
               >> stats.iowait >> stats.irq >> stats.softirq;
        }
        return stats;
    }

    double calculateCPUUsage() {
        CPUStats curr = getCPUStats();
        
        long prev_idle = prev_cpu.idle + prev_cpu.iowait;
        long curr_idle = curr.idle + curr.iowait;
        
        long prev_total = prev_cpu.user + prev_cpu.nice + prev_cpu.system + 
                         prev_cpu.idle + prev_cpu.iowait + prev_cpu.irq + prev_cpu.softirq;
        long curr_total = curr.user + curr.nice + curr.system + 
                         curr.idle + curr.iowait + curr.irq + curr.softirq;
        
        long total_diff = curr_total - prev_total;
        long idle_diff = curr_idle - prev_idle;
        
        prev_cpu = curr;
        
        if (total_diff == 0) return 0.0;
        return (double)(total_diff - idle_diff) / total_diff * 100.0;
    }

    double getMemoryUsage() {
        std::ifstream file("/proc/meminfo");
        std::string line;
        long total = 0, available = 0;
        
        while (std::getline(file, line)) {
            if (line.find("MemTotal:") == 0) {
                std::istringstream(line.substr(9)) >> total;
            } else if (line.find("MemAvailable:") == 0) {
                std::istringstream(line.substr(13)) >> available;
            }
        }
        
        if (total == 0) return 0.0;
        return (double)(total - available) / total * 100.0;
    }

    double getDiskUsage() {
        struct statvfs stat;
        if (statvfs("/", &stat) != 0) return 0.0;
        
        unsigned long total = stat.f_blocks * stat.f_frsize;
        unsigned long available = stat.f_bavail * stat.f_frsize;
        
        if (total == 0) return 0.0;
        return (double)(total - available) / total * 100.0;
    }

    long getDiskIORead() {
        std::ifstream file("/proc/diskstats");
        std::string line;
        long total_read = 0;
        
        while (std::getline(file, line)) {
            std::istringstream ss(line);
            int major, minor;
            std::string device;
            long reads, read_merges, sectors_read;
            
            ss >> major >> minor >> device >> reads >> read_merges >> sectors_read;
            
            if (device.find("sd") == 0 || device.find("nvme") == 0) {
                total_read += sectors_read * 512; // 512 bytes per sector
            }
        }
        return total_read;
    }

    void sendMetrics(const std::string& json_data) {
        CURL* curl = curl_easy_init();
        if (curl) {
            struct curl_slist* headers = NULL;
            headers = curl_slist_append(headers, "Content-Type: application/json");
            
            curl_easy_setopt(curl, CURLOPT_URL, server_url.c_str());
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_data.c_str());
            curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);
            
            CURLcode res = curl_easy_perform(curl);
            
            if (res != CURLE_OK) {
                std::cerr << "Failed to send metrics: " << curl_easy_strerror(res) << std::endl;
            }
            
            curl_slist_free_all(headers);
            curl_easy_cleanup(curl);
        }
    }

public:
    SystemMetrics(const std::string& url, const std::string& host) 
        : server_url(url), hostname(host) {
        prev_cpu = getCPUStats();
        curl_global_init(CURL_GLOBAL_DEFAULT);
    }

    ~SystemMetrics() {
        curl_global_cleanup();
    }

    void collectAndSend() {
        double cpu = calculateCPUUsage();
        double memory = getMemoryUsage();
        double disk = getDiskUsage();
        long disk_io = getDiskIORead();
        
        // Build JSON
        Json::Value root;
        root["hostname"] = hostname;
        root["timestamp"] = (Json::Int64)std::chrono::system_clock::now().time_since_epoch().count();
        root["cpu_usage"] = cpu;
        root["memory_usage"] = memory;
        root["disk_usage"] = disk;
        root["disk_io_read"] = (Json::Int64)disk_io;
        
        Json::StreamWriterBuilder writer;
        std::string json_data = Json::writeString(writer, root);
        
        std::cout << "Sending metrics: CPU=" << cpu << "% Memory=" << memory 
                  << "% Disk=" << disk << "%" << std::endl;
        
        sendMetrics(json_data);
    }

    void startCollection(int interval_seconds) {
        while (true) {
            collectAndSend();
            std::this_thread::sleep_for(std::chrono::seconds(interval_seconds));
        }
    }
};

int main(int argc, char* argv[]) {
    std::string server_url = "http://localhost:8080/metrics";
    int interval = 5;
    
    if (argc > 1) server_url = argv[1];
    if (argc > 2) interval = std::stoi(argv[2]);
    
    char hostname[256];
    gethostname(hostname, sizeof(hostname));
    
    std::cout << "Starting metrics collector..." << std::endl;
    std::cout << "Hostname: " << hostname << std::endl;
    std::cout << "Server: " << server_url << std::endl;
    std::cout << "Interval: " << interval << " seconds" << std::endl;
    
    SystemMetrics collector(server_url, hostname);
    collector.startCollection(interval);
    
    return 0;
}
"""
Flask server for Monitor-AI.
Collects system metrics via psutil and serves them as JSON.
Server listens only on localhost for security.
"""
import time
import psutil
from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Store previous network counters to calculate speed
_prev_net_counters = psutil.net_io_counters()
_prev_net_time = time.time()


def get_cpu_stats():
    """Return total CPU usage percent and per-core percentages."""
    return {
        "total": psutil.cpu_percent(interval=None),
        "cores": psutil.cpu_percent(interval=None, percpu=True),
    }


def get_ram_stats():
    """Return RAM usage: used MB, total MB, and percent used."""
    mem = psutil.virtual_memory()
    return {
        "used_mb": round(mem.used / 1024 / 1024),
        "total_mb": round(mem.total / 1024 / 1024),
        "percent": mem.percent,
    }


def get_disk_stats():
    """Return disk usage for C: drive: used GB, total GB, and percent used."""
    disk = psutil.disk_usage("C:/")
    return {
        "used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
        "total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
        "percent": disk.percent,
    }


def get_network_stats():
    """Return network speed in Mbps (download and upload) since last call."""
    global _prev_net_counters, _prev_net_time

    current_counters = psutil.net_io_counters()
    current_time = time.time()
    elapsed = current_time - _prev_net_time

    if elapsed <= 0:
        return {"download_mbps": 0.0, "upload_mbps": 0.0}

    bytes_recv = current_counters.bytes_recv - _prev_net_counters.bytes_recv
    bytes_sent = current_counters.bytes_sent - _prev_net_counters.bytes_sent

    _prev_net_counters = current_counters
    _prev_net_time = current_time

    return {
        "download_mbps": round(bytes_recv * 8 / 1024 / 1024 / elapsed, 3),
        "upload_mbps": round(bytes_sent * 8 / 1024 / 1024 / elapsed, 3),
    }


@app.route("/")
def index():
    """Serve the main dashboard page."""
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    """
    Return all system metrics as JSON.
    Called by the browser every second to update the dashboard.
    """
    cpu = get_cpu_stats()
    return jsonify({
        "cpu_total": cpu["total"],
        "cpu_cores": cpu["cores"],
        "ram": get_ram_stats(),
        "disk": get_disk_stats(),
        "network": get_network_stats(),
    })


if __name__ == "__main__":
    # Listen only on localhost — no external connections
    app.run(host="127.0.0.1", port=5000, debug=False)

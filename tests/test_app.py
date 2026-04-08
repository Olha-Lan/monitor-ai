"""Tests for Flask server endpoints and data structure."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app


@pytest.fixture
def client():
    """Create test client for Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_returns_200(client):
    """Home page must load successfully."""
    response = client.get("/")
    assert response.status_code == 200


def test_stats_returns_json(client):
    """API endpoint must return JSON."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.content_type == "application/json"


def test_stats_has_required_keys(client):
    """API response must contain all required metrics."""
    response = client.get("/api/stats")
    data = response.get_json()
    assert "cpu_total" in data
    assert "cpu_cores" in data
    assert "ram" in data
    assert "disk" in data
    assert "network" in data


def test_cpu_total_is_valid_percent(client):
    """CPU total must be a number between 0 and 100."""
    response = client.get("/api/stats")
    data = response.get_json()
    assert isinstance(data["cpu_total"], (int, float))
    assert 0 <= data["cpu_total"] <= 100


def test_cpu_cores_is_list(client):
    """CPU cores must be a list of percentages."""
    response = client.get("/api/stats")
    data = response.get_json()
    assert isinstance(data["cpu_cores"], list)
    assert len(data["cpu_cores"]) > 0


def test_ram_has_required_fields(client):
    """RAM data must contain used, total, and percent fields."""
    response = client.get("/api/stats")
    data = response.get_json()
    ram = data["ram"]
    assert "used_mb" in ram
    assert "total_mb" in ram
    assert "percent" in ram
    assert ram["total_mb"] > 0


def test_disk_has_required_fields(client):
    """Disk data must contain used, total, and percent fields."""
    response = client.get("/api/stats")
    data = response.get_json()
    disk = data["disk"]
    assert "used_gb" in disk
    assert "total_gb" in disk
    assert "percent" in disk


def test_network_has_required_fields(client):
    """Network data must contain upload and download speed fields."""
    response = client.get("/api/stats")
    data = response.get_json()
    net = data["network"]
    assert "download_mbps" in net
    assert "upload_mbps" in net

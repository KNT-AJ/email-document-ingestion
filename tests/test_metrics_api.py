"""Tests for metrics API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from utils.metrics import OCRMetrics, MetricsCollector


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_collector():
    """Create mock metrics collector."""
    collector = MagicMock(spec=MetricsCollector)
    collector.get_ocr_metrics.return_value = {
        "pytesseract": {
            "requests": 10,
            "successful_requests": 8,
            "failed_requests": 2,
            "success_rate": 80.0,
            "latency_p95_ms": 150.0,
            "avg_latency_ms": 120.0,
            "avg_pages_per_request": 5.0,
            "avg_words_per_request": 500.0,
            "avg_cost_cents": 0.25,
            "avg_confidence": 0.85,
            "total_pages_processed": 50,
            "total_words_extracted": 5000,
            "total_cost_cents": 2.5,
        }
    }
    collector.get_system_metrics.return_value = {
        "total_requests": 10,
        "total_successful_requests": 8,
        "total_failed_requests": 2,
        "overall_success_rate": 80.0,
        "total_cost_cents": 2.5,
        "engines_count": 1,
        "last_updated": "2024-01-01T00:00:00Z",
    }
    return collector


class TestMetricsDashboard:
    """Test metrics dashboard endpoint."""

    def test_get_dashboard_success(self, client, mock_collector):
        """Test getting metrics dashboard successfully."""
        with patch('api.routes.metrics.get_metrics_collector', return_value=mock_collector):
            response = client.get("/api/metrics/dashboard")

            assert response.status_code == 200
            data = response.json()

            assert "system" in data
            assert "engines" in data
            assert "summary" in data
            assert data["system"]["total_requests"] == 10
            assert data["engines"]["pytesseract"]["requests"] == 10
            assert data["summary"]["total_engines"] == 1

    def test_get_dashboard_error(self, client):
        """Test getting metrics dashboard with error."""
        with patch('api.routes.metrics.get_metrics_collector', side_effect=Exception("Test error")):
            response = client.get("/api/metrics/dashboard")

            assert response.status_code == 500
            assert "Failed to retrieve metrics" in response.json()["detail"]


class TestEngineMetrics:
    """Test engine-specific metrics endpoints."""

    def test_get_engine_metrics_success(self, client, mock_collector):
        """Test getting metrics for specific engine successfully."""
        with patch('api.routes.metrics.get_metrics_collector', return_value=mock_collector):
            response = client.get("/api/metrics/engines/pytesseract")

            assert response.status_code == 200
            data = response.json()

            assert data["requests"] == 10
            assert data["success_rate"] == 80.0
            assert data["avg_latency_ms"] == 120.0

    def test_get_engine_metrics_not_found(self, client, mock_collector):
        """Test getting metrics for non-existent engine."""
        mock_collector.get_ocr_metrics.return_value = {}  # Empty result

        with patch('api.routes.metrics.get_metrics_collector', return_value=mock_collector):
            response = client.get("/api/metrics/engines/nonexistent")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_get_engine_metrics_error(self, client):
        """Test getting engine metrics with error."""
        with patch('api.routes.metrics.get_metrics_collector', side_effect=Exception("Test error")):
            response = client.get("/api/metrics/engines/pytesseract")

            assert response.status_code == 500
            assert "Failed to retrieve engine metrics" in response.json()["detail"]


class TestAllEnginesMetrics:
    """Test all engines metrics endpoint."""

    def test_get_all_engines_success(self, client, mock_collector):
        """Test getting metrics for all engines successfully."""
        with patch('api.routes.metrics.get_metrics_collector', return_value=mock_collector):
            response = client.get("/api/metrics/engines")

            assert response.status_code == 200
            data = response.json()

            assert "engines" in data
            assert "pytesseract" in data["engines"]
            assert data["engines"]["pytesseract"]["requests"] == 10

    def test_get_all_engines_error(self, client):
        """Test getting all engines metrics with error."""
        with patch('api.routes.metrics.get_metrics_collector', side_effect=Exception("Test error")):
            response = client.get("/api/metrics/engines")

            assert response.status_code == 500
            assert "Failed to retrieve engines metrics" in response.json()["detail"]


class TestResetMetrics:
    """Test metrics reset endpoint."""

    def test_reset_specific_engine(self, client, mock_collector):
        """Test resetting metrics for specific engine."""
        with patch('api.routes.metrics.get_metrics_collector', return_value=mock_collector):
            response = client.post("/api/metrics/reset?engine=pytesseract")

            assert response.status_code == 200
            assert "Metrics reset for engine 'pytesseract'" in response.json()["message"]
            mock_collector.reset_metrics.assert_called_with("pytesseract")

    def test_reset_all_engines(self, client, mock_collector):
        """Test resetting metrics for all engines."""
        with patch('api.routes.metrics.get_metrics_collector', return_value=mock_collector):
            response = client.post("/api/metrics/reset")

            assert response.status_code == 200
            assert "All metrics reset" in response.json()["message"]
            mock_collector.reset_metrics.assert_called_with(None)

    def test_reset_metrics_error(self, client):
        """Test resetting metrics with error."""
        with patch('api.routes.metrics.get_metrics_collector', side_effect=Exception("Test error")):
            response = client.post("/api/metrics/reset")

            assert response.status_code == 500
            assert "Failed to reset metrics" in response.json()["detail"]


class TestSystemMetrics:
    """Test system metrics endpoint."""

    def test_get_system_metrics_success(self, client, mock_collector):
        """Test getting system metrics successfully."""
        with patch('api.routes.metrics.get_metrics_collector', return_value=mock_collector):
            response = client.get("/api/metrics/system")

            assert response.status_code == 200
            data = response.json()

            assert data["total_requests"] == 10
            assert data["overall_success_rate"] == 80.0
            assert data["engines_count"] == 1

    def test_get_system_metrics_error(self, client):
        """Test getting system metrics with error."""
        with patch('api.routes.metrics.get_metrics_collector', side_effect=Exception("Test error")):
            response = client.get("/api/metrics/system")

            assert response.status_code == 500
            assert "Failed to retrieve system metrics" in response.json()["detail"]

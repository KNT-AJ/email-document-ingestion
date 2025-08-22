"""Tests for metrics collection system."""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
import pytest

from utils.metrics import (
    OCRMetrics,
    MetricsCollector,
    MetricsTimer,
    get_metrics_collector,
    record_ocr_metrics,
)


class TestOCRMetrics:
    """Test OCR metrics data structure."""

    def test_init(self):
        """Test OCR metrics initialization."""
        metrics = OCRMetrics()

        assert metrics.requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.latencies_ms == []
        assert metrics.pages_processed == []
        assert metrics.words_extracted == []
        assert metrics.costs == []
        assert metrics.confidence_scores == []

    def test_add_request_success(self):
        """Test adding successful request."""
        metrics = OCRMetrics()
        metrics.add_request(success=True)

        assert metrics.requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 100.0

    def test_add_request_failure(self):
        """Test adding failed request."""
        metrics = OCRMetrics()
        metrics.add_request(success=False)

        assert metrics.requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.success_rate == 0.0

    def test_add_latency(self):
        """Test adding latency measurements."""
        metrics = OCRMetrics()
        metrics.add_latency(100.0)
        metrics.add_latency(200.0)

        assert metrics.latencies_ms == [100.0, 200.0]
        assert metrics.avg_latency == 150.0

    def test_add_pages_processed(self):
        """Test adding pages processed."""
        metrics = OCRMetrics()
        metrics.add_pages_processed(5)
        metrics.add_pages_processed(10)

        assert metrics.pages_processed == [5, 10]
        assert metrics.avg_pages_per_request == 7.5

    def test_add_words_extracted(self):
        """Test adding words extracted."""
        metrics = OCRMetrics()
        metrics.add_words_extracted(100)
        metrics.add_words_extracted(200)

        assert metrics.words_extracted == [100, 200]
        assert metrics.avg_words_per_request == 150.0

    def test_add_cost(self):
        """Test adding cost measurements."""
        metrics = OCRMetrics()
        metrics.add_cost(0.50)
        metrics.add_cost(1.00)

        assert metrics.costs == [0.50, 1.00]
        assert metrics.avg_cost == 0.75

    def test_add_confidence(self):
        """Test adding confidence scores."""
        metrics = OCRMetrics()
        metrics.add_confidence(0.85)
        metrics.add_confidence(0.95)

        assert metrics.confidence_scores == [0.85, 0.95]
        assert metrics.avg_confidence == 0.90

    def test_latency_p95(self):
        """Test 95th percentile latency calculation."""
        metrics = OCRMetrics()
        # Add 100 latency measurements
        latencies = list(range(1, 101))  # 1 to 100 ms
        for latency in latencies:
            metrics.add_latency(float(latency))

        # 95th percentile should be around 95
        assert 94 <= metrics.latency_p95 <= 96

    def test_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = OCRMetrics()
        metrics.add_request(success=True)
        metrics.add_latency(100.0)
        metrics.add_pages_processed(5)
        metrics.add_words_extracted(100)
        metrics.add_cost(0.50)
        metrics.add_confidence(0.85)

        result = metrics.to_dict()

        assert result["requests"] == 1
        assert result["successful_requests"] == 1
        assert result["failed_requests"] == 0
        assert result["success_rate"] == 100.0
        assert result["avg_latency_ms"] == 100.0
        assert result["avg_pages_per_request"] == 5.0
        assert result["avg_words_per_request"] == 100.0
        assert result["avg_cost_cents"] == 0.50
        assert result["avg_confidence"] == 0.85


class TestMetricsCollector:
    """Test metrics collector functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.collector = MetricsCollector(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        # Remove test files
        if os.path.exists(os.path.join(self.temp_dir, "ocr_metrics.json")):
            os.remove(os.path.join(self.temp_dir, "ocr_metrics.json"))
        os.rmdir(self.temp_dir)

    def test_init(self):
        """Test metrics collector initialization."""
        assert isinstance(self.collector.ocr_metrics, dict)
        assert self.collector.storage_path == self.temp_dir

    def test_load_metrics_file_not_exists(self):
        """Test loading metrics when file doesn't exist."""
        # File doesn't exist, should not raise error
        collector = MetricsCollector(self.temp_dir)
        assert len(collector.ocr_metrics) == 0

    def test_load_metrics_file_exists(self):
        """Test loading metrics from existing file."""
        # Create a test metrics file
        test_data = {
            "pytesseract": {
                "requests": 5,
                "successful_requests": 4,
                "failed_requests": 1
            }
        }

        metrics_file = os.path.join(self.temp_dir, "ocr_metrics.json")
        with open(metrics_file, 'w') as f:
            json.dump(test_data, f)

        collector = MetricsCollector(self.temp_dir)

        assert "pytesseract" in collector.ocr_metrics
        assert collector.ocr_metrics["pytesseract"].requests == 5
        assert collector.ocr_metrics["pytesseract"].successful_requests == 4
        assert collector.ocr_metrics["pytesseract"].failed_requests == 1

    def test_save_metrics(self):
        """Test saving metrics to file."""
        self.collector.ocr_metrics["test_engine"] = OCRMetrics()
        self.collector.ocr_metrics["test_engine"].add_request(success=True)

        self.collector._save_metrics()

        metrics_file = os.path.join(self.temp_dir, "ocr_metrics.json")
        assert os.path.exists(metrics_file)

        with open(metrics_file, 'r') as f:
            data = json.load(f)

        assert "test_engine" in data
        assert data["test_engine"]["requests"] == 1

    def test_record_ocr_request(self):
        """Test recording OCR request metrics."""
        with patch.object(self.collector, '_save_metrics') as mock_save:
            self.collector.record_ocr_request(
                engine="pytesseract",
                success=True,
                latency_ms=100.0,
                pages=5,
                words=100,
                cost=0.50,
                confidence=0.85
            )

            # Check that metrics were recorded
            metrics = self.collector.ocr_metrics["pytesseract"]
            assert metrics.requests == 1
            assert metrics.successful_requests == 1
            assert metrics.latencies_ms == [100.0]
            assert metrics.pages_processed == [5]
            assert metrics.words_extracted == [100]
            assert metrics.costs == [0.50]
            assert metrics.confidence_scores == [0.85]

            # Check that save was called (every 10 requests)
            mock_save.assert_not_called()  # Only 1 request, not called yet

    def test_record_ocr_request_save_on_tenth(self):
        """Test that metrics are saved on every 10th request."""
        with patch.object(self.collector, '_save_metrics') as mock_save:
            # Add 9 requests
            for i in range(9):
                self.collector.record_ocr_request("pytesseract", success=True)

            # Save should not have been called yet
            mock_save.assert_not_called()

            # Add 10th request
            self.collector.record_ocr_request("pytesseract", success=True)

            # Now save should be called
            mock_save.assert_called_once()

    def test_get_ocr_metrics_specific_engine(self):
        """Test getting metrics for specific engine."""
        self.collector.ocr_metrics["pytesseract"] = OCRMetrics()
        self.collector.ocr_metrics["pytesseract"].add_request(success=True)

        result = self.collector.get_ocr_metrics("pytesseract")

        assert "pytesseract" in result
        assert result["pytesseract"]["requests"] == 1

    def test_get_ocr_metrics_all_engines(self):
        """Test getting metrics for all engines."""
        self.collector.ocr_metrics["pytesseract"] = OCRMetrics()
        self.collector.ocr_metrics["pytesseract"].add_request(success=True)

        self.collector.ocr_metrics["google_vision"] = OCRMetrics()
        self.collector.ocr_metrics["google_vision"].add_request(success=False)

        result = self.collector.get_ocr_metrics()

        assert "pytesseract" in result
        assert "google_vision" in result
        assert result["pytesseract"]["requests"] == 1
        assert result["google_vision"]["requests"] == 1

    def test_get_system_metrics(self):
        """Test getting system-wide metrics."""
        # Add metrics for different engines
        self.collector.ocr_metrics["pytesseract"] = OCRMetrics()
        self.collector.ocr_metrics["pytesseract"].add_request(success=True)
        self.collector.ocr_metrics["pytesseract"].add_latency(100.0)

        self.collector.ocr_metrics["google_vision"] = OCRMetrics()
        self.collector.ocr_metrics["google_vision"].add_request(success=False)
        self.collector.ocr_metrics["google_vision"].add_cost(1.00)

        system_metrics = self.collector.get_system_metrics()

        assert system_metrics["total_requests"] == 2
        assert system_metrics["total_successful_requests"] == 1
        assert system_metrics["total_failed_requests"] == 1
        assert system_metrics["overall_success_rate"] == 50.0
        assert system_metrics["total_cost_cents"] == 1.00
        assert system_metrics["engines_count"] == 2

    def test_reset_metrics_specific_engine(self):
        """Test resetting metrics for specific engine."""
        self.collector.ocr_metrics["pytesseract"] = OCRMetrics()
        self.collector.ocr_metrics["pytesseract"].add_request(success=True)

        with patch.object(self.collector, '_save_metrics') as mock_save:
            self.collector.reset_metrics("pytesseract")

            assert isinstance(self.collector.ocr_metrics["pytesseract"], OCRMetrics)
            assert self.collector.ocr_metrics["pytesseract"].requests == 0
            mock_save.assert_called_once()

    def test_reset_metrics_all_engines(self):
        """Test resetting metrics for all engines."""
        self.collector.ocr_metrics["pytesseract"] = OCRMetrics()
        self.collector.ocr_metrics["pytesseract"].add_request(success=True)
        self.collector.ocr_metrics["google_vision"] = OCRMetrics()
        self.collector.ocr_metrics["google_vision"].add_request(success=True)

        with patch.object(self.collector, '_save_metrics') as mock_save:
            self.collector.reset_metrics()

            assert len(self.collector.ocr_metrics) == 0
            mock_save.assert_called_once()


class TestMetricsTimer:
    """Test metrics timer context manager."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.collector = MetricsCollector(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        # Remove test files
        if os.path.exists(os.path.join(self.temp_dir, "ocr_metrics.json")):
            os.remove(os.path.join(self.temp_dir, "ocr_metrics.json"))
        os.rmdir(self.temp_dir)

    def test_timer_success(self):
        """Test timer with successful operation."""
        with patch('utils.metrics.get_metrics_collector', return_value=self.collector):
            with MetricsTimer("pytesseract") as timer:
                timer.set_pages(5)
                timer.set_words(100)
                timer.set_cost(0.50)
                timer.set_confidence(0.85)
                # Simulate some work
                import time
                time.sleep(0.01)

        # Check that metrics were recorded
        metrics = self.collector.ocr_metrics["pytesseract"]
        assert metrics.requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.pages_processed == [5]
        assert metrics.words_extracted == [100]
        assert metrics.costs == [0.50]
        assert metrics.confidence_scores == [0.85]
        assert len(metrics.latencies_ms) == 1
        assert metrics.latencies_ms[0] > 0  # Should have some latency

    def test_timer_failure(self):
        """Test timer with failed operation."""
        with patch('utils.metrics.get_metrics_collector', return_value=self.collector):
            with pytest.raises(ValueError):
                with MetricsTimer("pytesseract") as timer:
                    timer.set_pages(5)
                    raise ValueError("Test error")

        # Check that failure was recorded
        metrics = self.collector.ocr_metrics["pytesseract"]
        assert metrics.requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.pages_processed == [5]  # Should still record pages even on failure
        assert len(metrics.latencies_ms) == 1  # Should record latency even on failure


class TestMetricsFunctions:
    """Test standalone metrics functions."""

    def test_get_metrics_collector(self):
        """Test getting global metrics collector."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        # Should return the same instance
        assert collector1 is collector2

    def test_record_ocr_metrics_function(self):
        """Test record_ocr_metrics function."""
        temp_dir = tempfile.mkdtemp()
        collector = MetricsCollector(temp_dir)

        with patch('utils.metrics.get_metrics_collector', return_value=collector):
            record_ocr_metrics(
                engine="pytesseract",
                success=True,
                latency_ms=100.0,
                pages=5,
                words=100,
                cost=0.50,
                confidence=0.85
            )

            metrics = collector.ocr_metrics["pytesseract"]
            assert metrics.requests == 1
            assert metrics.successful_requests == 1
            assert metrics.latencies_ms == [100.0]
            assert metrics.pages_processed == [5]
            assert metrics.words_extracted == [100]
            assert metrics.costs == [0.50]
            assert metrics.confidence_scores == [0.85]

        # Cleanup
        if os.path.exists(os.path.join(temp_dir, "ocr_metrics.json")):
            os.remove(os.path.join(temp_dir, "ocr_metrics.json"))
        os.rmdir(temp_dir)

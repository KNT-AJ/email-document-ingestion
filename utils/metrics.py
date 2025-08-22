"""Metrics collection and reporting system for the application."""

import time
import statistics
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from config import get_settings


@dataclass
class OCRMetrics:
    """Container for OCR engine metrics."""

    # Request metrics
    requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Performance metrics
    latencies_ms: List[float] = field(default_factory=list)
    pages_processed: List[int] = field(default_factory=list)
    words_extracted: List[int] = field(default_factory=list)

    # Cost metrics (if available)
    costs: List[float] = field(default_factory=list)

    # Confidence metrics
    confidence_scores: List[float] = field(default_factory=list)

    def add_request(self, success: bool = True) -> None:
        """Add a request to the metrics."""
        self.requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def add_latency(self, latency_ms: float) -> None:
        """Add a latency measurement."""
        self.latencies_ms.append(latency_ms)

    def add_pages_processed(self, pages: int) -> None:
        """Add pages processed count."""
        self.pages_processed.append(pages)

    def add_words_extracted(self, words: int) -> None:
        """Add words extracted count."""
        self.words_extracted.append(words)

    def add_cost(self, cost: float) -> None:
        """Add cost measurement."""
        self.costs.append(cost)

    def add_confidence(self, confidence: float) -> None:
        """Add confidence score."""
        self.confidence_scores.append(confidence)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.requests == 0:
            return 0.0
        return (self.successful_requests / self.requests) * 100

    @property
    def latency_p95(self) -> float:
        """Calculate 95th percentile latency."""
        if not self.latencies_ms:
            return 0.0
        return statistics.quantiles(self.latencies_ms, n=100)[94] if len(self.latencies_ms) >= 20 else statistics.mean(self.latencies_ms)

    @property
    def avg_latency(self) -> float:
        """Calculate average latency."""
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def avg_pages_per_request(self) -> float:
        """Calculate average pages processed per request."""
        return statistics.mean(self.pages_processed) if self.pages_processed else 0.0

    @property
    def avg_words_per_request(self) -> float:
        """Calculate average words extracted per request."""
        return statistics.mean(self.words_extracted) if self.words_extracted else 0.0

    @property
    def avg_cost(self) -> float:
        """Calculate average cost per request."""
        return statistics.mean(self.costs) if self.costs else 0.0

    @property
    def avg_confidence(self) -> float:
        """Calculate average confidence score."""
        return statistics.mean(self.confidence_scores) if self.confidence_scores else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format."""
        return {
            "requests": self.requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(self.success_rate, 2),
            "latency_p95_ms": round(self.latency_p95, 2),
            "avg_latency_ms": round(self.avg_latency, 2),
            "avg_pages_per_request": round(self.avg_pages_per_request, 2),
            "avg_words_per_request": round(self.avg_words_per_request, 2),
            "avg_cost_cents": round(self.avg_cost, 4),
            "avg_confidence": round(self.avg_confidence, 2),
            "total_pages_processed": sum(self.pages_processed),
            "total_words_extracted": sum(self.words_extracted),
            "total_cost_cents": round(sum(self.costs), 4),
        }


class MetricsCollector:
    """Central metrics collection system."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize the metrics collector.

        Args:
            storage_path: Path to store metrics data
        """
        self.settings = get_settings()
        self.storage_path = storage_path or os.path.join(
            self.settings.LOCAL_STORAGE_PATH, "metrics"
        )
        os.makedirs(self.storage_path, exist_ok=True)

        # In-memory metrics storage
        self.ocr_metrics: Dict[str, OCRMetrics] = defaultdict(OCRMetrics)

        # Load existing metrics if available
        self._load_metrics()

    def _load_metrics(self) -> None:
        """Load metrics from persistent storage."""
        metrics_file = os.path.join(self.storage_path, "ocr_metrics.json")
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                    for engine, metrics_data in data.items():
                        metrics = OCRMetrics()
                        # Load the data (simplified - in production you'd want more robust loading)
                        metrics.requests = metrics_data.get('requests', 0)
                        metrics.successful_requests = metrics_data.get('successful_requests', 0)
                        metrics.failed_requests = metrics_data.get('failed_requests', 0)
                        self.ocr_metrics[engine] = metrics
            except Exception as e:
                print(f"Warning: Could not load metrics from {metrics_file}: {e}")

    def _save_metrics(self) -> None:
        """Save metrics to persistent storage."""
        metrics_file = os.path.join(self.storage_path, "ocr_metrics.json")
        try:
            data = {engine: metrics.to_dict() for engine, metrics in self.ocr_metrics.items()}
            with open(metrics_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save metrics to {metrics_file}: {e}")

    def record_ocr_request(
        self,
        engine: str,
        success: bool = True,
        latency_ms: Optional[float] = None,
        pages: Optional[int] = None,
        words: Optional[int] = None,
        cost: Optional[float] = None,
        confidence: Optional[float] = None
    ) -> None:
        """Record an OCR request with its metrics.

        Args:
            engine: OCR engine name
            success: Whether the request was successful
            latency_ms: Request latency in milliseconds
            pages: Number of pages processed
            words: Number of words extracted
            cost: Cost in cents
            confidence: Confidence score (0-100)
        """
        metrics = self.ocr_metrics[engine]
        metrics.add_request(success=success)

        if latency_ms is not None:
            metrics.add_latency(latency_ms)
        if pages is not None:
            metrics.add_pages_processed(pages)
        if words is not None:
            metrics.add_words_extracted(words)
        if cost is not None:
            metrics.add_cost(cost)
        if confidence is not None:
            metrics.add_confidence(confidence)

        # Save metrics periodically (every 10 requests)
        if metrics.requests % 10 == 0:
            self._save_metrics()

    def get_ocr_metrics(self, engine: Optional[str] = None) -> Dict[str, Any]:
        """Get OCR metrics for one or all engines.

        Args:
            engine: Specific engine name, or None for all engines

        Returns:
            Dictionary containing metrics data
        """
        if engine:
            metrics = self.ocr_metrics.get(engine, OCRMetrics())
            return {engine: metrics.to_dict()}

        return {engine: metrics.to_dict() for engine, metrics in self.ocr_metrics.items()}

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics."""
        total_requests = sum(m.requests for m in self.ocr_metrics.values())
        total_successful = sum(m.successful_requests for m in self.ocr_metrics.values())
        total_failed = sum(m.failed_requests for m in self.ocr_metrics.values())
        total_cost = sum(sum(m.costs) for m in self.ocr_metrics.values())

        return {
            "total_requests": total_requests,
            "total_successful_requests": total_successful,
            "total_failed_requests": total_failed,
            "overall_success_rate": round((total_successful / total_requests * 100) if total_requests > 0 else 0, 2),
            "total_cost_cents": round(total_cost, 4),
            "engines_count": len(self.ocr_metrics),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def reset_metrics(self, engine: Optional[str] = None) -> None:
        """Reset metrics for a specific engine or all engines.

        Args:
            engine: Specific engine name, or None to reset all
        """
        if engine:
            self.ocr_metrics[engine] = OCRMetrics()
        else:
            self.ocr_metrics.clear()
        self._save_metrics()

    def cleanup_old_data(self, days: int = 30) -> None:
        """Clean up old metrics data.

        Args:
            days: Remove data older than this many days
        """
        # For now, this is a placeholder. In a production system,
        # you might want to implement time-series data with proper cleanup
        pass


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_ocr_metrics(
    engine: str,
    success: bool = True,
    latency_ms: Optional[float] = None,
    pages: Optional[int] = None,
    words: Optional[int] = None,
    cost: Optional[float] = None,
    confidence: Optional[float] = None
) -> None:
    """Helper function to record OCR metrics.

    Args:
        engine: OCR engine name
        success: Whether the request was successful
        latency_ms: Request latency in milliseconds
        pages: Number of pages processed
        words: Number of words extracted
        cost: Cost in cents
        confidence: Confidence score (0-100)
    """
    collector = get_metrics_collector()
    collector.record_ocr_request(
        engine=engine,
        success=success,
        latency_ms=latency_ms,
        pages=pages,
        words=words,
        cost=cost,
        confidence=confidence
    )


class MetricsTimer:
    """Context manager for timing operations and recording metrics."""

    def __init__(self, engine: str):
        """Initialize timer for an OCR engine.

        Args:
            engine: OCR engine name
        """
        self.engine = engine
        self.start_time: Optional[float] = None
        self.pages: Optional[int] = None
        self.words: Optional[int] = None
        self.cost: Optional[float] = None
        self.confidence: Optional[float] = None
        self.success: bool = True

    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and record metrics."""
        if self.start_time is not None:
            latency_ms = (time.time() - self.start_time) * 1000
            self.success = exc_type is None

            record_ocr_metrics(
                engine=self.engine,
                success=self.success,
                latency_ms=latency_ms,
                pages=self.pages,
                words=self.words,
                cost=self.cost,
                confidence=self.confidence
            )

    def set_pages(self, pages: int) -> 'MetricsTimer':
        """Set number of pages processed."""
        self.pages = pages
        return self

    def set_words(self, words: int) -> 'MetricsTimer':
        """Set number of words extracted."""
        self.words = words
        return self

    def set_cost(self, cost: float) -> 'MetricsTimer':
        """Set cost in cents."""
        self.cost = cost
        return self

    def set_confidence(self, confidence: float) -> 'MetricsTimer':
        """Set confidence score."""
        self.confidence = confidence
        return self

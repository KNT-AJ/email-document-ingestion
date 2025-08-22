"""Centralized error logging and monitoring service.

This service provides centralized error logging functionality that integrates with
the ApplicationError system, providing structured logging, correlation IDs,
and monitoring integrations.
"""

import uuid
import logging
import json
from typing import Dict, Any, Optional, List
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from models.exceptions import ApplicationError, ErrorCategory, ErrorSeverity
from utils.logging import get_logger

# Context variable for correlation ID tracking
correlation_id_context: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


@dataclass
class ErrorLogEntry:
    """Structured error log entry."""
    correlation_id: Optional[str]
    timestamp: datetime
    error_class: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    context: Dict[str, Any]
    retryable: bool
    retry_count: int
    error_chain: List[Dict[str, Any]]
    stack_trace: Optional[str]
    module: Optional[str]
    function: Optional[str]
    line_number: Optional[int]
    process_info: Dict[str, Any]


class ErrorLoggingService:
    """Centralized service for error logging and monitoring."""

    def __init__(self, monitoring_service: Optional['MonitoringService'] = None):
        self.logger = get_logger("error.logging")
        self.monitoring_service = monitoring_service
        self._correlation_id_stack: List[str] = []

    def log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Log an error with full context and monitoring.

        Args:
            error: The exception to log
            context: Additional context for the error
            correlation_id: Correlation ID for tracking (auto-generated if not provided)
            **kwargs: Additional key-value pairs for context

        Returns:
            Correlation ID used for the error log
        """
        # Use provided correlation ID or generate a new one
        if correlation_id is None:
            # Check if error already has a correlation ID
            if isinstance(error, ApplicationError) and error.correlation_id:
                correlation_id = error.correlation_id
            else:
                correlation_id = self.get_current_correlation_id() or str(uuid.uuid4())

        # Set correlation ID in context for the duration of this operation
        token = self.set_correlation_id(correlation_id)
        try:
            # Create structured log entry
            log_entry = self._create_log_entry(error, context or {}, correlation_id, **kwargs)

            # Convert to dict for logging
            log_data = asdict(log_entry)
            log_data['timestamp'] = log_data['timestamp'].isoformat()
            log_data['category'] = log_data['category'].value
            log_data['severity'] = log_data['severity'].value

            # Log based on severity
            log_method = self._get_log_method(log_entry.severity)
            log_method(
                f"Error logged: {log_entry.error_class}",
                extra=log_data,
                exc_info=error
            )

            # Send to monitoring service if available
            if self.monitoring_service:
                self.monitoring_service.send_error(log_entry)

            return correlation_id

        finally:
            # Restore previous correlation ID
            self.reset_correlation_id(token)

    def log_application_error(
        self,
        error: ApplicationError,
        additional_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Log an ApplicationError with enhanced context.

        Args:
            error: The ApplicationError to log
            additional_context: Additional context beyond what's in the error
            **kwargs: Additional key-value pairs

        Returns:
            Correlation ID used for the error log
        """
        # Merge all contexts
        merged_context = {}
        if error.context:
            merged_context.update(error.context)
        if additional_context:
            merged_context.update(additional_context)
        if kwargs:
            merged_context.update(kwargs)

        # Set timestamp if not already set
        if error.timestamp is None:
            error.timestamp = datetime.now(timezone.utc)

        return self.log_error(error, merged_context)

    def _create_log_entry(
        self,
        error: Exception,
        context: Dict[str, Any],
        correlation_id: str,
        **kwargs
    ) -> ErrorLogEntry:
        """Create a structured log entry from an exception."""
        # Extract stack frame information
        frame_info = self._extract_frame_info()

        # Build process info
        import os
        import platform
        process_info = {
            "process_id": os.getpid(),
            "thread_id": self._get_thread_id(),
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version()
        }

        # Handle ApplicationError vs generic Exception
        if isinstance(error, ApplicationError):
            # Use the merged context passed to this method
            return ErrorLogEntry(
                correlation_id=correlation_id,
                timestamp=error.timestamp or datetime.now(timezone.utc),
                error_class=error.__class__.__name__,
                message=error.message,
                category=error.category,
                severity=error.severity,
                context=context,  # Use merged context
                retryable=error.retryable,
                retry_count=error.retry_count,
                error_chain=error.error_chain,
                stack_trace=self._format_stack_trace(error),
                module=frame_info.get("module"),
                function=frame_info.get("function"),
                line_number=frame_info.get("line_number"),
                process_info=process_info
            )
        else:
            # Generic exception handling
            return ErrorLogEntry(
                correlation_id=correlation_id,
                timestamp=datetime.now(timezone.utc),
                error_class=error.__class__.__name__,
                message=str(error),
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.ERROR,
                context=context,
                retryable=False,
                retry_count=0,
                error_chain=[{
                    "class": error.__class__.__name__,
                    "message": str(error),
                    "category": "system",
                    "severity": "error",
                    "context": context,
                    "retryable": False,
                    "retry_count": 0
                }],
                stack_trace=self._format_stack_trace(error),
                module=frame_info.get("module"),
                function=frame_info.get("function"),
                line_number=frame_info.get("line_number"),
                process_info=process_info
            )

    def _extract_frame_info(self) -> Dict[str, Any]:
        """Extract information about the current stack frame."""
        import inspect

        frame = inspect.currentframe()
        try:
            # Go up the stack to find the calling frame (skip this method and log_error)
            caller_frame = frame.f_back.f_back
            if caller_frame:
                return {
                    "module": caller_frame.f_globals.get("__name__", "unknown"),
                    "function": caller_frame.f_code.co_name,
                    "line_number": caller_frame.f_lineno,
                    "file": caller_frame.f_code.co_filename
                }
        finally:
            del frame

        return {}

    def _format_stack_trace(self, error: Exception) -> Optional[str]:
        """Format exception stack trace as string."""
        import traceback
        return ''.join(traceback.format_exception(type(error), error, error.__traceback__))

    def _get_thread_id(self) -> int:
        """Get current thread identifier."""
        import threading
        return threading.get_ident()

    def _get_log_method(self, severity: ErrorSeverity):
        """Get appropriate logging method based on severity."""
        severity_map = {
            ErrorSeverity.INFO: self.logger.info,
            ErrorSeverity.WARNING: self.logger.warning,
            ErrorSeverity.ERROR: self.logger.error,
            ErrorSeverity.CRITICAL: self.logger.critical
        }
        return severity_map.get(severity, self.logger.error)

    def get_current_correlation_id(self) -> Optional[str]:
        """Get the current correlation ID from context."""
        return correlation_id_context.get()

    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID in context and return token for restoration."""
        return correlation_id_context.set(correlation_id)

    def reset_correlation_id(self, token):
        """Reset correlation ID using token."""
        correlation_id_context.reset(token)

    def create_child_correlation_id(self, parent_id: Optional[str] = None) -> str:
        """Create a child correlation ID for sub-operations."""
        if parent_id is None:
            parent_id = self.get_current_correlation_id()

        base_id = parent_id or str(uuid.uuid4())
        child_id = f"{base_id}.{str(uuid.uuid4())[:8]}"
        return child_id

    def log_error_summary(
        self,
        error: Exception,
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log a concise error summary for monitoring dashboards.

        Args:
            error: The exception that occurred
            operation: Name of the operation that failed
            context: Additional context

        Returns:
            Correlation ID used for the log
        """
        correlation_id = self.get_current_correlation_id() or str(uuid.uuid4())

        summary_data = {
            "operation": operation,
            "error_class": error.__class__.__name__,
            "error_message": str(error),
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(context or {})
        }

        self.logger.error(f"Error summary for {operation}", extra=summary_data)
        return correlation_id

    def log_retry_attempt(
        self,
        operation: str,
        attempt: int,
        max_attempts: int,
        error: Exception,
        delay_seconds: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log retry attempt information.

        Args:
            operation: Name of the operation being retried
            attempt: Current attempt number (1-based)
            max_attempts: Maximum number of attempts
            error: The error that caused the retry
            delay_seconds: Delay before next attempt
            correlation_id: Correlation ID for tracking
        """
        correlation_id = correlation_id or self.get_current_correlation_id() or str(uuid.uuid4())

        retry_data = {
            "operation": operation,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "delay_seconds": delay_seconds,
            "error_class": error.__class__.__name__,
            "error_message": str(error),
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.logger.warning(f"Retry attempt {attempt}/{max_attempts} for {operation}", extra=retry_data)

    def log_dead_letter_queue_entry(
        self,
        operation: str,
        payload: Dict[str, Any],
        error: Exception,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log entry being sent to dead letter queue.

        Args:
            operation: Name of the operation that failed permanently
            payload: Original payload that failed to process
            error: The final error that caused the failure
            correlation_id: Correlation ID for tracking
        """
        correlation_id = correlation_id or self.get_current_correlation_id() or str(uuid.uuid4())

        dlq_data = {
            "operation": operation,
            "error_class": error.__class__.__name__,
            "error_message": str(error),
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload_size": len(json.dumps(payload, default=str)) if payload else 0
        }

        self.logger.error(f"Dead letter queue entry for {operation}", extra=dlq_data)


class MonitoringService:
    """Base class for monitoring service integrations."""

    def send_error(self, log_entry: ErrorLogEntry) -> None:
        """Send error to monitoring service.

        Args:
            log_entry: Structured error log entry
        """
        raise NotImplementedError("Subclasses must implement send_error")


class SentryMonitoringService(MonitoringService):
    """Sentry integration for error monitoring."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Sentry client."""
        try:
            import sentry_sdk
            if self.dsn:
                sentry_sdk.init(dsn=self.dsn, traces_sample_rate=1.0)
                self._client = sentry_sdk
        except ImportError:
            logging.warning("Sentry SDK not available. Install with: pip install sentry-sdk")

    def send_error(self, log_entry: ErrorLogEntry) -> None:
        """Send error to Sentry."""
        if not self._client:
            return

        try:
            # Create a synthetic exception for Sentry
            error = Exception(log_entry.message)
            error.__class__.__name__ = log_entry.error_class

            # Add context as tags and extra data
            with self._client.configure_scope() as scope:
                scope.set_tag("error_category", log_entry.category.value)
                scope.set_tag("error_severity", log_entry.severity.value)
                scope.set_tag("correlation_id", log_entry.correlation_id or "unknown")
                scope.set_tag("retryable", str(log_entry.retryable))
                scope.set_extra("retry_count", log_entry.retry_count)
                scope.set_extra("context", log_entry.context)
                scope.set_extra("process_info", log_entry.process_info)

                # Capture the exception
                self._client.capture_exception(error)

        except Exception as e:
            logging.error(f"Failed to send error to Sentry: {e}")


class ELKMonitoringService(MonitoringService):
    """ELK Stack integration for error monitoring."""

    def __init__(self, elasticsearch_url: Optional[str] = None, index_prefix: str = "error-logs"):
        self.elasticsearch_url = elasticsearch_url
        self.index_prefix = index_prefix
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Elasticsearch client."""
        try:
            from elasticsearch import Elasticsearch
            if self.elasticsearch_url:
                self._client = Elasticsearch(self.elasticsearch_url)
        except ImportError:
            logging.warning("Elasticsearch client not available. Install with: pip install elasticsearch")

    def send_error(self, log_entry: ErrorLogEntry) -> None:
        """Send error to Elasticsearch."""
        if not self._client:
            return

        try:
            # Create index name with date
            index_name = f"{self.index_prefix}-{log_entry.timestamp.strftime('%Y-%m-%d')}"

            # Prepare document
            document = asdict(log_entry)
            document['timestamp'] = document['timestamp'].isoformat()
            document['category'] = document['category'].value
            document['severity'] = document['severity'].value

            # Index the document
            self._client.index(index=index_name, document=document)

        except Exception as e:
            logging.error(f"Failed to send error to Elasticsearch: {e}")


# Global error logging service instance
_error_logging_service: Optional[ErrorLoggingService] = None


def get_error_logging_service() -> ErrorLoggingService:
    """Get the global error logging service instance."""
    global _error_logging_service

    if _error_logging_service is None:
        # Initialize with available monitoring services
        monitoring_services = []

        # Try to initialize Sentry if DSN is available
        try:
            import os
            sentry_dsn = os.getenv("SENTRY_DSN")
            if sentry_dsn:
                monitoring_services.append(SentryMonitoringService(sentry_dsn))
        except ImportError:
            pass

        # Try to initialize ELK if URL is available
        try:
            import os
            elasticsearch_url = os.getenv("ELASTICSEARCH_URL")
            if elasticsearch_url:
                monitoring_services.append(ELKMonitoringService(elasticsearch_url))
        except ImportError:
            pass

        # Use the first available monitoring service
        monitoring_service = monitoring_services[0] if monitoring_services else None

        _error_logging_service = ErrorLoggingService(monitoring_service)

    return _error_logging_service


def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """Convenience function to log an error using the global service."""
    return get_error_logging_service().log_error(error, context, **kwargs)


def log_application_error(
    error: ApplicationError,
    additional_context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """Convenience function to log an ApplicationError using the global service."""
    return get_error_logging_service().log_application_error(error, additional_context, **kwargs)


def get_current_correlation_id() -> Optional[str]:
    """Get the current correlation ID from the global service."""
    return get_error_logging_service().get_current_correlation_id()


def create_correlation_context(correlation_id: Optional[str] = None):
    """Context manager for setting correlation ID."""
    service = get_error_logging_service()

    class CorrelationContext:
        def __init__(self, service, correlation_id):
            self.service = service
            self.correlation_id = correlation_id or str(uuid.uuid4())
            self.token = None

        def __enter__(self):
            self.token = self.service.set_correlation_id(self.correlation_id)
            return self.correlation_id

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.token:
                self.service.reset_correlation_id(self.token)

    return CorrelationContext(service, correlation_id)

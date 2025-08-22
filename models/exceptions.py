"""Comprehensive error handling system for the data ingestion system.

This module implements the error taxonomy specified in the PRD section 13:
- INGEST/EMAIL: Gmail API related errors
- STORAGE: Blob storage related errors
- OCR: OCR engine related errors

Each error type includes severity levels, context collection, and proper serialization
for logging and API responses.
"""

import json
import traceback
from typing import Any, Dict, Optional, List, Union
from enum import Enum


class ErrorSeverity(Enum):
    """Severity levels for errors as specified in the error taxonomy."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories as defined in PRD section 13."""
    INGEST_EMAIL = "ingest_email"
    STORAGE = "storage"
    OCR = "ocr"
    SYSTEM = "system"


class ApplicationError(Exception):
    """Base error class for all application errors.

    Provides structured error handling with severity levels, context collection,
    and proper serialization for logging and API responses.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = False,
        retry_count: int = 0
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.cause = cause
        self.correlation_id = correlation_id
        self.retryable = retryable
        self.retry_count = retry_count
        self.timestamp = None  # Set when logged

        # Build full error chain
        self.error_chain = self._build_error_chain()

        # Call parent constructor with message
        super().__init__(self.message)

    def _build_error_chain(self) -> List[Dict[str, Any]]:
        """Build a chain of error information including nested causes."""
        chain = []
        current_error = self

        while current_error:
            error_info = {
                "class": current_error.__class__.__name__,
                "message": str(current_error),
                "category": str(current_error.category.value) if hasattr(current_error, 'category') else "unknown",
                "severity": str(current_error.severity.value) if hasattr(current_error, 'severity') else "unknown",
                "context": getattr(current_error, 'context', {}),
                "retryable": getattr(current_error, 'retryable', False),
                "retry_count": getattr(current_error, 'retry_count', 0)
            }
            chain.append(error_info)

            # Get next error in chain
            current_error = getattr(current_error, 'cause', None)
            if current_error and not isinstance(current_error, Exception):
                break

        return chain

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error to dictionary for logging and API responses."""
        return {
            "error_class": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context,
            "correlation_id": self.correlation_id,
            "retryable": self.retryable,
            "retry_count": self.retry_count,
            "error_chain": self.error_chain,
            "timestamp": self.timestamp
        }

    def to_json(self) -> str:
        """Serialize error to JSON string."""
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)

    def __str__(self) -> str:
        """String representation of the error."""
        parts = [
            f"[{self.category.value.upper()}] {self.severity.value.upper()}: {self.message}"
        ]

        if self.context:
            parts.append(f"Context: {json.dumps(self.context, default=str)}")

        if self.correlation_id:
            parts.append(f"Correlation ID: {self.correlation_id}")

        if self.retry_count > 0:
            parts.append(f"Retry count: {self.retry_count}")

        return " | ".join(parts)


# INGEST/EMAIL Error Classes
class IngestEmailError(ApplicationError):
    """Base class for email ingestion related errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = False,
        retry_count: int = 0
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.INGEST_EMAIL,
            severity=severity,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable,
            retry_count=retry_count
        )


class GmailAuthError(IngestEmailError):
    """Gmail authentication errors (401/403)."""

    def __init__(
        self,
        message: str = "Gmail authentication failed",
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=True  # Token refresh may succeed
        )


class GmailAPIError(IngestEmailError):
    """General Gmail API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        if status_code:
            context["status_code"] = status_code

        retryable = status_code in [429, 500, 502, 503, 504] if status_code else False

        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable
        )


class GmailThreadNotFoundError(IngestEmailError):
    """Thread not found (404) - not retryable as per PRD."""

    def __init__(
        self,
        thread_id: str,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        context["thread_id"] = thread_id

        super().__init__(
            message=f"Gmail thread not found: {thread_id}",
            severity=ErrorSeverity.WARNING,
            context=context,
            correlation_id=correlation_id,
            retryable=False  # As per PRD: 404 thread → skip
        )


class EmailParsingError(IngestEmailError):
    """Malformed MIME or email parsing errors."""

    def __init__(
        self,
        message: str = "Failed to parse email",
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=False  # As per PRD: malformed MIME → quarantine
        )


# STORAGE Error Classes
class StorageError(ApplicationError):
    """Base class for storage related errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = False,
        retry_count: int = 0
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.STORAGE,
            severity=severity,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable,
            retry_count=retry_count
        )


class BlobStorageError(StorageError):
    """General blob storage errors."""

    def __init__(
        self,
        message: str,
        blob_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = True  # Storage errors are generally retryable
    ):
        context = context or {}
        if blob_path:
            context["blob_path"] = blob_path

        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable
        )


class BlobNotFoundError(StorageError):
    """Blob not found in storage."""

    def __init__(
        self,
        blob_path: str,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        context["blob_path"] = blob_path

        super().__init__(
            message=f"Blob not found: {blob_path}",
            severity=ErrorSeverity.WARNING,
            context=context,
            correlation_id=correlation_id,
            retryable=False
        )


class StorageConnectionError(StorageError):
    """Storage connection issues."""

    def __init__(
        self,
        message: str = "Storage connection failed",
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=True
        )


class StorageTimeoutError(StorageError):
    """Storage operation timeout."""

    def __init__(
        self,
        operation: str = "storage operation",
        timeout_seconds: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        if timeout_seconds:
            context["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=f"Storage operation timed out: {operation}",
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=True
        )


class ChecksumMismatchError(StorageError):
    """Checksum mismatch between local and stored blob."""

    def __init__(
        self,
        blob_path: str,
        expected_hash: str,
        actual_hash: str,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        context.update({
            "blob_path": blob_path,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash
        })

        super().__init__(
            message=f"Checksum mismatch for {blob_path}",
            severity=ErrorSeverity.ERROR,
            context=context,
            correlation_id=correlation_id,
            retryable=True  # As per PRD: checksum mismatch → re-download
        )


# OCR Error Classes
class OcrError(ApplicationError):
    """Base class for OCR related errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = False,
        retry_count: int = 0
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.OCR,
            severity=severity,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable,
            retry_count=retry_count
        )


class OcrEngineError(OcrError):
    """General OCR engine errors."""

    def __init__(
        self,
        message: str,
        engine: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = False
    ):
        context = context or {}
        context["engine"] = engine
        if error_code:
            context["error_code"] = error_code

        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable
        )


class OcrEngineUnavailableError(OcrEngineError):
    """OCR engine is unavailable."""

    def __init__(
        self,
        engine: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=f"OCR engine unavailable: {engine}",
            engine=engine,
            error_code="engine_unavailable",
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=True
        )


class OcrTimeoutError(OcrEngineError):
    """OCR operation timed out."""

    def __init__(
        self,
        engine: str,
        timeout_seconds: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        if timeout_seconds:
            context["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=f"OCR timeout for engine: {engine}",
            engine=engine,
            error_code="timeout",
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=True
        )


class OcrQuotaExceededError(OcrEngineError):
    """OCR engine quota exceeded."""

    def __init__(
        self,
        engine: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=f"OCR quota exceeded for engine: {engine}",
            engine=engine,
            error_code="quota_exceeded",
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=False  # Quota exceeded is generally not retryable immediately
        )


class OcrUnsupportedMimeError(OcrEngineError):
    """Unsupported MIME type for OCR processing."""

    def __init__(
        self,
        engine: str,
        mime_type: str,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        context["mime_type"] = mime_type

        super().__init__(
            message=f"Unsupported MIME type '{mime_type}' for OCR engine: {engine}",
            engine=engine,
            error_code="unsupported_mime",
            context=context,
            correlation_id=correlation_id,
            retryable=False
        )


class OcrImageQualityError(OcrEngineError):
    """Image quality too low for OCR processing."""

    def __init__(
        self,
        engine: str,
        quality_score: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        if quality_score is not None:
            context["quality_score"] = quality_score

        super().__init__(
            message=f"Image quality too low for OCR engine: {engine}",
            engine=engine,
            error_code="image_quality_low",
            context=context,
            correlation_id=correlation_id,
            retryable=False
        )


# SYSTEM Error Classes
class SystemError(ApplicationError):
    """Base class for system-level errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = False,
        retry_count: int = 0
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM,
            severity=severity,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable,
            retry_count=retry_count
        )


class ConfigurationError(SystemError):
    """Configuration related errors."""

    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        context = context or {}
        if config_key:
            context["config_key"] = config_key

        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            correlation_id=correlation_id,
            retryable=False
        )


class DatabaseError(SystemError):
    """Database related errors."""

    def __init__(
        self,
        message: str = "Database error",
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        retryable: bool = True  # Database errors are often retryable
    ):
        context = context or {}
        if operation:
            context["operation"] = operation

        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=cause,
            correlation_id=correlation_id,
            retryable=retryable
        )


# Utility functions for error handling
def wrap_error(
    original_error: Exception,
    message: str,
    category: ErrorCategory,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    retryable: Optional[bool] = None,
    retry_count: int = 0
) -> ApplicationError:
    """Wrap an existing exception in an ApplicationError while preserving the original error chain."""

    # Determine retryable based on original error if not specified
    if retryable is None:
        retryable = isinstance(original_error, (ConnectionError, TimeoutError))

    # Create appropriate error class based on category
    error_classes = {
        ErrorCategory.INGEST_EMAIL: IngestEmailError,
        ErrorCategory.STORAGE: StorageError,
        ErrorCategory.OCR: OcrError,
        ErrorCategory.SYSTEM: SystemError
    }

    error_class = error_classes.get(category, ApplicationError)

    return error_class(
        message=message,
        severity=severity,
        context=context,
        cause=original_error,
        correlation_id=correlation_id,
        retryable=retryable,
        retry_count=retry_count
    )


def create_error_from_exception(
    exception: Exception,
    category: ErrorCategory,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> ApplicationError:
    """Create an ApplicationError from a standard Python exception."""

    # Map common exception types to our error categories
    exception_mappings = {
        ConnectionError: (ErrorCategory.STORAGE, "Connection error", True),
        TimeoutError: (ErrorCategory.SYSTEM, "Operation timed out", True),
        PermissionError: (ErrorCategory.INGEST_EMAIL, "Permission denied", False),
        FileNotFoundError: (ErrorCategory.STORAGE, "File not found", False),
        ValueError: (ErrorCategory.SYSTEM, "Invalid value", False),
        RuntimeError: (ErrorCategory.SYSTEM, "Runtime error", False)
    }

    # Get mapping or use defaults
    mapping = exception_mappings.get(type(exception), (category, str(exception), False))
    mapped_category, message, retryable = mapping

    return wrap_error(
        original_error=exception,
        message=message,
        category=mapped_category,
        context=context,
        correlation_id=correlation_id,
        retryable=retryable
    )


def get_error_summary(error: ApplicationError) -> Dict[str, Any]:
    """Get a summary of the error for logging purposes."""
    return {
        "error_class": error.__class__.__name__,
        "message": error.message,
        "category": error.category.value,
        "severity": error.severity.value,
        "retryable": error.retryable,
        "retry_count": error.retry_count,
        "correlation_id": error.correlation_id,
        "context_keys": list(error.context.keys()) if error.context else [],
        "has_cause": error.cause is not None
    }

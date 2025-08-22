"""Unit tests for the comprehensive error handling system."""

import json
import pytest
from unittest.mock import Mock
from models.exceptions import (
    ApplicationError,
    ErrorSeverity,
    ErrorCategory,
    IngestEmailError,
    GmailAuthError,
    GmailAPIError,
    GmailThreadNotFoundError,
    EmailParsingError,
    StorageError,
    BlobStorageError,
    BlobNotFoundError,
    StorageConnectionError,
    StorageTimeoutError,
    ChecksumMismatchError,
    OcrError,
    OcrEngineError,
    OcrEngineUnavailableError,
    OcrTimeoutError,
    OcrQuotaExceededError,
    OcrUnsupportedMimeError,
    OcrImageQualityError,
    SystemError,
    ConfigurationError,
    DatabaseError,
    wrap_error,
    create_error_from_exception,
    get_error_summary
)


class TestApplicationError:
    """Test the base ApplicationError class."""

    def test_basic_error_creation(self):
        """Test basic error creation with all parameters."""
        error = ApplicationError(
            message="Test error",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={"key": "value"},
            correlation_id="test-123",
            retryable=True,
            retry_count=2
        )

        assert error.message == "Test error"
        assert error.category == ErrorCategory.SYSTEM
        assert error.severity == ErrorSeverity.ERROR
        assert error.context == {"key": "value"}
        assert error.correlation_id == "test-123"
        assert error.retryable is True
        assert error.retry_count == 2

    def test_error_serialization(self):
        """Test error serialization to dictionary and JSON."""
        error = ApplicationError(
            message="Test error",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={"test": "data"},
            correlation_id="test-123"
        )

        error_dict = error.to_dict()

        assert error_dict["error_class"] == "ApplicationError"
        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "system"
        assert error_dict["severity"] == "error"
        assert error_dict["context"] == {"test": "data"}
        assert error_dict["correlation_id"] == "test-123"
        assert error_dict["retryable"] is False
        assert error_dict["retry_count"] == 0

        # Test JSON serialization
        json_str = error.to_json()
        parsed = json.loads(json_str)
        assert parsed["error_class"] == "ApplicationError"

    def test_error_chain_building(self):
        """Test error chain building with nested causes."""
        root_cause = ValueError("Root cause")
        middle_error = ApplicationError("Middle error", ErrorCategory.SYSTEM, cause=root_cause)
        top_error = ApplicationError("Top error", ErrorCategory.SYSTEM, cause=middle_error)

        assert len(top_error.error_chain) == 3
        assert top_error.error_chain[0]["class"] == "ApplicationError"
        assert "Top error" in top_error.error_chain[0]["message"]
        assert top_error.error_chain[1]["class"] == "ApplicationError"
        assert "Middle error" in top_error.error_chain[1]["message"]
        assert top_error.error_chain[2]["class"] == "ValueError"
        assert top_error.error_chain[2]["message"] == "Root cause"

    def test_string_representation(self):
        """Test string representation of errors."""
        error = ApplicationError(
            message="Test error",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={"key": "value"},
            correlation_id="test-123",
            retry_count=1
        )

        str_repr = str(error)
        assert "[SYSTEM] ERROR: Test error" in str_repr
        assert "test-123" in str_repr
        assert "Retry count: 1" in str_repr


class TestIngestEmailErrors:
    """Test email ingestion related errors."""

    def test_gmail_auth_error(self):
        """Test Gmail authentication error."""
        error = GmailAuthError(
            message="Token expired",
            context={"user": "test@example.com"},
            correlation_id="auth-123"
        )

        assert error.category == ErrorCategory.INGEST_EMAIL
        assert error.severity == ErrorSeverity.ERROR
        assert error.retryable is True
        assert error.context["user"] == "test@example.com"

    def test_gmail_api_error_retryable(self):
        """Test Gmail API error with retryable status code."""
        error = GmailAPIError(
            message="Rate limited",
            status_code=429,
            context={"endpoint": "/messages"},
            correlation_id="api-123"
        )

        assert error.retryable is True
        assert error.context["status_code"] == 429

    def test_gmail_api_error_non_retryable(self):
        """Test Gmail API error with non-retryable status code."""
        error = GmailAPIError(
            message="Not found",
            status_code=404,
            correlation_id="api-456"
        )

        assert error.retryable is False

    def test_gmail_thread_not_found_error(self):
        """Test Gmail thread not found error."""
        error = GmailThreadNotFoundError(
            thread_id="thread-123",
            correlation_id="thread-456"
        )

        assert error.severity == ErrorSeverity.WARNING
        assert error.retryable is False
        assert error.context["thread_id"] == "thread-123"

    def test_email_parsing_error(self):
        """Test email parsing error."""
        error = EmailParsingError(
            message="Malformed MIME structure",
            context={"message_id": "msg-123"},
            correlation_id="parse-123"
        )

        assert error.retryable is False
        assert error.severity == ErrorSeverity.ERROR


class TestStorageErrors:
    """Test storage related errors."""

    def test_blob_storage_error(self):
        """Test blob storage error."""
        error = BlobStorageError(
            message="Upload failed",
            blob_path="documents/test.pdf",
            context={"size": 1024},
            correlation_id="blob-123"
        )

        assert error.category == ErrorCategory.STORAGE
        assert error.retryable is True
        assert error.context["blob_path"] == "documents/test.pdf"

    def test_blob_not_found_error(self):
        """Test blob not found error."""
        error = BlobNotFoundError(
            blob_path="missing/file.pdf",
            correlation_id="missing-123"
        )

        assert error.severity == ErrorSeverity.WARNING
        assert error.retryable is False

    def test_storage_timeout_error(self):
        """Test storage timeout error."""
        error = StorageTimeoutError(
            operation="download",
            timeout_seconds=30,
            context={"attempt": 2},
            correlation_id="timeout-123"
        )

        assert error.retryable is True
        assert error.context["timeout_seconds"] == 30

    def test_checksum_mismatch_error(self):
        """Test checksum mismatch error."""
        error = ChecksumMismatchError(
            blob_path="documents/test.pdf",
            expected_hash="abc123",
            actual_hash="def456",
            correlation_id="checksum-123"
        )

        assert error.retryable is True
        assert error.context["expected_hash"] == "abc123"
        assert error.context["actual_hash"] == "def456"


class TestOcrErrors:
    """Test OCR related errors."""

    def test_ocr_engine_unavailable_error(self):
        """Test OCR engine unavailable error."""
        error = OcrEngineUnavailableError(
            engine="mistral",
            context={"region": "us-east-1"},
            correlation_id="ocr-123"
        )

        assert error.category == ErrorCategory.OCR
        assert error.retryable is True
        assert error.context["engine"] == "mistral"
        assert error.context["error_code"] == "engine_unavailable"

    def test_ocr_timeout_error(self):
        """Test OCR timeout error."""
        error = OcrTimeoutError(
            engine="google_docai",
            timeout_seconds=300,
            correlation_id="timeout-ocr-123"
        )

        assert error.retryable is True
        assert error.context["error_code"] == "timeout"

    def test_ocr_quota_exceeded_error(self):
        """Test OCR quota exceeded error."""
        error = OcrQuotaExceededError(
            engine="azure_docintel",
            correlation_id="quota-123"
        )

        assert error.retryable is False
        assert error.context["error_code"] == "quota_exceeded"

    def test_ocr_unsupported_mime_error(self):
        """Test OCR unsupported MIME type error."""
        error = OcrUnsupportedMimeError(
            engine="tesseract",
            mime_type="video/mp4",
            correlation_id="mime-123"
        )

        assert error.retryable is False
        assert error.context["mime_type"] == "video/mp4"
        assert error.context["error_code"] == "unsupported_mime"

    def test_ocr_image_quality_error(self):
        """Test OCR image quality error."""
        error = OcrImageQualityError(
            engine="paddleocr",
            quality_score=0.3,
            correlation_id="quality-123"
        )

        assert error.retryable is False
        assert error.context["quality_score"] == 0.3
        assert error.context["error_code"] == "image_quality_low"


class TestSystemErrors:
    """Test system related errors."""

    def test_configuration_error(self):
        """Test configuration error."""
        error = ConfigurationError(
            message="Missing required config",
            config_key="DATABASE_URL",
            correlation_id="config-123"
        )

        assert error.category == ErrorCategory.SYSTEM
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.retryable is False
        assert error.context["config_key"] == "DATABASE_URL"

    def test_database_error(self):
        """Test database error."""
        error = DatabaseError(
            message="Connection failed",
            operation="INSERT",
            context={"table": "emails"},
            correlation_id="db-123"
        )

        assert error.retryable is True
        assert error.context["operation"] == "INSERT"


class TestUtilityFunctions:
    """Test utility functions for error handling."""

    def test_wrap_error(self):
        """Test wrapping an existing exception."""
        original_error = ConnectionError("Network unreachable")
        wrapped_error = wrap_error(
            original_error=original_error,
            message="Failed to connect to storage",
            category=ErrorCategory.STORAGE,
            context={"endpoint": "s3.amazonaws.com"},
            correlation_id="wrap-123",
            retryable=True
        )

        assert wrapped_error.cause == original_error
        assert wrapped_error.category == ErrorCategory.STORAGE
        assert wrapped_error.retryable is True
        assert len(wrapped_error.error_chain) == 2

    def test_create_error_from_exception(self):
        """Test creating ApplicationError from standard Python exception."""
        original_error = ConnectionError("Connection refused")
        error = create_error_from_exception(
            exception=original_error,
            category=ErrorCategory.STORAGE,
            context={"host": "localhost"},
            correlation_id="convert-123"
        )

        assert isinstance(error, StorageError)
        assert error.cause == original_error
        assert error.retryable is True

    def test_create_error_from_value_error(self):
        """Test creating ApplicationError from ValueError."""
        original_error = ValueError("Invalid input")
        error = create_error_from_exception(
            exception=original_error,
            category=ErrorCategory.SYSTEM,
            correlation_id="value-123"
        )

        assert isinstance(error, SystemError)
        assert error.retryable is False

    def test_get_error_summary(self):
        """Test getting error summary for logging."""
        error = ApplicationError(
            message="Test error",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={"key": "value"},
            correlation_id="summary-123",
            retryable=True,
            retry_count=1
        )

        summary = get_error_summary(error)

        assert summary["error_class"] == "ApplicationError"
        assert summary["message"] == "Test error"
        assert summary["category"] == "system"
        assert summary["severity"] == "error"
        assert summary["retryable"] is True
        assert summary["retry_count"] == 1
        assert summary["correlation_id"] == "summary-123"
        assert summary["context_keys"] == ["key"]


class TestErrorInheritance:
    """Test that all error classes inherit properly from ApplicationError."""

    def test_all_errors_inherit_from_application_error(self):
        """Ensure all error classes are subclasses of ApplicationError."""
        error_classes = [
            IngestEmailError, GmailAuthError, GmailAPIError, GmailThreadNotFoundError,
            EmailParsingError, StorageError, BlobStorageError, BlobNotFoundError,
            StorageConnectionError, StorageTimeoutError, ChecksumMismatchError,
            OcrError, OcrEngineError, OcrEngineUnavailableError, OcrTimeoutError,
            OcrQuotaExceededError, OcrUnsupportedMimeError, OcrImageQualityError,
            SystemError, ConfigurationError, DatabaseError
        ]

        for error_class in error_classes:
            # Create a simple instance
            if error_class == ChecksumMismatchError:
                error = error_class(blob_path="test", expected_hash="expected", actual_hash="actual")
            elif hasattr(error_class, '__bases__') and ApplicationError in error_class.__mro__:
                if error_class in [GmailThreadNotFoundError]:
                    error = error_class("test-thread-id")
                elif error_class in [OcrEngineUnavailableError, OcrTimeoutError, OcrQuotaExceededError]:
                    error = error_class("test-engine")
                elif error_class == OcrUnsupportedMimeError:
                    error = error_class("test-engine", "text/plain")
                elif error_class == OcrImageQualityError:
                    error = error_class("test-engine")
                elif error_class == OcrEngineError:
                    error = error_class("Test error", "test-engine")
                else:
                    error = error_class("test message")

                assert isinstance(error, ApplicationError)
                assert hasattr(error, 'to_dict')
                assert hasattr(error, 'to_json')
                assert hasattr(error, 'error_chain')

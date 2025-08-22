"""Unit tests for the error logging service."""

import json
import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from services.error_logging_service import (
    ErrorLoggingService,
    ErrorLogEntry,
    MonitoringService,
    SentryMonitoringService,
    ELKMonitoringService,
    log_error,
    log_application_error,
    get_current_correlation_id,
    create_correlation_context
)
from dataclasses import asdict
from models.exceptions import (
    ApplicationError,
    ErrorCategory,
    ErrorSeverity,
    GmailAuthError,
    OcrTimeoutError
)


class TestErrorLoggingService:
    """Test the ErrorLoggingService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ErrorLoggingService()

    def test_log_error_with_generic_exception(self):
        """Test logging a generic Python exception."""
        error = ValueError("Test error")
        context = {"user_id": "123", "operation": "test"}

        with patch.object(self.service.logger, 'error') as mock_log:
            correlation_id = self.service.log_error(error, context)

            # Verify correlation ID was generated
            assert correlation_id is not None
            assert isinstance(uuid.UUID(correlation_id), uuid.UUID)

            # Verify log was called
            assert mock_log.called
            call_args = mock_log.call_args
            assert call_args[0][0] == "Error logged: ValueError"

            # Check log data
            extra_data = call_args[1]['extra']
            assert extra_data['error_class'] == 'ValueError'
            assert extra_data['message'] == 'Test error'
            assert extra_data['category'] == 'system'
            assert extra_data['severity'] == 'error'
            assert extra_data['context'] == context
            assert extra_data['retryable'] is False
            assert extra_data['retry_count'] == 0

    def test_log_error_with_application_error(self):
        """Test logging an ApplicationError."""
        error = GmailAuthError(
            message="Token expired",
            context={"user": "test@example.com"},
            correlation_id="test-123"
        )

        with patch.object(self.service.logger, 'error') as mock_log:
            returned_correlation_id = self.service.log_error(error)

            # Verify correlation ID is preserved
            assert returned_correlation_id == "test-123"

            # Verify log was called
            assert mock_log.called
            call_args = mock_log.call_args
            extra_data = call_args[1]['extra']

            assert extra_data['error_class'] == 'GmailAuthError'
            assert extra_data['category'] == 'ingest_email'
            assert extra_data['severity'] == 'error'
            assert extra_data['retryable'] is True

    def test_log_application_error_method(self):
        """Test the log_application_error method specifically."""
        error = OcrTimeoutError(
            engine="mistral",
            timeout_seconds=300,
            context={"document_id": "doc-123"}
        )
        additional_context = {"workflow_id": "wf-456"}

        with patch.object(self.service.logger, 'error') as mock_log:
            correlation_id = self.service.log_application_error(error, additional_context)

            assert correlation_id is not None
            assert mock_log.called

            call_args = mock_log.call_args
            extra_data = call_args[1]['extra']

            # Verify context merging
            assert extra_data['context']['document_id'] == 'doc-123'
            assert extra_data['context']['workflow_id'] == 'wf-456'

    def test_correlation_id_management(self):
        """Test correlation ID context management."""
        # Initially no correlation ID
        assert self.service.get_current_correlation_id() is None

        # Set correlation ID
        test_id = "test-correlation-123"
        token = self.service.set_correlation_id(test_id)

        # Verify it's set
        assert self.service.get_current_correlation_id() == test_id

        # Reset and verify
        self.service.reset_correlation_id(token)
        assert self.service.get_current_correlation_id() is None

    def test_create_child_correlation_id(self):
        """Test creating child correlation IDs."""
        parent_id = "parent-123"
        child_id = self.service.create_child_correlation_id(parent_id)

        # Child ID should start with parent ID
        assert child_id.startswith(parent_id + ".")

        # Should have additional segment
        parts = child_id.split(".")
        assert len(parts) == 2
        assert len(parts[1]) == 8  # UUID prefix

    def test_log_error_summary(self):
        """Test logging error summary for monitoring."""
        error = RuntimeError("Service unavailable")
        operation = "email_fetch"

        with patch.object(self.service.logger, 'error') as mock_log:
            correlation_id = self.service.log_error_summary(error, operation)

            assert correlation_id is not None
            assert mock_log.called

            call_args = mock_log.call_args
            extra_data = call_args[1]['extra']

            assert extra_data['operation'] == operation
            assert extra_data['error_class'] == 'RuntimeError'
            assert extra_data['error_message'] == 'Service unavailable'
            assert extra_data['correlation_id'] == correlation_id

    def test_log_retry_attempt(self):
        """Test logging retry attempt information."""
        error = ConnectionError("Connection failed")
        operation = "blob_upload"

        with patch.object(self.service.logger, 'warning') as mock_log:
            self.service.log_retry_attempt(
                operation=operation,
                attempt=2,
                max_attempts=3,
                error=error,
                delay_seconds=5.0,
                correlation_id="retry-123"
            )

            assert mock_log.called
            call_args = mock_log.call_args
            extra_data = call_args[1]['extra']

            assert extra_data['operation'] == operation
            assert extra_data['attempt'] == 2
            assert extra_data['max_attempts'] == 3
            assert extra_data['delay_seconds'] == 5.0
            assert extra_data['correlation_id'] == "retry-123"

    def test_log_dead_letter_queue_entry(self):
        """Test logging dead letter queue entry."""
        error = ValueError("Invalid data format")
        operation = "document_processing"
        payload = {"document_id": "doc-123", "data": "invalid"}

        with patch.object(self.service.logger, 'error') as mock_log:
            self.service.log_dead_letter_queue_entry(operation, payload, error)

            assert mock_log.called
            call_args = mock_log.call_args
            extra_data = call_args[1]['extra']

            assert extra_data['operation'] == operation
            assert extra_data['error_class'] == 'ValueError'
            assert 'payload_size' in extra_data


class TestMonitoringServices:
    """Test monitoring service integrations."""

    def test_sentry_monitoring_service_without_dsn(self):
        """Test Sentry service without DSN."""
        service = SentryMonitoringService()
        log_entry = ErrorLogEntry(
            correlation_id="test-123",
            timestamp=datetime.now(timezone.utc),
            error_class="TestError",
            message="Test message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={},
            retryable=False,
            retry_count=0,
            error_chain=[],
            stack_trace=None,
            module=None,
            function=None,
            line_number=None,
            process_info={}
        )

        # Should not raise error even without Sentry SDK
        service.send_error(log_entry)

    @patch('services.error_logging_service.sentry_sdk', create=True)
    def test_sentry_monitoring_service_with_dsn(self, mock_sentry):
        """Test Sentry service with DSN configured."""
        mock_client = Mock()
        mock_sentry.init.return_value = None
        mock_sentry.configure_scope.return_value.__enter__ = Mock(return_value=Mock())
        mock_sentry.configure_scope.return_value.__exit__ = Mock(return_value=None)

        service = SentryMonitoringService(dsn="https://test@sentry.io/123")
        service._client = mock_client

        log_entry = ErrorLogEntry(
            correlation_id="test-123",
            timestamp=datetime.now(timezone.utc),
            error_class="TestError",
            message="Test message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={"key": "value"},
            retryable=True,
            retry_count=2,
            error_chain=[],
            stack_trace="Test stack trace",
            module="test_module",
            function="test_function",
            line_number=42,
            process_info={"process_id": 123}
        )

        service.send_error(log_entry)

        # Verify Sentry was called
        mock_sentry.init.assert_called_once()
        mock_sentry.configure_scope.assert_called_once()
        mock_client.capture_exception.assert_called_once()

    def test_elk_monitoring_service_without_client(self):
        """Test ELK service without Elasticsearch client."""
        service = ELKMonitoringService()
        log_entry = ErrorLogEntry(
            correlation_id="test-123",
            timestamp=datetime.now(timezone.utc),
            error_class="TestError",
            message="Test message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={},
            retryable=False,
            retry_count=0,
            error_chain=[],
            stack_trace=None,
            module=None,
            function=None,
            line_number=None,
            process_info={}
        )

        # Should not raise error without ES client
        service.send_error(log_entry)

    @patch('services.error_logging_service.Elasticsearch', create=True)
    def test_elk_monitoring_service_with_client(self, mock_es_class):
        """Test ELK service with Elasticsearch client."""
        mock_client = Mock()
        mock_es_class.return_value = mock_client

        service = ELKMonitoringService(elasticsearch_url="http://localhost:9200")
        service._client = mock_client

        log_entry = ErrorLogEntry(
            correlation_id="test-123",
            timestamp=datetime.now(timezone.utc),
            error_class="TestError",
            message="Test message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={},
            retryable=False,
            retry_count=0,
            error_chain=[],
            stack_trace=None,
            module=None,
            function=None,
            line_number=None,
            process_info={}
        )

        service.send_error(log_entry)

        # Verify Elasticsearch was called
        mock_client.index.assert_called_once()
        call_args = mock_client.index.call_args
        assert "error-logs-" in call_args[1]['index']


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_log_error_function(self):
        """Test the global log_error function."""
        error = ValueError("Test error")
        context = {"test": "context"}

        with patch('services.error_logging_service.get_error_logging_service') as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service
            mock_service.log_error.return_value = "test-correlation-id"

            correlation_id = log_error(error, context)

            assert correlation_id == "test-correlation-id"
            mock_service.log_error.assert_called_once_with(error, context)

    def test_log_application_error_function(self):
        """Test the global log_application_error function."""
        error = GmailAuthError("Auth failed")

        with patch('services.error_logging_service.get_error_logging_service') as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service
            mock_service.log_application_error.return_value = "test-correlation-id"

            correlation_id = log_application_error(error)

            assert correlation_id == "test-correlation-id"
            mock_service.log_application_error.assert_called_once_with(error, None)

    def test_get_current_correlation_id_function(self):
        """Test the global get_current_correlation_id function."""
        with patch('services.error_logging_service.get_error_logging_service') as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service
            mock_service.get_current_correlation_id.return_value = "current-id"

            result = get_current_correlation_id()

            assert result == "current-id"
            mock_service.get_current_correlation_id.assert_called_once()


class TestCorrelationContext:
    """Test correlation context manager."""

    def test_correlation_context_manager(self):
        """Test using correlation context manager."""
        service = ErrorLoggingService()

        # Test with provided correlation ID
        test_id = "test-correlation-456"
        with create_correlation_context(test_id) as context_id:
            assert context_id == test_id
            assert service.get_current_correlation_id() == test_id

        # Verify correlation ID is cleared after context
        assert service.get_current_correlation_id() is None

    def test_correlation_context_manager_auto_generate(self):
        """Test correlation context manager with auto-generated ID."""
        service = ErrorLoggingService()

        with create_correlation_context() as context_id:
            assert context_id is not None
            assert isinstance(uuid.UUID(context_id), uuid.UUID)
            assert service.get_current_correlation_id() == context_id

        # Verify correlation ID is cleared after context
        assert service.get_current_correlation_id() is None


class TestErrorLogEntry:
    """Test the ErrorLogEntry dataclass."""

    def test_error_log_entry_creation(self):
        """Test creating an ErrorLogEntry."""
        timestamp = datetime.now(timezone.utc)

        entry = ErrorLogEntry(
            correlation_id="test-123",
            timestamp=timestamp,
            error_class="TestError",
            message="Test message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={"key": "value"},
            retryable=True,
            retry_count=1,
            error_chain=[{"class": "TestError", "message": "Test message"}],
            stack_trace="Test stack trace",
            module="test_module",
            function="test_function",
            line_number=42,
            process_info={"process_id": 123}
        )

        assert entry.correlation_id == "test-123"
        assert entry.timestamp == timestamp
        assert entry.error_class == "TestError"
        assert entry.message == "Test message"
        assert entry.category == ErrorCategory.SYSTEM
        assert entry.severity == ErrorSeverity.ERROR
        assert entry.context == {"key": "value"}
        assert entry.retryable is True
        assert entry.retry_count == 1
        assert len(entry.error_chain) == 1
        assert entry.stack_trace == "Test stack trace"
        assert entry.module == "test_module"
        assert entry.function == "test_function"
        assert entry.line_number == 42
        assert entry.process_info == {"process_id": 123}

    def test_error_log_entry_serialization(self):
        """Test serializing ErrorLogEntry to dict."""
        timestamp = datetime.now(timezone.utc)

        entry = ErrorLogEntry(
            correlation_id="test-123",
            timestamp=timestamp,
            error_class="TestError",
            message="Test message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            context={"key": "value"},
            retryable=False,
            retry_count=0,
            error_chain=[],
            stack_trace=None,
            module=None,
            function=None,
            line_number=None,
            process_info={}
        )

        entry_dict = asdict(entry)

        # Check that enums are converted to their values
        assert entry_dict['category'].value == 'system'
        assert entry_dict['severity'].value == 'error'
        assert entry_dict['timestamp'] == timestamp  # Should remain datetime object in dict

        # Check that None values are preserved
        assert entry_dict['stack_trace'] is None
        assert entry_dict['module'] is None

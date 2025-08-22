"""Tests for logging utilities and sensitive data redaction."""

import json
import logging
import pytest
from unittest.mock import patch, MagicMock
import structlog

from utils.logging import (
    SensitiveDataRedactor,
    configure_logging,
    get_logger,
    log_function_entry,
    log_function_exit,
    log_error,
    log_api_request,
    log_ocr_operation,
    log_workflow_step,
    log_performance_metric,
    create_context_logger,
)


class TestSensitiveDataRedactor:
    """Test sensitive data redaction functionality."""

    def test_redact_api_key(self):
        """Test redaction of API keys."""
        message = 'API key: sk-1234567890abcdef'
        redacted = SensitiveDataRedactor.redact_sensitive_data(message)
        assert 'sk-1234567890abcdef' not in redacted
        assert '[REDACTED_API_KEY]' in redacted

    def test_redact_email(self):
        """Test redaction of email addresses."""
        message = 'User email: test@example.com'
        redacted = SensitiveDataRedactor.redact_sensitive_data(message)
        assert 'test@example.com' not in redacted
        assert '[REDACTED_EMAIL]' in redacted

    def test_redact_database_url(self):
        """Test redaction of database URLs with credentials."""
        message = 'DB URL: postgresql://user:password@localhost:5432/db'
        redacted = SensitiveDataRedactor.redact_sensitive_data(message)
        assert 'user:password@localhost:5432' not in redacted
        assert '[REDACTED_DB_URL]' in redacted

    def test_redact_long_strings(self):
        """Test redaction of long alphanumeric strings."""
        long_string = 'A' * 40
        message = f'Token: {long_string}'
        redacted = SensitiveDataRedactor.redact_sensitive_data(message)
        assert long_string not in redacted
        assert '[REDACTED_LONG_STRING]' in redacted

    def test_redact_dictionary(self):
        """Test redaction of sensitive data in dictionaries."""
        data = {
            'user': 'test@example.com',
            'api_key': 'sk-1234567890abcdef',
            'normal_field': 'safe_value',
            'nested': {
                'password': 'secret123',
                'safe': 'value'
            }
        }

        redacted = SensitiveDataRedactor.redact_dict(data)

        assert redacted['user'] == '[REDACTED_EMAIL]'
        assert redacted['api_key'] == '[REDACTED_API_KEY]'
        assert redacted['normal_field'] == 'safe_value'
        assert redacted['nested']['password'] == '[REDACTED_PASSWORD]'
        assert redacted['nested']['safe'] == 'value'

    def test_skip_metadata_fields(self):
        """Test that metadata fields are not redacted."""
        data = {
            'timestamp': '2024-01-01T00:00:00Z',
            'level': 'INFO',
            'logger': 'test_logger',
            'message': 'User email: test@example.com'
        }

        redacted = SensitiveDataRedactor.redact_dict(data)

        assert redacted['timestamp'] == '2024-01-01T00:00:00Z'
        assert redacted['level'] == 'INFO'
        assert redacted['logger'] == 'test_logger'
        assert '[REDACTED_EMAIL]' in redacted['message']


class TestLoggingConfiguration:
    """Test logging configuration and utilities."""

    def test_configure_logging_with_structlog(self):
        """Test logging configuration with structlog."""
        with patch('utils.logging.logging') as mock_logging:
            configure_logging(level='DEBUG', format_type='json')

            # Verify structlog was configured
            structlog.configure.assert_called_once()

    def test_get_logger_structlog(self):
        """Test getting logger with structlog available."""
        with patch('utils.logging.structlog') as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger

            logger = get_logger('test_logger')

            assert logger == mock_logger
            mock_structlog.get_logger.assert_called_with('test_logger')

    def test_get_logger_fallback(self):
        """Test getting logger fallback when structlog not available."""
        with patch('utils.logging.structlog', None):
            with patch('utils.logging.inspect') as mock_inspect:
                mock_frame = MagicMock()
                mock_frame.f_back.f_globals = {'__name__': 'test_module'}
                mock_inspect.currentframe.return_value = mock_frame

                logger = get_logger()

                assert isinstance(logger, logging.Logger)
                assert logger.name == 'test_module'

    def test_log_function_entry_structlog(self):
        """Test function entry logging with structlog."""
        mock_logger = MagicMock()
        with patch('utils.logging.structlog') as mock_structlog:
            mock_structlog.stdlib.BoundLogger = MagicMock

        log_function_entry(mock_logger, 'test_func', {'arg1': 'value1'})

        mock_logger.info.assert_called_with(
            'Entering function test_func',
            func_name='test_func',
            args={'arg1': 'value1'}
        )

    def test_log_function_exit(self):
        """Test function exit logging."""
        mock_logger = MagicMock()
        with patch('utils.logging.structlog') as mock_structlog:
            mock_structlog.stdlib.BoundLogger = MagicMock

        log_function_exit(mock_logger, 'test_func', 'result', 100.5)

        mock_logger.info.assert_called_with(
            'Exiting function test_func',
            func_name='test_func',
            result='result',
            duration_ms=100.5
        )

    def test_log_error(self):
        """Test error logging."""
        mock_logger = MagicMock()
        error = ValueError("Test error")

        log_error(mock_logger, error, {'context': 'test'})

        mock_logger.error.assert_called_with(
            "Error occurred",
            exc_info=error,
            error_type="ValueError",
            error_message="Test error",
            context="test"
        )

    def test_log_api_request(self):
        """Test API request logging."""
        mock_logger = MagicMock()

        log_api_request(mock_logger, 'GET', '/api/test', 200, 150.0, 'user123')

        mock_logger.info.assert_called_with(
            "API request",
            method="GET",
            path="/api/test",
            status_code=200,
            duration_ms=150.0,
            user_id="user123"
        )

    def test_log_ocr_operation(self):
        """Test OCR operation logging."""
        mock_logger = MagicMock()

        log_ocr_operation(
            mock_logger,
            engine='pytesseract',
            operation='process',
            document_id='doc123',
            success=True,
            duration_ms=500.0
        )

        mock_logger.info.assert_called_with(
            "OCR operation",
            engine="pytesseract",
            operation="process",
            document_id="doc123",
            success=True,
            duration_ms=500.0
        )

    def test_log_workflow_step(self):
        """Test workflow step logging."""
        mock_logger = MagicMock()

        log_workflow_step(
            mock_logger,
            workflow='ocr_pipeline',
            step='extract_text',
            status='completed',
            step_id='step_1'
        )

        mock_logger.info.assert_called_with(
            "Workflow step completed",
            workflow="ocr_pipeline",
            step="extract_text",
            status="completed",
            step_id="step_1"
        )

    def test_log_performance_metric(self):
        """Test performance metric logging."""
        mock_logger = MagicMock()

        log_performance_metric(mock_logger, 'response_time', 250.5, 'ms')

        mock_logger.info.assert_called_with(
            "Performance metric: response_time",
            metric_name="response_time",
            value=250.5,
            unit="ms"
        )

    def test_create_context_logger_structlog(self):
        """Test creating context logger with structlog."""
        mock_logger = MagicMock()
        with patch('utils.logging.structlog') as mock_structlog:
            mock_structlog.stdlib.BoundLogger = type(mock_logger)

            context_logger = create_context_logger(mock_logger, user_id='123', request_id='456')

            mock_logger.bind.assert_called_with(user_id='123', request_id='456')

    def test_create_context_logger_fallback(self):
        """Test creating context logger fallback."""
        mock_logger = MagicMock()
        mock_logger.name = 'test_logger'
        mock_logger.getChild = MagicMock()

        with patch('utils.logging.structlog', None):
            context_logger = create_context_logger(mock_logger, key1='value1', key2='value2')

            mock_logger.getChild.assert_called_with('key1_value1_key2_value2')

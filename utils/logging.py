"""Centralized logging configuration for the application."""

import sys
import logging
import os
import re
from typing import Optional, Dict, Any, List
from config import get_settings


class SensitiveDataRedactor:
    """Redactor for sensitive data in logs."""

    # Patterns for sensitive data
    SENSITIVE_PATTERNS = [
        # API keys and tokens
        (r'api_key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?', '[REDACTED_API_KEY]'),
        (r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9\-_\.]{20,})["\']?', '[REDACTED_TOKEN]'),
        (r'password["\']?\s*[:=]\s*["\']?([^"\']{3,})["\']?', '[REDACTED_PASSWORD]'),
        (r'secret["\']?\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{10,})["\']?', '[REDACTED_SECRET]'),
        # Email addresses
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]'),
        # URLs with credentials
        (r'https?://[^:\s]+:[^@\s]+@', '[REDACTED_URL_WITH_CREDS]'),
        # Database connection strings
        (r'postgresql://[^:\s]+:[^@\s]+@', '[REDACTED_DB_URL]'),
        (r'mongodb://[^:\s]+:[^@\s]+@', '[REDACTED_DB_URL]'),
        # Generic patterns for long alphanumeric strings that might be keys
        (r'\b[A-Za-z0-9]{32,}\b', '[REDACTED_LONG_STRING]'),
    ]

    @classmethod
    def redact_sensitive_data(cls, message: str) -> str:
        """Redact sensitive data from log messages.

        Args:
            message: The log message to redact

        Returns:
            The message with sensitive data redacted
        """
        if not isinstance(message, str):
            return str(message)

        redacted_message = message
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            redacted_message = re.sub(pattern, replacement, redacted_message, flags=re.IGNORECASE)

        return redacted_message

    @classmethod
    def redact_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive data from dictionary values.

        Args:
            data: Dictionary to redact

        Returns:
            Dictionary with sensitive values redacted
        """
        if not isinstance(data, dict):
            return data

        redacted_data = {}
        for key, value in data.items():
            # Skip redacting certain metadata keys
            if key.lower() in ['timestamp', 'level', 'logger', 'request_id']:
                redacted_data[key] = value
                continue

            if isinstance(value, str):
                redacted_data[key] = cls.redact_sensitive_data(value)
            elif isinstance(value, dict):
                redacted_data[key] = cls.redact_dict(value)
            elif isinstance(value, list):
                redacted_data[key] = [cls.redact_dict(item) if isinstance(item, dict) else
                                     cls.redact_sensitive_data(item) if isinstance(item, str) else item
                                     for item in value]
            else:
                redacted_data[key] = value

        return redacted_data


def configure_logging(
    level: Optional[str] = None,
    format_type: Optional[str] = None,
    app_name: Optional[str] = None
) -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ('json' or 'console')
        app_name: Application name for logging context
    """
    settings = get_settings()

    # Use provided values or fall back to settings
    log_level = level or settings.LOG_LEVEL
    format_type = format_type or settings.LOG_FORMAT
    app_name = app_name or settings.APP_NAME

    # Clear existing handlers to avoid duplicate logs
    logging.getLogger().handlers.clear()

    # Create handlers list
    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        fmt="%(message)s" if format_type.lower() == "json" else f"[%(asctime)s] {app_name} - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    handlers.append(console_handler)

    # File handler (if enabled)
    if settings.ENABLE_FILE_LOGGING and settings.LOG_FILE_PATH:
        try:
            from logging.handlers import RotatingFileHandler

            # Ensure log directory exists
            log_dir = os.path.dirname(settings.LOG_FILE_PATH)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_handler = RotatingFileHandler(
                settings.LOG_FILE_PATH,
                maxBytes=settings.LOG_MAX_FILE_SIZE,
                backupCount=settings.LOG_BACKUP_COUNT
            )
            file_formatter = logging.Formatter(
                fmt=f"[%(asctime)s] {app_name} - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(getattr(logging, log_level.upper()))
            handlers.append(file_handler)
        except Exception as e:
            print(f"Failed to configure file logging: {e}")

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True
    )

    # Configure structlog if available
    try:
        import structlog

        # Configure structlog processors based on format
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
        ]

        # Add sensitive data redaction processor
        def redact_processor(logger, method_name, event_dict):
            """Processor to redact sensitive data from log events."""
            redacted_event = SensitiveDataRedactor.redact_dict(event_dict)
            return redacted_event

        processors.append(redact_processor)

        if format_type.lower() == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    except ImportError:
        # structlog not available, continue with standard logging
        pass


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name. If None, uses the calling module name.

    Returns:
        Configured logger instance
    """
    try:
        import structlog
        return structlog.get_logger(name)
    except ImportError:
        import inspect
        if name is None:
            # Get the calling module name
            frame = inspect.currentframe()
            try:
                name = frame.f_back.f_globals.get("__name__", "unknown")
            finally:
                del frame
        return logging.getLogger(name)


def get_request_logger() -> logging.Logger:
    """Get a logger specifically for HTTP request logging."""
    return get_logger("api.request")


def get_task_logger() -> logging.Logger:
    """Get a logger specifically for Celery task logging."""
    return get_logger("celery.task")


def get_database_logger() -> logging.Logger:
    """Get a logger specifically for database operations."""
    return get_logger("database")


def log_function_entry(logger: logging.Logger, func_name: str, args: Dict[str, Any] = None, **kwargs) -> None:
    """Log function entry with parameters.

    Args:
        logger: Logger instance
        func_name: Function name
        args: Function arguments (will be redacted)
        **kwargs: Additional context
    """
    try:
        import structlog
        if isinstance(logger, structlog.stdlib.BoundLogger):
            logger.info(f"Entering function {func_name}", func_name=func_name, args=args, **kwargs)
        else:
            logger.info(f"Entering function {func_name}", extra={"func_name": func_name, "args": args, **kwargs})
    except ImportError:
        logger.info(f"Entering function {func_name}", extra={"func_name": func_name, "args": args, **kwargs})


def log_function_exit(logger: logging.Logger, func_name: str, result: Any = None, duration_ms: float = None, **kwargs) -> None:
    """Log function exit with result and duration.

    Args:
        logger: Logger instance
        func_name: Function name
        result: Function result (will be redacted)
        duration_ms: Function execution duration in milliseconds
        **kwargs: Additional context
    """
    log_data = {"func_name": func_name, "duration_ms": duration_ms, **kwargs}

    try:
        import structlog
        if isinstance(logger, structlog.stdlib.BoundLogger):
            if result is not None:
                log_data["result"] = result
            logger.info(f"Exiting function {func_name}", **log_data)
        else:
            if result is not None:
                log_data["result"] = result
            logger.info(f"Exiting function {func_name}", extra=log_data)
    except ImportError:
        if result is not None:
            log_data["result"] = result
        logger.info(f"Exiting function {func_name}", extra=log_data)


def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None, **kwargs) -> None:
    """Log error with context and redaction.

    Args:
        logger: Logger instance
        error: Exception object
        context: Additional context
        **kwargs: Additional key-value pairs
    """
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {}),
        **kwargs
    }

    try:
        import structlog
        if isinstance(logger, structlog.stdlib.BoundLogger):
            logger.error("Error occurred", exc_info=error, **error_data)
        else:
            logger.error("Error occurred", exc_info=error, extra=error_data)
    except ImportError:
        logger.error("Error occurred", exc_info=error, extra=error_data)


def log_api_request(logger: logging.Logger, method: str, path: str, status_code: int = None,
                   duration_ms: float = None, user_id: str = None, **kwargs) -> None:
    """Log API request with structured data.

    Args:
        logger: Logger instance
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        user_id: User identifier
        **kwargs: Additional context
    """
    log_data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "user_id": user_id,
        **kwargs
    }

    try:
        import structlog
        if isinstance(logger, structlog.stdlib.BoundLogger):
            logger.info("API request", **log_data)
        else:
            logger.info("API request", extra=log_data)
    except ImportError:
        logger.info("API request", extra=log_data)


def log_ocr_operation(logger: logging.Logger, engine: str, operation: str, document_id: str = None,
                     success: bool = True, duration_ms: float = None, **kwargs) -> None:
    """Log OCR operation with structured data.

    Args:
        logger: Logger instance
        engine: OCR engine name
        operation: Operation performed (e.g., 'process', 'extract', 'validate')
        document_id: Document identifier
        success: Whether operation was successful
        duration_ms: Operation duration in milliseconds
        **kwargs: Additional context
    """
    log_data = {
        "engine": engine,
        "operation": operation,
        "document_id": document_id,
        "success": success,
        "duration_ms": duration_ms,
        **kwargs
    }

    try:
        import structlog
        if isinstance(logger, structlog.stdlib.BoundLogger):
            logger.info("OCR operation", **log_data)
        else:
            logger.info("OCR operation", extra=log_data)
    except ImportError:
        logger.info("OCR operation", extra=log_data)


def log_workflow_step(logger: logging.Logger, workflow: str, step: str, status: str,
                     step_id: str = None, **kwargs) -> None:
    """Log workflow step execution.

    Args:
        logger: Logger instance
        workflow: Workflow name
        step: Step name
        status: Step status (e.g., 'started', 'completed', 'failed')
        step_id: Unique step identifier
        **kwargs: Additional context
    """
    log_data = {
        "workflow": workflow,
        "step": step,
        "status": status,
        "step_id": step_id,
        **kwargs
    }

    try:
        import structlog
        if isinstance(logger, structlog.stdlib.BoundLogger):
            logger.info(f"Workflow step {status}", **log_data)
        else:
            logger.info(f"Workflow step {status}", extra=log_data)
    except ImportError:
        logger.info(f"Workflow step {status}", extra=log_data)


def log_performance_metric(logger: logging.Logger, metric_name: str, value: float,
                          unit: str = None, **kwargs) -> None:
    """Log performance metric.

    Args:
        logger: Logger instance
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        **kwargs: Additional context
    """
    log_data = {
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        **kwargs
    }

    try:
        import structlog
        if isinstance(logger, structlog.stdlib.BoundLogger):
            logger.info(f"Performance metric: {metric_name}", **log_data)
        else:
            logger.info(f"Performance metric: {metric_name}", extra=log_data)
    except ImportError:
        logger.info(f"Performance metric: {metric_name}", extra=log_data)


def create_context_logger(base_logger: logging.Logger, **context) -> logging.Logger:
    """Create a logger with persistent context.

    Args:
        base_logger: Base logger instance
        **context: Context key-value pairs

    Returns:
        Logger with persistent context
    """
    try:
        import structlog
        if isinstance(base_logger, structlog.stdlib.BoundLogger):
            return base_logger.bind(**context)
        else:
            # For standard logging, we create a child logger
            return base_logger.getChild("_".join(f"{k}_{v}" for k, v in context.items()))
    except ImportError:
        return base_logger.getChild("_".join(f"{k}_{v}" for k, v in context.items()))


def setup_uvicorn_logging() -> dict:
    """Configure logging for Uvicorn server.

    Returns:
        Dictionary with uvicorn logging configuration
    """
    settings = get_settings()

    log_level = getattr(logging, settings.LOG_LEVEL.upper())

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "access": {
                "format": "[%(asctime)s] %(levelname)s - %(client_addr)s - \"%(request_line)s\" %(status_code)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout"
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout"
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": log_level},
            "uvicorn.error": {"level": log_level},
            "uvicorn.access": {"handlers": ["access"], "level": log_level, "propagate": False},
        }
    }


# Initialize logging when module is imported
configure_logging()

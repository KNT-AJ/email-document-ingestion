"""Base task classes for Celery with logging and error handling."""

import time
from typing import Any, Dict, Optional, Union
from datetime import datetime

from celery import Task
from celery.exceptions import Retry

from utils.logging import get_logger
from config import get_settings

# Get settings
settings = get_settings()
logger = get_logger("celery.base_task")


class BaseTask(Task):
    """Base task class with comprehensive logging and error handling.

    This class provides:
    - Structured logging for task lifecycle events
    - Automatic error handling and retry logic
    - Task execution time tracking
    - Dead-letter queue support for failed tasks
    - Progress tracking
    """

    abstract = True
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_kwargs = {'max_retries': 3}
    time_limit = 600  # 10 minutes
    soft_time_limit = 300  # 5 minutes

    def __init__(self):
        """Initialize the base task."""
        self.start_time = None
        self.task_logger = get_logger(f"celery.task.{self.__class__.__name__}")

    def on_success(self, retval, task_id, args, kwargs):
        """Handle successful task completion."""
        execution_time = time.time() - self.start_time if self.start_time else 0

        self.task_logger.info(
            "Task completed successfully",
            task_id=task_id,
            task_name=self.name,
            execution_time_seconds=round(execution_time, 2),
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()) if kwargs else [],
            result_type=type(retval).__name__,
            status="success"
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        execution_time = time.time() - self.start_time if self.start_time else 0

        self.task_logger.error(
            "Task failed",
            task_id=task_id,
            task_name=self.name,
            execution_time_seconds=round(execution_time, 2),
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()) if kwargs else [],
            max_retries=self.retry_kwargs.get('max_retries', 0),
            current_retry=getattr(self.request, 'retries', 0),
            status="failed"
        )

        # Move to dead-letter queue if max retries exceeded
        max_retries = self.retry_kwargs.get('max_retries', 0)
        current_retry = getattr(self.request, 'retries', 0)

        if current_retry >= max_retries:
            self._move_to_dead_letter_queue(task_id, exc, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        execution_time = time.time() - self.start_time if self.start_time else 0

        self.task_logger.warning(
            "Task retrying",
            task_id=task_id,
            task_name=self.name,
            execution_time_seconds=round(execution_time, 2),
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            current_retry=getattr(self.request, 'retries', 0),
            max_retries=self.retry_kwargs.get('max_retries', 0),
            status="retrying"
        )

    def __call__(self, *args, **kwargs):
        """Execute the task with timing and error handling."""
        self.start_time = time.time()

        self.task_logger.info(
            "Task started",
            task_id=self.request.id,
            task_name=self.name,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()) if kwargs else [],
            queue=self.request.delivery_info.get('routing_key', 'unknown') if self.request.delivery_info else 'unknown',
            status="started"
        )

        try:
            result = super().__call__(*args, **kwargs)
            return result
        except Exception as exc:
            self.task_logger.error(
                "Task execution failed",
                task_id=self.request.id,
                task_name=self.name,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                status="error"
            )
            raise

    def update_progress(self, current: int, total: int, message: str = ""):
        """Update task progress."""
        if total > 0:
            progress = (current / total) * 100
        else:
            progress = 0

        self.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': total,
                'progress': progress,
                'message': message,
                'task_id': self.request.id,
                'task_name': self.name,
            }
        )

        self.task_logger.debug(
            "Task progress updated",
            task_id=self.request.id,
            task_name=self.name,
            current=current,
            total=total,
            progress=round(progress, 2),
            message=message
        )

    def _move_to_dead_letter_queue(self, task_id: str, exc: Exception, args: tuple, kwargs: dict, einfo: Any):
        """Move failed task to dead-letter queue."""
        try:
            from workers.celery_app import celery_app

            dead_letter_data = {
                'original_task_id': task_id,
                'task_name': self.name,
                'args': args,
                'kwargs': kwargs,
                'exception_type': type(exc).__name__,
                'exception_message': str(exc),
                'traceback': str(einfo),
                'failed_at': datetime.utcnow().isoformat(),
                'retries': getattr(self.request, 'retries', 0),
            }

            # Send to dead-letter queue
            celery_app.send_task(
                'app.tasks.handle_failed_task',
                args=[dead_letter_data],
                queue='failed_tasks',
                routing_key='failed_tasks'
            )

            self.task_logger.info(
                "Task moved to dead-letter queue",
                task_id=task_id,
                task_name=self.name,
                failed_task_id=task_id
            )

        except Exception as dlq_exc:
            self.task_logger.error(
                "Failed to move task to dead-letter queue",
                task_id=task_id,
                task_name=self.name,
                dlq_exception=str(dlq_exc)
            )


class IOBoundTask(BaseTask):
    """Base task for I/O bound operations.

    Optimized for tasks that spend most time waiting for I/O operations
    like network requests, file operations, or database queries.
    """

    abstract = True
    time_limit = 1200  # 20 minutes (longer for I/O operations)
    soft_time_limit = 900  # 15 minutes
    retry_backoff_max = 300  # 5 minutes (shorter backoff for I/O issues)

    def __init__(self):
        """Initialize I/O bound task."""
        super().__init__()
        self.task_logger = get_logger(f"celery.task.io.{self.__class__.__name__}")


class CPUBoundTask(BaseTask):
    """Base task for CPU bound operations.

    Optimized for tasks that require significant CPU processing
    like image processing, data analysis, or complex calculations.
    """

    abstract = True
    time_limit = 1800  # 30 minutes (longer for CPU-intensive tasks)
    soft_time_limit = 1500  # 25 minutes
    retry_backoff_max = 900  # 15 minutes (longer backoff for CPU issues)

    def __init__(self):
        """Initialize CPU bound task."""
        super().__init__()
        self.task_logger = get_logger(f"celery.task.cpu.{self.__class__.__name__}")


class APITask(IOBoundTask):
    """Base task for external API calls.

    Includes specific handling for API rate limits, timeouts,
    and network-related errors.
    """

    abstract = True
    autoretry_for = (Exception, TimeoutError, ConnectionError)
    retry_backoff_max = 600  # 10 minutes
    time_limit = 300  # 5 minutes (APIs shouldn't take longer)
    soft_time_limit = 180  # 3 minutes

    def __init__(self):
        """Initialize API task."""
        super().__init__()
        self.task_logger = get_logger(f"celery.task.api.{self.__class__.__name__}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Enhanced retry logic for API tasks."""
        super().on_retry(exc, task_id, args, kwargs, einfo)

        # Log additional context for API errors
        self.task_logger.warning(
            "API task retry details",
            task_id=task_id,
            task_name=self.name,
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            retry_after=self.retry_backoff,
            current_retry=getattr(self.request, 'retries', 0)
        )


class DocumentProcessingTask(CPUBoundTask):
    """Base task for document processing operations.

    Includes specific handling for OCR, image processing,
    and document analysis tasks.
    """

    abstract = True
    time_limit = 3600  # 1 hour (document processing can be long)
    soft_time_limit = 3000  # 50 minutes
    autoretry_for = (Exception, FileNotFoundError, PermissionError)

    def __init__(self):
        """Initialize document processing task."""
        super().__init__()
        self.task_logger = get_logger(f"celery.task.doc.{self.__class__.__name__}")


class BatchProcessingTask(BaseTask):
    """Base task for batch processing operations.

    Handles large volumes of data processing with proper progress
    tracking and chunked processing.
    """

    abstract = True
    time_limit = 7200  # 2 hours (batch operations can be very long)
    soft_time_limit = 6000  # 100 minutes
    chunk_size = 100  # Default chunk size for batch processing

    def __init__(self):
        """Initialize batch processing task."""
        super().__init__()
        self.task_logger = get_logger(f"celery.task.batch.{self.__class__.__name__}")

    def process_batch(self, items: list, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """Process items in batches with progress tracking."""
        if not items:
            return {'processed': 0, 'failed': 0, 'results': []}

        batch_size = batch_size or self.chunk_size
        results = []
        processed = 0
        failed = 0

        total_items = len(items)

        for i in range(0, total_items, batch_size):
            batch = items[i:i + batch_size]
            batch_start = i + 1
            batch_end = min(i + batch_size, total_items)

            self.update_progress(
                batch_start,
                total_items,
                f"Processing batch {batch_start}-{batch_end} of {total_items}"
            )

            try:
                batch_results = self.process_batch_chunk(batch)
                results.extend(batch_results)
                processed += len(batch_results)
            except Exception as exc:
                self.task_logger.error(
                    "Batch processing failed",
                    task_id=self.request.id,
                    task_name=self.name,
                    batch_start=batch_start,
                    batch_end=batch_end,
                    exception=str(exc)
                )
                failed += len(batch)

        return {
            'processed': processed,
            'failed': failed,
            'total': total_items,
            'results': results
        }

    def process_batch_chunk(self, batch: list) -> list:
        """Process a single batch chunk. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement process_batch_chunk")


# Task registry for easy access
TASK_CLASSES = {
    'base': BaseTask,
    'io': IOBoundTask,
    'cpu': CPUBoundTask,
    'api': APITask,
    'document': DocumentProcessingTask,
    'batch': BatchProcessingTask,
}


__all__ = [
    'BaseTask',
    'IOBoundTask',
    'CPUBoundTask',
    'APITask',
    'DocumentProcessingTask',
    'BatchProcessingTask',
    'TASK_CLASSES',
]

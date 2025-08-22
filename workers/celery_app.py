"""Celery application configuration with environment-based settings."""

from celery import Celery
from celery.signals import setup_logging

from config import get_settings
from config.celery_config import get_celery_config
from utils.logging import get_logger

# Get settings and configuration
settings = get_settings()
celery_config = get_celery_config()
logger = get_logger("celery")

# Create Celery app
celery_app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "workers.tasks.email_ingestion",
        "workers.tasks.document_processing",
        "workers.tasks.ocr_workflow",
        "workers.tasks.system_tasks",
        "api.routes.reprocess"  # Include reprocess routes for task discovery
    ],  # Import task modules
)

# Configure Celery using environment-based configuration
celery_app.conf.update(celery_config)


@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure Celery logging to use our logging system."""
    # Celery will use our configured logging
    pass


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    logger.info("Debug task executed", task_id=self.request.id)
    return f"Task {self.request.id} completed successfully"


# Export the app instance
__all__ = ["celery_app"]

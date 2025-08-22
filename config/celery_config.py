"""Celery configuration module with environment variable support."""

import os
from typing import List, Dict, Any
from celery.schedules import crontab
from kombu import Queue, Exchange

from .settings import get_settings

# Get settings instance
settings = get_settings()


class CeleryConfig:
    """Environment-based Celery configuration following 12-Factor principles."""

    # Broker and Result Backend
    broker_url = settings.CELERY_BROKER_URL
    result_backend = settings.CELERY_RESULT_BACKEND

    # Serialization
    task_serializer = settings.CELERY_TASK_SERIALIZER
    accept_content = settings.CELERY_ACCEPT_CONTENT
    result_serializer = settings.CELERY_RESULT_SERIALIZER

    # Time and Timezone
    timezone = settings.CELERY_TIMEZONE
    enable_utc = settings.CELERY_ENABLE_UTC

    # Worker Configuration
    worker_prefetch_multiplier = 1
    task_acks_late = True
    worker_concurrency = settings.MAX_CONCURRENT_TASKS

    # Task Time Limits (in seconds)
    task_soft_time_limit = 300  # 5 minutes
    task_time_limit = 600       # 10 minutes

    # Result Configuration
    result_expires = 3600  # 1 hour
    task_ignore_result = False

    # Task Routing and Queues
    task_default_queue = 'default'
    task_default_exchange_type = 'direct'
    task_default_routing_key = 'default'

    # Queue Definitions
    task_queues = (
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('email_ingestion', Exchange('email_ingestion'), routing_key='email_ingestion'),
        Queue('document_processing', Exchange('document_processing'), routing_key='document_processing'),
        Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
        Queue('long_running', Exchange('long_running'), routing_key='long_running'),
        Queue('failed_tasks', Exchange('failed_tasks'), routing_key='failed_tasks'),
        Queue('retry_tasks', Exchange('retry_tasks'), routing_key='retry_tasks'),
    )

    # Task Routing
    task_routes = {
        # Route email processing tasks to email_ingestion queue
        'workers.tasks.email_ingestion.process_email_ingestion': {
            'queue': 'email_ingestion',
            'routing_key': 'email_ingestion'
        },

        # Route document processing tasks to document_processing queue
        'workers.tasks.document_processing.process_document_ocr': {
            'queue': 'document_processing',
            'routing_key': 'document_processing'
        },
        'workers.tasks.document_processing.process_batch_documents': {
            'queue': 'document_processing',
            'routing_key': 'document_processing'
        },

        # Route high-priority tasks
        'app.tasks.high_priority.*': {
            'queue': 'high_priority',
            'routing_key': 'high_priority'
        },

        # Route long-running tasks
        'app.tasks.long_running.*': {
            'queue': 'long_running',
            'routing_key': 'long_running'
        },

        # Route failed tasks to dead-letter queue
        'app.tasks.failed.*': {
            'queue': 'failed_tasks',
            'routing_key': 'failed_tasks'
        },

        # Route system tasks to default queue
        'workers.tasks.system_tasks.health_check': {
            'queue': 'default',
            'routing_key': 'default'
        },
        'workers.tasks.system_tasks.cleanup_expired_results': {
            'queue': 'default',
            'routing_key': 'default'
        },
        'workers.tasks.system_tasks.generate_daily_reports': {
            'queue': 'default',
            'routing_key': 'default'
        },
        'workers.tasks.system_tasks.cleanup_old_logs': {
            'queue': 'default',
            'routing_key': 'default'
        },

        # Route dead-letter queue processing to retry_tasks queue
        'workers.tasks.system_tasks.process_dead_letter_queue': {
            'queue': 'retry_tasks',
            'routing_key': 'retry_tasks'
        },
        'workers.tasks.system_tasks.handle_failed_task': {
            'queue': 'failed_tasks',
            'routing_key': 'failed_tasks'
        },
    }

    # Dead-letter Exchange Configuration
    task_publish_retry = True
    task_publish_retry_policy = {
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.5,
    }

    # Monitoring and Events
    task_send_sent_event = True
    worker_send_task_events = True
    task_track_started = True

    # Logging Configuration
    worker_hijack_root_logger = False

    # Rate Limiting
    worker_disable_rate_limits = False

    # Task Annotations for Error Handling
    task_annotations = {
        '*': {
            'rate_limit': '100/m',  # Default rate limit
        },
        'workers.tasks.document_processing.*': {
            'rate_limit': '10/m',  # Lower rate limit for CPU-intensive tasks
            'time_limit': 1800,    # 30 minutes for document processing
            'soft_time_limit': 1500,
        },
        'workers.tasks.email_ingestion.*': {
            'rate_limit': '50/m',  # Moderate rate limit for I/O tasks
            'time_limit': 600,     # 10 minutes for email processing
            'soft_time_limit': 300,
        },
    }

    # Scheduled Tasks (Celery Beat)
    beat_schedule = {
        # Health check task - runs every 5 minutes
        'health-check': {
            'task': 'workers.tasks.system_tasks.health_check',
            'schedule': crontab(minute='*/5'),
            'options': {
                'queue': 'default',
                'expires': 300,
            }
        },

        # Cleanup expired results - runs daily at 2 AM
        'cleanup-expired-results': {
            'task': 'workers.tasks.system_tasks.cleanup_expired_results',
            'schedule': crontab(hour=2, minute=0),
            'options': {
                'queue': 'default',
                'expires': 3600,
            }
        },

        # Process dead-letter queue - runs every 10 minutes
        'process-dead-letter-queue': {
            'task': 'workers.tasks.system_tasks.process_dead_letter_queue',
            'schedule': crontab(minute='*/10'),
            'options': {
                'queue': 'retry_tasks',
                'expires': 600,
            }
        },

        # Generate daily reports - runs daily at 6 AM
        'generate-daily-reports': {
            'task': 'workers.tasks.system_tasks.generate_daily_reports',
            'schedule': crontab(hour=6, minute=0),
            'options': {
                'queue': 'default',
                'expires': 3600,
            }
        },

        # Cleanup old logs - runs weekly on Sunday at 3 AM
        'cleanup-old-logs': {
            'task': 'workers.tasks.system_tasks.cleanup_old_logs',
            'schedule': crontab(hour=3, minute=0, day_of_week='sunday'),
            'options': {
                'queue': 'default',
                'expires': 3600,
            }
        },
    }

    # Beat Configuration
    beat_scheduler = 'celery.beat.PersistentScheduler'
    beat_schedule_filename = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data',
        'celerybeat-schedule'
    )

    # Beat Database Directory
    beat_db_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data'
    )

    # Ensure beat database directory exists
    os.makedirs(beat_db_dir, exist_ok=True)

    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """Get configuration as a dictionary for Celery app configuration."""
        config_dict = {}
        for attr_name in dir(cls):
            if not attr_name.startswith('_') and not callable(getattr(cls, attr_name)):
                attr_value = getattr(cls, attr_name)
                if not attr_name.startswith('__'):
                    config_dict[attr_name] = attr_value
        return config_dict

    @classmethod
    def get_environment_info(cls) -> Dict[str, Any]:
        """Get environment-specific configuration information."""
        return {
            'broker_url': cls.broker_url,
            'result_backend': cls.result_backend,
            'timezone': cls.timezone,
            'concurrency': cls.worker_concurrency,
            'queues': [queue.name for queue in cls.task_queues],
            'scheduled_tasks': list(cls.beat_schedule.keys()),
        }


# Environment-specific configurations
class DevelopmentConfig(CeleryConfig):
    """Development environment configuration."""

    # Less restrictive settings for development
    task_soft_time_limit = 600   # 10 minutes
    task_time_limit = 1200        # 20 minutes
    worker_concurrency = 2        # Lower concurrency for dev

    # Enable debugging
    worker_disable_rate_limits = True

    # Development beat schedule (less frequent tasks)
    beat_schedule = {
        'health-check': {
            'task': 'app.tasks.health_check',
            'schedule': crontab(minute='*/2'),  # Every 2 minutes in dev
            'options': {
                'queue': 'default',
                'expires': 60,
            }
        },
    }


class ProductionConfig(CeleryConfig):
    """Production environment configuration."""

    # Stricter settings for production
    task_soft_time_limit = 300   # 5 minutes
    task_time_limit = 600        # 10 minutes
    worker_concurrency = settings.MAX_CONCURRENT_TASKS

    # Enable rate limiting
    worker_disable_rate_limits = False

    # More restrictive task annotations
    task_annotations = {
        **CeleryConfig.task_annotations,
        '*': {
            'rate_limit': '200/m',  # Higher rate limit for production
        },
    }


class TestingConfig(CeleryConfig):
    """Testing environment configuration."""

    # Test-specific settings
    task_always_eager = True      # Execute tasks synchronously
    task_eager_propagates = True  # Propagate exceptions in tests
    worker_concurrency = 1        # Single thread for tests

    # Disable rate limiting for tests
    worker_disable_rate_limits = True

    # Disable beat scheduler in tests
    beat_scheduler = None

    # Empty beat schedule for tests
    beat_schedule = {}


def get_celery_config() -> Dict[str, Any]:
    """Get Celery configuration based on current environment."""
    environment = os.getenv('ENVIRONMENT', 'development').lower()

    config_classes = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig,
    }

    config_class = config_classes.get(environment, DevelopmentConfig)
    return config_class.get_config_dict()


def get_celery_environment_info() -> Dict[str, Any]:
    """Get environment-specific configuration information."""
    environment = os.getenv('ENVIRONMENT', 'development').lower()

    config_classes = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig,
    }

    config_class = config_classes.get(environment, DevelopmentConfig)
    return config_class.get_environment_info()


# Export the configuration function
__all__ = [
    'CeleryConfig',
    'DevelopmentConfig',
    'ProductionConfig',
    'TestingConfig',
    'get_celery_config',
    'get_celery_environment_info',
]

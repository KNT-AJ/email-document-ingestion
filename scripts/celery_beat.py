#!/usr/bin/env python3
"""Celery Beat scheduler for periodic tasks."""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from workers.celery_app import celery_app
from config import get_settings

def main():
    """Main entry point for Celery Beat."""
    settings = get_settings()

    # Set up environment
    os.environ.setdefault('ENVIRONMENT', 'development')

    print(f"Starting Celery Beat for {settings.APP_NAME}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Beat schedule file: {celery_app.conf.beat_schedule_filename}")
    print("Scheduled tasks:")

    # Print scheduled tasks
    for task_name, task_config in celery_app.conf.beat_schedule.items():
        task = task_config['task']
        schedule = task_config['schedule']
        print(f"  - {task_name}: {task} ({schedule})")

    print("\nStarting scheduler...")

    # Start Celery Beat
    celery_app.Beat(
        hostname=f"beat@{settings.APP_NAME.lower().replace(' ', '_')}",
        loglevel=settings.LOG_LEVEL.lower(),
    ).run()

if __name__ == "__main__":
    main()

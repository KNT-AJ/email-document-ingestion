#!/usr/bin/env python3
"""Celery Worker starter script."""

import os
import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from workers.celery_app import celery_app
from config import get_settings

def main():
    """Main entry point for Celery Worker."""
    parser = argparse.ArgumentParser(description='Start Celery Worker')
    parser.add_argument(
        '--queues',
        default='default,email_ingestion,document_processing',
        help='Comma-separated list of queues to consume from'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        help='Number of concurrent worker processes'
    )
    parser.add_argument(
        '--hostname',
        help='Worker hostname'
    )
    parser.add_argument(
        '--loglevel',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level'
    )

    args = parser.parse_args()

    settings = get_settings()

    # Set up environment
    os.environ.setdefault('ENVIRONMENT', 'development')

    # Build worker arguments
    worker_args = []

    # Set hostname
    if args.hostname:
        worker_args.extend(['--hostname', args.hostname])
    else:
        hostname = f"worker@{settings.APP_NAME.lower().replace(' ', '_')}"
        worker_args.extend(['--hostname', hostname])

    # Set queues
    worker_args.extend(['--queues', args.queues])

    # Set concurrency
    if args.concurrency:
        worker_args.extend(['--concurrency', str(args.concurrency)])
    elif hasattr(settings, 'MAX_CONCURRENT_TASKS'):
        worker_args.extend(['--concurrency', str(settings.MAX_CONCURRENT_TASKS)])

    # Set log level
    worker_args.extend(['--loglevel', args.loglevel])

    # Add other useful flags
    worker_args.extend([
        '--prefetch-multiplier', '1',
        '--without-gossip',
        '--without-mingle',
        '--without-heartbeat',
        '--task-events',  # Enable task events for monitoring
    ])

    print(f"Starting Celery Worker for {settings.APP_NAME}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Queues: {args.queues}")
    print(f"Concurrency: {args.concurrency or settings.MAX_CONCURRENT_TASKS}")
    print(f"Log level: {args.loglevel}")
    print(f"Broker: {settings.CELERY_BROKER_URL}")
    print(f"Worker hostname: {args.hostname or hostname}")
    print("Starting worker...")

    # Start Celery Worker
    celery_app.Worker(
        hostname=args.hostname or hostname,
        concurrency=args.concurrency or settings.MAX_CONCURRENT_TASKS,
        loglevel=args.loglevel.lower(),
        queues=args.queues.split(','),
        prefetch_multiplier=1,
        without_gossip=True,
        without_mingle=True,
        without_heartbeat=True,
        task_events=True,
    ).run()

if __name__ == "__main__":
    main()

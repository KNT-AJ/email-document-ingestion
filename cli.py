"""Command-line interface for the Email & Document Ingestion System."""

import typer
import uvicorn
import subprocess
import os
from pathlib import Path
from typing import Optional

from config import get_settings
from utils.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger("cli")
settings = get_settings()

# Create Typer app with better organization
app = typer.Typer(
    name=settings.APP_NAME,
    help="CLI for managing the Email & Document Ingestion System",
    no_args_is_help=True,
    rich_markup_mode="rich"
)

# Create subcommands for better organization
labels_app = typer.Typer(
    name="labels",
    help="Gmail label management commands",
    no_args_is_help=True
)

watch_app = typer.Typer(
    name="watch", 
    help="Gmail watch (push notifications) commands",
    no_args_is_help=True
)

metrics_app = typer.Typer(
    name="metrics",
    help="System metrics and reporting commands", 
    no_args_is_help=True
)

# Add sub-applications to main app
app.add_typer(labels_app, name="labels")
app.add_typer(watch_app, name="watch") 
app.add_typer(metrics_app, name="metrics")


@app.command()
def run_api(
    host: str = typer.Option(settings.HOST, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(settings.PORT, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(settings.DEBUG, "--reload", help="Enable auto-reload")
):
    """Run the FastAPI server."""
    logger.info(f"Starting API server on {host}:{port}")

    try:
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=reload,
            log_config=None  # Use our own logging
        )
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        raise typer.Exit(1)


@app.command()
def run_worker(
    concurrency: int = typer.Option(
        settings.MAX_CONCURRENT_TASKS,
        "--concurrency",
        "-c",
        help="Number of worker processes"
    ),
    loglevel: str = typer.Option("info", "--loglevel", "-l", help="Logging level"),
    queues: str = typer.Option(
        "default,email_ingestion,document_processing",
        "--queues",
        "-q",
        help="Comma-separated list of queues to consume from"
    )
):
    """Run a Celery worker."""
    logger.info(f"Starting Celery worker with concurrency={concurrency}")
    logger.info(f"Queues: {queues}")

    try:
        cmd = [
            "celery",
            "-A", "workers.celery_app",
            "worker",
            f"--concurrency={concurrency}",
            f"--loglevel={loglevel}",
            f"--queues={queues}",
            "--prefetch-multiplier=1",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
            "--task-events",
        ]

        subprocess.run(cmd)
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {e}")
        raise typer.Exit(1)


@app.command()
def run_beat(
    loglevel: str = typer.Option("info", "--loglevel", "-l", help="Logging level")
):
    """Run Celery beat scheduler."""
    logger.info("Starting Celery beat scheduler")
    logger.info(f"Log level: {loglevel}")

    try:
        cmd = [
            "celery",
            "-A", "workers.celery_app",
            "beat",
            f"--loglevel={loglevel}"
        ]

        subprocess.run(cmd)
    except Exception as e:
        logger.error(f"Failed to start Celery beat: {e}")
        raise typer.Exit(1)


@app.command()
def celery_status():
    """Check Celery status and configuration."""
    logger.info("Checking Celery status and configuration")

    try:
        from workers.celery_app import celery_app
        from config.celery_config import get_celery_environment_info

        # Print configuration info
        env_info = get_celery_environment_info()
        typer.echo("=== Celery Configuration ===")
        typer.echo(f"Broker: {env_info['broker_url']}")
        typer.echo(f"Backend: {env_info['result_backend']}")
        typer.echo(f"Timezone: {env_info['timezone']}")
        typer.echo(f"Queues: {', '.join(env_info['queues'])}")
        typer.echo(f"Concurrency: {env_info['concurrency']}")
        typer.echo("")

        typer.echo("=== Scheduled Tasks ===")
        for task_name in env_info['scheduled_tasks']:
            task_config = celery_app.conf.beat_schedule[task_name]
            typer.echo(f"{task_name}: {task_config['task']} ({task_config['schedule']})")
        typer.echo("")

        # Test broker connection
        typer.echo("=== Connection Test ===")
        try:
            # Simple broker connection test
            connection = celery_app.broker_connection()
            connection.ensure_connection(max_retries=3)
            typer.secho("✓ Broker connection successful", fg=typer.colors.GREEN)
            connection.close()
        except Exception as e:
            typer.secho(f"✗ Broker connection failed: {e}", fg=typer.colors.RED)

    except Exception as e:
        logger.error(f"Failed to check Celery status: {e}")
        raise typer.Exit(1)


@app.command()
def create_migration(
    message: str = typer.Argument(..., help="Migration message")
):
    """Create a new Alembic migration."""
    logger.info(f"Creating migration: {message}")

    try:
        cmd = [
            "alembic",
            "revision",
            "--autogenerate",
            "-m", message
        ]

        subprocess.run(cmd)
    except Exception as e:
        logger.error(f"Failed to create migration: {e}")
        raise typer.Exit(1)


@app.command()
def migrate(
    revision: str = typer.Argument("head", help="Revision to migrate to")
):
    """Run database migrations."""
    logger.info(f"Running migrations to {revision}")

    try:
        cmd = ["alembic", "upgrade", revision]
        subprocess.run(cmd)
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise typer.Exit(1)


@app.command()
def rollback(
    revision: str = typer.Argument("-1", help="Revision to rollback to")
):
    """Rollback database migrations."""
    logger.info(f"Rolling back migrations to {revision}")

    try:
        cmd = ["alembic", "downgrade", revision]
        subprocess.run(cmd)
    except Exception as e:
        logger.error(f"Failed to rollback migrations: {e}")
        raise typer.Exit(1)


@app.command()
def test(
    path: Optional[str] = typer.Argument(None, help="Path to tests"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    coverage: bool = typer.Option(False, "--coverage", help="Generate coverage report")
):
    """Run tests."""
    logger.info("Running tests")

    try:
        cmd = ["python", "-m", "pytest"]
        if path:
            cmd.append(path)
        if verbose:
            cmd.append("-v")
        if coverage:
            cmd.extend(["--cov=./", "--cov-report=html"])

        subprocess.run(cmd)
    except Exception as e:
        logger.error(f"Failed to run tests: {e}")
        raise typer.Exit(1)


@app.command()
def lint():
    """Run linting tools."""
    logger.info("Running linting tools")

    try:
        # Run flake8
        logger.info("Running flake8...")
        subprocess.run(["flake8", "."])

        # Run mypy
        logger.info("Running mypy...")
        subprocess.run(["mypy", "."])

        # Run black check
        logger.info("Running black check...")
        subprocess.run(["black", "--check", "."])

        # Run isort check
        logger.info("Running isort check...")
        subprocess.run(["isort", "--check-only", "."])

    except Exception as e:
        logger.error(f"Linting failed: {e}")
        raise typer.Exit(1)


@app.command()
def format():
    """Format code with black and isort."""
    logger.info("Formatting code")

    try:
        # Run black
        logger.info("Running black...")
        subprocess.run(["black", "."])

        # Run isort
        logger.info("Running isort...")
        subprocess.run(["isort", "."])

    except Exception as e:
        logger.error(f"Code formatting failed: {e}")
        raise typer.Exit(1)


@app.command()
def setup():
    """Set up the development environment."""
    logger.info("Setting up development environment")

    try:
        # Create .env file if it doesn't exist
        env_file = Path(".env")
        if not env_file.exists():
            logger.info("Creating .env file from template...")
            subprocess.run(["cp", ".env.example", ".env"])
            logger.info("Created .env file. Please edit it with your configuration.")

        # Install pre-commit hooks
        logger.info("Installing pre-commit hooks...")
        subprocess.run(["pre-commit", "install"])

        # Run migrations
        logger.info("Running database migrations...")
        migrate()

        logger.info("Development environment setup complete!")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        raise typer.Exit(1)


@app.command()
def clean():
    """Clean up generated files and cache."""
    logger.info("Cleaning up generated files")

    try:
        # Remove Python cache
        subprocess.run(["find", ".", "-type", "d", "-name", "__pycache__", "-exec", "rm", "-rf", "{}", "+"])
        subprocess.run(["find", ".", "-type", "f", "-name", "*.pyc", "-delete"])
        subprocess.run(["find", ".", "-type", "f", "-name", "*.pyo", "-delete"])
        subprocess.run(["find", ".", "-type", "f", "-name", "*.pyd", "-delete"])

        # Remove test cache
        subprocess.run(["find", ".", "-type", "d", "-name", ".pytest_cache", "-exec", "rm", "-rf", "{}", "+"])

        # Remove coverage files
        subprocess.run(["find", ".", "-type", "f", "-name", ".coverage", "-delete"])
        subprocess.run(["rm", "-rf", "htmlcov"])

        # Remove mypy cache
        subprocess.run(["rm", "-rf", ".mypy_cache"])

        logger.info("Cleanup complete!")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise typer.Exit(1)


@app.command()
def dev():
    """Start development environment with API and worker."""
    logger.info("Starting development environment")

    typer.echo("Starting development environment...")
    typer.echo("API will be available at: http://localhost:8000")
    typer.echo("API docs will be available at: http://localhost:8000/docs")
    typer.echo("Press Ctrl+C to stop")

    # You can extend this to start both API and worker
    # For now, just provide instructions
    typer.echo("\nTo start the services:")
    typer.echo("1. Terminal 1: python cli.py run-api")
    typer.echo("2. Terminal 2: python cli.py run-worker")


@app.command()
def ocr_process(
    document_path: str = typer.Argument(..., help="Path to document to process"),
    document_id: int = typer.Option(..., "--document-id", help="Database document ID"),
    workflow: str = typer.Option("azure_primary", "--workflow", help="Workflow configuration"),
    async_mode: bool = typer.Option(False, "--async", help="Run asynchronously"),
    timeout: int = typer.Option(1800, "--timeout", help="Timeout in seconds")
):
    """Process a document through the OCR workflow."""
    from cli_ocr_workflow import process_document
    import click
    
    # Create a Click context to run the command
    ctx = click.Context(process_document)
    ctx.params = {
        'document_path': document_path,
        'document_id': document_id,
        'workflow': workflow,
        'async_mode': async_mode,
        'timeout': timeout,
        'config_override': None
    }
    
    try:
        ctx.invoke(process_document, **ctx.params)
    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        raise typer.Exit(1)


@app.command()
def ocr_config(
    workflow: str = typer.Option("azure_primary", "--workflow", help="Workflow to show config for")
):
    """Show OCR workflow configuration."""
    from cli_ocr_workflow import show_config
    import click
    
    ctx = click.Context(show_config)
    ctx.params = {'workflow': workflow}
    
    try:
        ctx.invoke(show_config, **ctx.params)
    except Exception as e:
        logger.error(f"Failed to show config: {e}")
        raise typer.Exit(1)


@app.command()
def ocr_status(
    task_id: str = typer.Argument(..., help="Task ID to check status for")
):
    """Check OCR workflow task status."""
    from cli_ocr_workflow import check_status
    import click
    
    ctx = click.Context(check_status)
    ctx.params = {'task_id': task_id}
    
    try:
        ctx.invoke(check_status, **ctx.params)
    except Exception as e:
        logger.error(f"Failed to check status: {e}")
        raise typer.Exit(1)


@app.command()
def ocr_test(
    document_path: str = typer.Argument(..., help="Path to document to test"),
    engines: str = typer.Option("azure,google,tesseract", "--engines", help="Engines to test"),
    timeout: int = typer.Option(300, "--timeout", help="Timeout per engine")
):
    """Test multiple OCR engines on a document."""
    from cli_ocr_workflow import test_engines
    import click
    
    ctx = click.Context(test_engines)
    ctx.params = {
        'document_path': document_path,
        'engines': engines,
        'timeout': timeout
    }
    
    try:
        ctx.invoke(test_engines, **ctx.params)
    except Exception as e:
        logger.error(f"Engine testing failed: {e}")
        raise typer.Exit(1)


@app.command()
def backfill(
    user_id: str = typer.Argument(..., help="User ID for Gmail authentication"),
    start_date: str = typer.Argument(..., help="Start date for backfill (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)"),
    end_date: Optional[str] = typer.Argument(None, help="End date for backfill (default: now)"),
    labels: str = typer.Option("", "--labels", "-l", help="Comma-separated list of label names or IDs to process"),
    max_messages: int = typer.Option(1000, "--max-messages", "-m", help="Maximum number of messages to process"),
    batch_size: int = typer.Option(50, "--batch-size", "-b", help="Number of messages to process in each batch"),
    process_attachments: bool = typer.Option(True, "--process-attachments/--no-attachments", help="Process email attachments"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be processed without actually doing it"),
    query: str = typer.Option("", "--query", "-q", help="Additional Gmail search query to apply")
):
    """Backfill historical emails from Gmail for a specific time range.
    
    This command fetches and processes historical emails from Gmail within the specified date range.
    It supports filtering by labels, limiting the number of messages, and provides progress reporting.
    
    Examples:
    - Backfill last 30 days: python cli.py backfill user123 2024-01-01
    - Backfill specific range: python cli.py backfill user123 2024-01-01 2024-01-31
    - Backfill with labels: python cli.py backfill user123 2024-01-01 --labels "INBOX,Important"
    - Dry run: python cli.py backfill user123 2024-01-01 --dry-run
    """
    from datetime import datetime, timezone
    from workers.tasks.email_ingestion import backfill_historical_emails
    from utils.date_utils import parse_date_range, validate_date_range
    
    try:
        logger.info(f"Starting backfill for user {user_id}")
        
        # Parse and validate date range
        start_dt, end_dt = parse_date_range(start_date, end_date)
        validate_date_range(start_dt, end_dt, max_messages)
        
        # Parse labels
        label_list = [label.strip() for label in labels.split(",") if label.strip()] if labels else []
        
        # Show configuration
        typer.echo(f"Backfill Configuration:")
        typer.echo(f"  User ID: {user_id}")
        typer.echo(f"  Date Range: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        typer.echo(f"  Labels: {', '.join(label_list) if label_list else 'All'}")
        typer.echo(f"  Max Messages: {max_messages}")
        typer.echo(f"  Batch Size: {batch_size}")
        typer.echo(f"  Process Attachments: {process_attachments}")
        typer.echo(f"  Additional Query: {query or 'None'}")
        typer.echo(f"  Dry Run: {dry_run}")
        typer.echo("")
        
        if dry_run:
            typer.echo("DRY RUN MODE - No actual processing will occur")
            # In dry run mode, we would estimate what would be processed
            typer.echo("Would start backfill task with these parameters")
            return
        
        if not typer.confirm("Do you want to proceed with the backfill?"):
            typer.echo("Backfill cancelled")
            return
        
        # Start backfill task
        logger.info("Starting backfill task")
        backfill_task = backfill_historical_emails.delay(
            user_id=user_id,
            start_date=start_dt,
            end_date=end_dt,
            labels=label_list,
            max_messages=max_messages,
            batch_size=batch_size,
            process_attachments=process_attachments,
            additional_query=query
        )
        
        typer.secho(f"✓ Backfill task started successfully!", fg=typer.colors.GREEN)
        typer.echo(f"Task ID: {backfill_task.id}")
        typer.echo(f"Monitor progress with: python cli.py backfill-status {backfill_task.id}")
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        typer.secho(f"✗ Backfill failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def backfill_status(
    task_id: str = typer.Argument(..., help="Backfill task ID to check status for"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Continuously monitor progress"),
    refresh_interval: int = typer.Option(5, "--interval", "-i", help="Refresh interval in seconds (when following)")
):
    """Check the status and progress of a backfill operation.
    
    Examples:
    - Check status once: python cli.py backfill-status abc123-def456
    - Follow progress: python cli.py backfill-status abc123-def456 --follow
    """
    import time
    from celery.result import AsyncResult
    from workers.celery_app import celery_app
    
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        def display_status():
            state = task_result.state
            info = task_result.info
            
            typer.echo(f"Task ID: {task_id}")
            typer.echo(f"Status: {state}")
            
            if state == 'PENDING':
                typer.echo("Task is waiting to be processed...")
            elif state == 'PROGRESS':
                if isinstance(info, dict):
                    progress = info.get('progress', 0) * 100
                    message = info.get('message', 'Processing...')
                    typer.echo(f"Progress: {progress:.1f}% - {message}")
                    
                    # Show detailed stats if available
                    if 'messages_fetched' in info:
                        typer.echo(f"Messages Fetched: {info['messages_fetched']}")
                    if 'messages_processed' in info:
                        typer.echo(f"Messages Processed: {info['messages_processed']}")
                    if 'documents_created' in info:
                        typer.echo(f"Documents Created: {info['documents_created']}")
                    if 'errors_count' in info:
                        typer.echo(f"Errors: {info['errors_count']}")
                else:
                    typer.echo(f"Progress: {info}")
            elif state == 'SUCCESS':
                typer.secho("✓ Backfill completed successfully!", fg=typer.colors.GREEN)
                if isinstance(info, dict):
                    typer.echo(f"Total Messages Processed: {info.get('total_processed', 'Unknown')}")
                    typer.echo(f"Total Documents Created: {info.get('total_documents', 'Unknown')}")
                    typer.echo(f"Duration: {info.get('duration_seconds', 'Unknown')} seconds")
                else:
                    typer.echo(f"Result: {info}")
            elif state == 'FAILURE':
                typer.secho("✗ Backfill failed!", fg=typer.colors.RED)
                if isinstance(info, dict):
                    typer.echo(f"Error: {info.get('error', 'Unknown error')}")
                else:
                    typer.echo(f"Error: {info}")
            else:
                typer.echo(f"State: {state}")
                typer.echo(f"Info: {info}")
        
        if follow:
            typer.echo("Following backfill progress (Press Ctrl+C to stop)...")
            typer.echo("=" * 50)
            
            try:
                while True:
                    display_status()
                    
                    # Check if task is complete
                    if task_result.state in ['SUCCESS', 'FAILURE']:
                        break
                    
                    typer.echo("-" * 50)
                    time.sleep(refresh_interval)
                    
            except KeyboardInterrupt:
                typer.echo("\nStopped following progress")
        else:
            display_status()
            
    except Exception as e:
        logger.error(f"Failed to check backfill status: {e}")
        typer.secho(f"✗ Failed to check status: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def backfill_list(
    user_id: Optional[str] = typer.Option(None, "--user", "-u", help="Filter by user ID"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status (PENDING, PROGRESS, SUCCESS, FAILURE)"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of recent tasks to show")
):
    """List recent backfill tasks and their status.
    
    Examples:
    - List all recent backfills: python cli.py backfill-list
    - List for specific user: python cli.py backfill-list --user user123
    - List failed tasks: python cli.py backfill-list --status FAILURE
    """
    from celery import current_app
    from celery.app.control import Inspect
    from workers.celery_app import celery_app
    
    try:
        inspector = Inspect(app=celery_app)
        
        # Get active tasks
        active_tasks = inspector.active()
        scheduled_tasks = inspector.scheduled()
        
        typer.echo("Recent Backfill Tasks:")
        typer.echo("=" * 60)
        
        all_tasks = []
        
        # Collect active tasks
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    if task.get('name', '').endswith('backfill_historical_emails'):
                        task_info = {
                            'id': task['id'],
                            'name': task['name'],
                            'status': 'ACTIVE',
                            'worker': worker
                        }
                        all_tasks.append(task_info)
        
        # Collect scheduled tasks
        if scheduled_tasks:
            for worker, tasks in scheduled_tasks.items():
                for task in tasks:
                    if task.get('name', '').endswith('backfill_historical_emails'):
                        task_info = {
                            'id': task['id'],
                            'name': task['name'],
                            'status': 'SCHEDULED',
                            'worker': worker
                        }
                        all_tasks.append(task_info)
        
        # Apply filters
        if user_id:
            all_tasks = [task for task in all_tasks if user_id in str(task.get('args', []))]
        
        if status:
            all_tasks = [task for task in all_tasks if task['status'] == status]
        
        # Limit results
        all_tasks = all_tasks[:limit]
        
        if not all_tasks:
            typer.echo("No backfill tasks found matching criteria")
            return
        
        # Display tasks
        for task in all_tasks:
            typer.echo(f"Task ID: {task['id']}")
            typer.echo(f"Status: {task['status']}")
            typer.echo(f"Worker: {task['worker']}")
            typer.echo("-" * 40)
            
    except Exception as e:
        logger.error(f"Failed to list backfill tasks: {e}")
        typer.secho(f"✗ Failed to list tasks: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def reprocess_document(
    document_id: int = typer.Argument(..., help="Database ID of the document to reprocess", min=1),
    ocr_engine: Optional[str] = typer.Option(None, "--engine", "-e", help="Specific OCR engine to use (e.g., 'azure', 'google', 'tesseract')"),
    workflow: str = typer.Option("azure_primary", "--workflow", "-w", help="Workflow configuration name"),
    priority: str = typer.Option("normal", "--priority", "-p", help="Processing priority (high, normal, low)"),
    wait: bool = typer.Option(False, "--wait", help="Wait for reprocessing to complete"),
    timeout: int = typer.Option(3600, "--timeout", help="Timeout in seconds when waiting", min=1, max=36000)
):
    """Reprocess a document with OCR.

    This command allows reprocessing a specific document with optional
    OCR engine selection for comparison or forced reprocessing.

    Examples:
        python cli.py reprocess-document 123 --engine azure
        python cli.py reprocess-document 456 --workflow google_primary --wait
        python cli.py reprocess-document 789 --engine tesseract --priority high
    """
    try:
        import uuid
        import time
        from workers.tasks.ocr_workflow import reprocess_document_ocr

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Validate inputs
        valid_engines = ['azure', 'google', 'tesseract', 'mistral', 'easyocr']
        if ocr_engine and ocr_engine not in valid_engines:
            typer.secho(f"Error: Invalid OCR engine '{ocr_engine}'. Valid engines: {', '.join(valid_engines)}", fg=typer.colors.RED)
            raise typer.Exit(1)

        valid_priorities = ['high', 'normal', 'low']
        if priority not in valid_priorities:
            typer.secho(f"Error: Invalid priority '{priority}'. Valid priorities: {', '.join(valid_priorities)}", fg=typer.colors.RED)
            raise typer.Exit(1)

        logger.info(
            "Starting document reprocessing via CLI",
            job_id=job_id,
            document_id=document_id,
            ocr_engine=ocr_engine,
            workflow=workflow,
            priority=priority
        )

        # Validate document exists
        from models.database import get_db_session
        from models.email import Document

        with get_db_session() as db:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                typer.secho(f"Error: Document {document_id} not found", fg=typer.colors.RED)
                raise typer.Exit(1)

            if not document.storage_path:
                typer.secho(f"Error: Document {document_id} has no valid storage path", fg=typer.colors.RED)
                raise typer.Exit(1)

        # Prepare workflow overrides if OCR engine is specified
        workflow_overrides = None
        if ocr_engine:
            workflow_overrides = {
                "primary_engine": {"engine_name": ocr_engine},
                "fallback_engines": []  # Disable fallbacks if specific engine requested
            }

        typer.secho(f"Queueing document {document_id} for reprocessing...", fg=typer.colors.BLUE)

        # Queue the reprocessing task
        task = reprocess_document_ocr.delay(
            job_id=job_id,
            document_id=document_id,
            workflow_config_name=workflow,
            workflow_overrides=workflow_overrides,
            priority=priority
        )

        typer.secho(f"Document reprocessing job queued successfully!", fg=typer.colors.GREEN)
        typer.echo(f"Job ID: {job_id}")
        typer.echo(f"Task ID: {task.id}")

        if wait:
            typer.secho(f"Waiting for reprocessing to complete (timeout: {timeout}s)...", fg=typer.colors.YELLOW)

            start_time = time.time()
            while time.time() - start_time < timeout:
                # Check if task is complete
                if task.ready():
                    result = task.result
                    if task.successful():
                        typer.secho("Document reprocessing completed successfully!", fg=typer.colors.GREEN)
                        typer.echo(f"Result: {result}")
                    else:
                        typer.secho("Document reprocessing failed!", fg=typer.colors.RED)
                        typer.echo(f"Error: {result}")
                    return

                time.sleep(2)  # Check every 2 seconds

            typer.secho(f"Timeout reached after {timeout} seconds", fg=typer.colors.YELLOW)
            typer.echo("Reprocessing may still be running in the background")

    except Exception as e:
        logger.error(
            "Document reprocessing failed",
            document_id=document_id,
            error=str(e)
        )
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def reprocess_email(
    email_id: int = typer.Argument(..., help="Database ID of the email to reprocess"),
    ocr_engine: Optional[str] = typer.Option(None, "--engine", "-e", help="Specific OCR engine to use for attachments"),
    workflow: str = typer.Option("azure_primary", "--workflow", "-w", help="Workflow configuration name for OCR"),
    process_attachments: bool = typer.Option(True, "--attachments/--no-attachments", help="Whether to reprocess attachments"),
    priority: str = typer.Option("normal", "--priority", "-p", help="Processing priority (high, normal, low)"),
    wait: bool = typer.Option(False, "--wait", help="Wait for reprocessing to complete"),
    timeout: int = typer.Option(3600, "--timeout", help="Timeout in seconds when waiting")
):
    """Reprocess an email and its attachments.

    This command allows reprocessing a specific email, including re-extracting
    attachments and reprocessing them with OCR if requested.

    Examples:
        python cli.py reprocess-email 123 --engine azure
        python cli.py reprocess-email 456 --no-attachments
        python cli.py reprocess-email 789 --engine tesseract --workflow custom_config --wait
    """
    try:
        import uuid
        import time
        from workers.tasks.email_ingestion import reprocess_email_ingestion

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Validate inputs
        valid_engines = ['azure', 'google', 'tesseract', 'mistral', 'easyocr']
        if ocr_engine and ocr_engine not in valid_engines:
            typer.secho(f"Error: Invalid OCR engine '{ocr_engine}'. Valid engines: {', '.join(valid_engines)}", fg=typer.colors.RED)
            raise typer.Exit(1)

        valid_priorities = ['high', 'normal', 'low']
        if priority not in valid_priorities:
            typer.secho(f"Error: Invalid priority '{priority}'. Valid priorities: {', '.join(valid_priorities)}", fg=typer.colors.RED)
            raise typer.Exit(1)

        logger.info(
            "Starting email reprocessing via CLI",
            job_id=job_id,
            email_id=email_id,
            ocr_engine=ocr_engine,
            process_attachments=process_attachments,
            workflow=workflow,
            priority=priority
        )

        # Validate email exists
        from models.database import get_db_session
        from models.email import Email

        with get_db_session() as db:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                typer.secho(f"Error: Email {email_id} not found", fg=typer.colors.RED)
                raise typer.Exit(1)

        typer.secho(f"Queueing email {email_id} for reprocessing...", fg=typer.colors.BLUE)

        # Queue the reprocessing task
        task = reprocess_email_ingestion.delay(
            job_id=job_id,
            email_id=email_id,
            ocr_engine=ocr_engine,
            workflow_config_name=workflow,
            process_attachments=process_attachments,
            priority=priority
        )

        typer.secho(f"Email reprocessing job queued successfully!", fg=typer.colors.GREEN)
        typer.echo(f"Job ID: {job_id}")
        typer.echo(f"Task ID: {task.id}")

        if wait:
            typer.secho(f"Waiting for reprocessing to complete (timeout: {timeout}s)...", fg=typer.colors.YELLOW)

            start_time = time.time()
            while time.time() - start_time < timeout:
                # Check if task is complete
                if task.ready():
                    result = task.result
                    if task.successful():
                        typer.secho("Email reprocessing completed successfully!", fg=typer.colors.GREEN)
                        typer.echo(f"Result: {result}")
                    else:
                        typer.secho("Email reprocessing failed!", fg=typer.colors.RED)
                        typer.echo(f"Error: {result}")
                    return

                time.sleep(2)  # Check every 2 seconds

            typer.secho(f"Timeout reached after {timeout} seconds", fg=typer.colors.YELLOW)
            typer.echo("Reprocessing may still be running in the background")

    except Exception as e:
        logger.error(
            "Email reprocessing failed",
            email_id=email_id,
            error=str(e)
        )
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def reprocess_status(
    job_id: str = typer.Argument(..., help="Job ID to check status for")
):
    """Check the status of a reprocessing job.

    Examples:
        python cli.py reprocess-status 123e4567-e89b-12d3-a456-426614174000
    """
    try:
        from celery.result import AsyncResult
        from workers.celery_app import celery_app

        # Get task result
        task_result = AsyncResult(job_id, app=celery_app)

        if task_result.state == 'PENDING':
            typer.secho(f"Job {job_id} is pending", fg=typer.colors.YELLOW)
        elif task_result.state == 'PROGRESS':
            progress_info = task_result.info
            progress = progress_info.get('progress', 0) * 100
            message = progress_info.get('message', 'Processing...')
            typer.secho(f"Job {job_id} is in progress: {message} ({progress:.1f}%)", fg=typer.colors.BLUE)
        elif task_result.state == 'SUCCESS':
            typer.secho(f"Job {job_id} completed successfully", fg=typer.colors.GREEN)
            result = task_result.result
            typer.echo(f"Result: {result}")
        elif task_result.state == 'FAILURE':
            typer.secho(f"Job {job_id} failed", fg=typer.colors.RED)
            typer.echo(f"Error: {task_result.info}")
        else:
            typer.secho(f"Job {job_id} is in state: {task_result.state}", fg=typer.colors.CYAN)

    except Exception as e:
        logger.error(f"Failed to get reprocessing status for job {job_id}: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@labels_app.command("list")
def labels_list(
    user_id: str = typer.Argument(..., help="User ID for Gmail authentication"),
    label_type: str = typer.Option("all", "--type", "-t", help="Filter by label type (user, system, all)"),
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table, json, csv)"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Save output to file")
):
    """List all Gmail labels for a user.
    
    This command retrieves and displays all Gmail labels for the specified user,
    with options to filter by type and format the output.
    
    Examples:
        python cli.py labels list user123
        python cli.py labels list user123 --type user --format json
        python cli.py labels list user123 --output labels.csv --format csv
    """
    try:
        from services.gmail_service import get_gmail_service
        import json
        import csv
        from io import StringIO

        logger.info(f"Listing Gmail labels for user: {user_id}")
        
        # Get Gmail service
        gmail_service = get_gmail_service()
        
        # Retrieve labels
        labels = gmail_service.list_labels(user_id)
        if labels is None:
            typer.secho("Failed to retrieve labels. Check authentication and user ID.", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        # Filter by type if specified
        if label_type != "all":
            labels = [label for label in labels if label.get('type', 'user') == label_type]
        
        if not labels:
            typer.secho("No labels found matching criteria.", fg=typer.colors.YELLOW)
            return
        
        logger.info(f"Found {len(labels)} labels")
        
        # Format output
        if format_type == "json":
            output = json.dumps(labels, indent=2)
        elif format_type == "csv":
            output_buffer = StringIO()
            writer = csv.DictWriter(output_buffer, fieldnames=['id', 'name', 'type', 'labelListVisibility', 'messageListVisibility'])
            writer.writeheader()
            for label in labels:
                writer.writerow({
                    'id': label.get('id', ''),
                    'name': label.get('name', ''),
                    'type': label.get('type', 'user'),
                    'labelListVisibility': label.get('labelListVisibility', ''),
                    'messageListVisibility': label.get('messageListVisibility', '')
                })
            output = output_buffer.getvalue()
        else:  # table format
            typer.echo(f"\nGmail Labels for {user_id}:")
            typer.echo("=" * 80)
            typer.echo(f"{'ID':<20} {'Name':<30} {'Type':<10} {'Visibility':<15}")
            typer.echo("-" * 80)
            for label in labels:
                label_id = label.get('id', '')[:18] + '..' if len(label.get('id', '')) > 20 else label.get('id', '')
                name = label.get('name', '')[:28] + '..' if len(label.get('name', '')) > 30 else label.get('name', '')
                label_type_val = label.get('type', 'user')
                visibility = label.get('labelListVisibility', '')[:13] + '..' if len(label.get('labelListVisibility', '')) > 15 else label.get('labelListVisibility', '')
                typer.echo(f"{label_id:<20} {name:<30} {label_type_val:<10} {visibility:<15}")
            
            typer.echo(f"\nTotal: {len(labels)} labels")
            output = None
        
        # Save to file if specified
        if output_file and output:
            with open(output_file, 'w') as f:
                f.write(output)
            typer.secho(f"Output saved to {output_file}", fg=typer.colors.GREEN)
        elif output:
            typer.echo(output)
            
    except Exception as e:
        logger.error(f"Failed to list labels for user {user_id}: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@labels_app.command("ensure")
def labels_ensure(
    user_id: str = typer.Argument(..., help="User ID for Gmail authentication"),
    label_name: str = typer.Argument(..., help="Name of the label to ensure exists"),
    bg_color: Optional[str] = typer.Option(None, "--bg-color", help="Background color (hex format, e.g. #ff0000)"),
    text_color: Optional[str] = typer.Option(None, "--text-color", help="Text color (hex format, e.g. #ffffff)"),
    list_visibility: str = typer.Option("labelShow", "--list-visibility", help="Label list visibility (labelShow, labelHide)"),
    message_visibility: str = typer.Option("show", "--message-visibility", help="Message list visibility (show, hide)")
):
    """Ensure a Gmail label exists, creating it if necessary.
    
    This command checks if a label exists and creates it if it doesn't.
    You can specify custom colors and visibility settings.
    
    Examples:
        python cli.py labels ensure user123 "Important Documents"
        python cli.py labels ensure user123 "Urgent" --bg-color "#ff0000" --text-color "#ffffff"
        python cli.py labels ensure user123 "Archive" --list-visibility labelHide
    """
    try:
        from services.gmail_service import get_gmail_service

        logger.info(f"Ensuring label '{label_name}' exists for user: {user_id}")
        
        # Validate inputs
        if list_visibility not in ["labelShow", "labelHide"]:
            typer.secho("Error: list-visibility must be 'labelShow' or 'labelHide'", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        if message_visibility not in ["show", "hide"]:
            typer.secho("Error: message-visibility must be 'show' or 'hide'", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        # Validate color formats if provided
        if bg_color and not (bg_color.startswith('#') and len(bg_color) == 7):
            typer.secho("Error: bg-color must be in hex format (e.g., #ff0000)", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        if text_color and not (text_color.startswith('#') and len(text_color) == 7):
            typer.secho("Error: text-color must be in hex format (e.g., #ffffff)", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        # Get Gmail service
        gmail_service = get_gmail_service()
        
        # Prepare color settings if provided
        color_settings = {}
        if bg_color or text_color:
            color_settings['color'] = {}
            if bg_color:
                color_settings['color']['backgroundColor'] = bg_color
            if text_color:
                color_settings['color']['textColor'] = text_color
        
        # Add visibility settings
        if list_visibility != "labelShow":
            color_settings['labelListVisibility'] = list_visibility
        if message_visibility != "show":
            color_settings['messageListVisibility'] = message_visibility
        
        # Ensure label exists
        label_result = gmail_service.ensure_label_exists(
            user_id,
            label_name,
            color_settings if color_settings else None
        )
        
        if label_result:
            if 'id' in label_result:
                typer.secho(f"✓ Label '{label_name}' is ready!", fg=typer.colors.GREEN)
                typer.echo(f"  ID: {label_result['id']}")
                typer.echo(f"  Name: {label_result['name']}")
                typer.echo(f"  Type: {label_result.get('type', 'user')}")
                if 'color' in label_result:
                    typer.echo(f"  Background Color: {label_result['color'].get('backgroundColor', 'default')}")
                    typer.echo(f"  Text Color: {label_result['color'].get('textColor', 'default')}")
            else:
                typer.secho(f"✓ Label '{label_name}' exists", fg=typer.colors.GREEN)
        else:
            typer.secho(f"✗ Failed to ensure label '{label_name}' exists", fg=typer.colors.RED)
            raise typer.Exit(1)
            
    except Exception as e:
        logger.error(f"Failed to ensure label '{label_name}' for user {user_id}: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@labels_app.command("assign")
def labels_assign(
    user_id: str = typer.Argument(..., help="User ID for Gmail authentication"),
    message_ids: str = typer.Argument(..., help="Comma-separated list of Gmail message IDs"),
    label_names: str = typer.Argument(..., help="Comma-separated list of label names or IDs to assign"),
    remove_labels: str = typer.Option("", "--remove", "-r", help="Comma-separated list of label names/IDs to remove"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without actually doing it"),
    batch_size: int = typer.Option(50, "--batch-size", help="Number of messages to process at once"),
    wait_between_batches: float = typer.Option(0.5, "--wait", help="Wait time between batches in seconds")
):
    """Assign labels to Gmail messages.
    
    This command adds and/or removes labels from specified Gmail messages.
    It supports batch processing for better performance with many messages.
    
    Examples:
        python cli.py labels assign user123 "msg_001,msg_002" "Important,Work"
        python cli.py labels assign user123 "msg_001" "Processed" --remove "INBOX,UNREAD"
        python cli.py labels assign user123 "msg_001,msg_002,msg_003" "Archive" --dry-run
    """
    try:
        from services.gmail_service import get_gmail_service
        import time

        # Parse inputs
        message_id_list = [mid.strip() for mid in message_ids.split(",") if mid.strip()]
        label_name_list = [label.strip() for label in label_names.split(",") if label.strip()]
        remove_label_list = [label.strip() for label in remove_labels.split(",") if label.strip()] if remove_labels else []
        
        if not message_id_list:
            typer.secho("Error: No message IDs provided", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        if not label_name_list and not remove_label_list:
            typer.secho("Error: No labels to assign or remove", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        logger.info(f"Processing {len(message_id_list)} messages for user: {user_id}")
        
        # Show configuration
        typer.echo(f"Label Assignment Configuration:")
        typer.echo(f"  User ID: {user_id}")
        typer.echo(f"  Messages: {len(message_id_list)}")
        typer.echo(f"  Labels to Add: {', '.join(label_name_list) if label_name_list else 'None'}")
        typer.echo(f"  Labels to Remove: {', '.join(remove_label_list) if remove_label_list else 'None'}")
        typer.echo(f"  Batch Size: {batch_size}")
        typer.echo(f"  Dry Run: {dry_run}")
        typer.echo("")
        
        if dry_run:
            typer.secho("DRY RUN MODE - No actual changes will be made", fg=typer.colors.YELLOW)
            for i, msg_id in enumerate(message_id_list):
                typer.echo(f"  Would process message {i+1}: {msg_id}")
                if label_name_list:
                    typer.echo(f"    - Add labels: {', '.join(label_name_list)}")
                if remove_label_list:
                    typer.echo(f"    - Remove labels: {', '.join(remove_label_list)}")
            return
        
        if not typer.confirm("Do you want to proceed with the label assignment?"):
            typer.echo("Label assignment cancelled")
            return
        
        # Get Gmail service
        gmail_service = get_gmail_service()
        
        # Process in batches
        total_successful = 0
        total_failed = 0
        
        for i in range(0, len(message_id_list), batch_size):
            batch = message_id_list[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(message_id_list) + batch_size - 1) // batch_size
            
            typer.echo(f"Processing batch {batch_num}/{total_batches} ({len(batch)} messages)...")
            
            # Add labels if specified
            if label_name_list:
                result = gmail_service.assign_labels_to_messages(user_id, batch, label_name_list)
                total_successful += result.get('successful', 0)
                total_failed += result.get('failed', 0)
                
                if result.get('errors'):
                    for error in result['errors']:
                        typer.secho(f"  Warning: {error}", fg=typer.colors.YELLOW)
            
            # Remove labels if specified
            if remove_label_list:
                for message_id in batch:
                    for label_name in remove_label_list:
                        success = gmail_service.remove_label_from_message(user_id, message_id, label_name)
                        if success:
                            total_successful += 1
                        else:
                            total_failed += 1
                            typer.secho(f"  Failed to remove '{label_name}' from {message_id}", fg=typer.colors.YELLOW)
            
            # Wait between batches if not the last batch
            if i + batch_size < len(message_id_list):
                time.sleep(wait_between_batches)
        
        # Summary
        typer.echo(f"\nLabel Assignment Summary:")
        typer.secho(f"  ✓ Successful operations: {total_successful}", fg=typer.colors.GREEN)
        if total_failed > 0:
            typer.secho(f"  ✗ Failed operations: {total_failed}", fg=typer.colors.RED)
        else:
            typer.secho(f"  ✗ Failed operations: {total_failed}", fg=typer.colors.GREEN)
        
        if total_failed > 0:
            typer.secho("Some operations failed. Check the logs for details.", fg=typer.colors.YELLOW)
            
    except Exception as e:
        logger.error(f"Failed to assign labels for user {user_id}: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@watch_app.command("start")
def watch_start(
    user_id: str = typer.Argument(..., help="User ID for Gmail authentication"),
    topic_name: str = typer.Option("gmail-notifications", "--topic", "-t", help="Pub/Sub topic name"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Google Cloud project ID (default: from environment)"),
    label_ids: str = typer.Option("INBOX", "--labels", "-l", help="Comma-separated list of label IDs to watch"),
    duration_days: int = typer.Option(7, "--duration", "-d", help="Watch duration in days (max 7)", min=1, max=7),
    push_endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="HTTPS endpoint for push notifications"),
    subscription_name: Optional[str] = typer.Option(None, "--subscription", "-s", help="Pub/Sub subscription name (for push endpoint)"),
    setup_infrastructure: bool = typer.Option(True, "--setup-infra/--no-setup-infra", help="Set up Pub/Sub infrastructure automatically")
):
    """Start Gmail watch for push notifications.
    
    This command sets up Gmail push notifications for the specified user and labels.
    It can automatically create the necessary Pub/Sub infrastructure if needed.
    
    Examples:
        python cli.py watch start user123
        python cli.py watch start user123 --topic my-topic --project my-project
        python cli.py watch start user123 --labels "INBOX,IMPORTANT" --duration 3
        python cli.py watch start user123 --endpoint https://myapp.com/gmail/webhook --subscription gmail-sub
    """
    try:
        from services.gmail_service import get_gmail_service
        from services.gmail_watch_config import get_gmail_watch_config
        import os

        logger.info(f"Starting Gmail watch for user: {user_id}")
        
        # Parse label IDs
        label_id_list = [label.strip() for label in label_ids.split(",") if label.strip()]
        
        # Get project ID
        if not project_id:
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
            if not project_id:
                typer.secho("Error: No project ID provided. Use --project or set GOOGLE_CLOUD_PROJECT environment variable", fg=typer.colors.RED)
                raise typer.Exit(1)
        
        # Show configuration
        typer.echo(f"Gmail Watch Configuration:")
        typer.echo(f"  User ID: {user_id}")
        typer.echo(f"  Project ID: {project_id}")
        typer.echo(f"  Topic Name: {topic_name}")
        typer.echo(f"  Label IDs: {', '.join(label_id_list)}")
        typer.echo(f"  Duration: {duration_days} days")
        typer.echo(f"  Push Endpoint: {push_endpoint or 'None (topic only)'}")
        typer.echo(f"  Setup Infrastructure: {setup_infrastructure}")
        typer.echo("")
        
        if not typer.confirm("Do you want to start Gmail watch with this configuration?"):
            typer.echo("Watch setup cancelled")
            return
        
        # Get services
        gmail_service = get_gmail_service()
        watch_config = get_gmail_watch_config(project_id=project_id)
        
        # Set up infrastructure if requested
        if setup_infrastructure:
            typer.echo("Setting up Pub/Sub infrastructure...")
            
            if push_endpoint and subscription_name:
                # Full infrastructure setup with push subscription
                infrastructure = watch_config.setup_gmail_watch_infrastructure(
                    topic_name=topic_name,
                    subscription_name=subscription_name,
                    push_endpoint=push_endpoint
                )
                typer.secho(f"✓ Infrastructure created:", fg=typer.colors.GREEN)
                typer.echo(f"  Topic: {infrastructure['topic']}")
                typer.echo(f"  Subscription: {infrastructure['subscription']}")
            else:
                # Topic-only setup
                topic_path = watch_config.create_topic(topic_name)
                watch_config.grant_gmail_publisher_role(topic_name)
                typer.secho(f"✓ Topic created with permissions: {topic_path}", fg=typer.colors.GREEN)
        
        # Start Gmail watch
        full_topic_name = f"projects/{project_id}/topics/{topic_name}"
        
        typer.echo("Setting up Gmail watch...")
        watch_response = gmail_service.setup_watch_with_retry(
            user_id=user_id,
            topic_name=full_topic_name,
            label_ids=label_id_list,
            watch_duration_days=duration_days
        )
        
        if watch_response:
            typer.secho("✓ Gmail watch started successfully!", fg=typer.colors.GREEN)
            typer.echo(f"  History ID: {watch_response.get('historyId')}")
            typer.echo(f"  Expiration: {watch_response.get('expiration')}")
            
            # Validate setup
            typer.echo("Validating setup...")
            validation = watch_config.validate_topic_permissions(topic_name)
            
            if validation.get('gmail_has_publisher_role', False):
                typer.secho("✓ Topic permissions validated", fg=typer.colors.GREEN)
            else:
                typer.secho("⚠ Warning: Topic permissions validation failed", fg=typer.colors.YELLOW)
                typer.echo("  Gmail may not have proper publisher permissions")
            
            # Store watch info for future reference
            typer.echo(f"\nTo stop this watch, use:")
            typer.echo(f"  python cli.py watch-stop {user_id}")
            
        else:
            typer.secho("✗ Failed to start Gmail watch", fg=typer.colors.RED)
            typer.echo("Check logs for detailed error information")
            raise typer.Exit(1)
            
    except Exception as e:
        logger.error(f"Failed to start Gmail watch for user {user_id}: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@watch_app.command("stop")
def watch_stop(
    user_id: str = typer.Argument(..., help="User ID for Gmail authentication"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt")
):
    """Stop Gmail watch for a user.
    
    This command stops the Gmail push notifications for the specified user.
    It only stops the watch; it does not delete Pub/Sub infrastructure.
    
    Examples:
        python cli.py watch stop user123
        python cli.py watch stop user123 --confirm
    """
    try:
        from services.gmail_service import get_gmail_service

        logger.info(f"Stopping Gmail watch for user: {user_id}")
        
        # Confirmation prompt
        if not confirm:
            typer.echo(f"This will stop Gmail watch for user: {user_id}")
            typer.echo("This action will disable push notifications but won't delete Pub/Sub infrastructure.")
            typer.echo("")
            
            if not typer.confirm("Do you want to stop Gmail watch?"):
                typer.echo("Watch stop cancelled")
                return
        
        # Get Gmail service
        gmail_service = get_gmail_service()
        
        # Stop watch
        typer.echo("Stopping Gmail watch...")
        success = gmail_service.stop_watch(user_id)
        
        if success:
            typer.secho("✓ Gmail watch stopped successfully!", fg=typer.colors.GREEN)
            typer.echo("Push notifications are now disabled for this user.")
            typer.echo("")
            typer.echo("Note: Pub/Sub topic and subscription (if any) are still active.")
            typer.echo("Use Google Cloud Console to delete them if no longer needed.")
        else:
            typer.secho("✗ Failed to stop Gmail watch", fg=typer.colors.RED)
            typer.echo("The watch may have already expired or not been active.")
            typer.echo("Check logs for detailed error information.")
            
    except Exception as e:
        logger.error(f"Failed to stop Gmail watch for user {user_id}: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@watch_app.command("status")
def watch_status(
    user_id: str = typer.Argument(..., help="User ID for Gmail authentication"),
    topic_name: Optional[str] = typer.Option(None, "--topic", "-t", help="Topic name to validate permissions"),
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Google Cloud project ID")
):
    """Check Gmail watch status and configuration.
    
    This command provides information about the current Gmail watch status
    and validates Pub/Sub topic permissions if specified.
    
    Examples:
        python cli.py watch status user123
        python cli.py watch status user123 --topic gmail-notifications --project my-project
    """
    try:
        from services.gmail_service import get_gmail_service
        from services.gmail_watch_config import get_gmail_watch_config
        import os

        logger.info(f"Checking Gmail watch status for user: {user_id}")
        
        # Get Gmail service
        gmail_service = get_gmail_service()
        
        typer.echo(f"Gmail Watch Status for {user_id}:")
        typer.echo("=" * 50)
        
        # Note: Gmail API doesn't provide a direct way to check current watch status
        # We can only try to set up a new watch and see if it fails
        typer.echo("Note: Gmail API doesn't provide direct watch status queries.")
        typer.echo("Watch status can only be determined by attempting operations.")
        typer.echo("")
        
        # If topic information is provided, validate permissions
        if topic_name:
            if not project_id:
                project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
                if not project_id:
                    typer.secho("Warning: No project ID provided for topic validation", fg=typer.colors.YELLOW)
                    return
            
            typer.echo(f"Validating topic permissions:")
            typer.echo(f"  Project: {project_id}")
            typer.echo(f"  Topic: {topic_name}")
            typer.echo("")
            
            watch_config = get_gmail_watch_config(project_id=project_id)
            validation = watch_config.validate_topic_permissions(topic_name)
            
            if validation.get('topic_exists', False):
                typer.secho("✓ Topic exists", fg=typer.colors.GREEN)
            else:
                typer.secho("✗ Topic does not exist", fg=typer.colors.RED)
            
            if validation.get('gmail_has_publisher_role', False):
                typer.secho("✓ Gmail has publisher permissions", fg=typer.colors.GREEN)
            else:
                typer.secho("✗ Gmail missing publisher permissions", fg=typer.colors.RED)
                typer.echo("  Run: python cli.py watch-start --setup-infra to fix")
            
            if 'error' in validation:
                typer.secho(f"⚠ Validation error: {validation['error']}", fg=typer.colors.YELLOW)
        
        typer.echo("")
        typer.echo("To start a new watch, use:")
        typer.echo(f"  python cli.py watch-start {user_id}")
        typer.echo("")
        typer.echo("To stop current watch, use:")
        typer.echo(f"  python cli.py watch-stop {user_id}")
            
    except Exception as e:
        logger.error(f"Failed to check Gmail watch status for user {user_id}: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@metrics_app.command("dump")
def metrics_dump(
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: metrics_YYYYMMDD_HHMMSS.json)"),
    format_type: str = typer.Option("json", "--format", "-f", help="Output format (json, csv, yaml)"),
    include_system: bool = typer.Option(True, "--system/--no-system", help="Include system-wide metrics"),
    include_engines: bool = typer.Option(True, "--engines/--no-engines", help="Include per-engine metrics"),
    include_database: bool = typer.Option(True, "--database/--no-database", help="Include database performance stats"),
    engine_filter: str = typer.Option("", "--engine", "-e", help="Filter by specific OCR engine"),
    days: int = typer.Option(7, "--days", "-d", help="Number of days for database stats", min=1, max=365),
    pretty: bool = typer.Option(True, "--pretty/--compact", help="Pretty print JSON output")
):
    """Dump comprehensive system metrics to file or stdout.
    
    This command exports detailed metrics about OCR performance, system health,
    and database statistics. It supports multiple output formats and filtering options.
    
    Examples:
        python cli.py metrics dump
        python cli.py metrics dump --output metrics.json --pretty
        python cli.py metrics dump --format csv --output metrics.csv
        python cli.py metrics dump --engine azure --days 30
        python cli.py metrics dump --no-system --engine tesseract
    """
    try:
        from utils.metrics import get_metrics_collector
        from services.ocr_query_service import OCRQueryService
        from models.database import get_db_session
        from datetime import datetime
        import json
        import csv
        import yaml
        from io import StringIO

        logger.info("Generating metrics dump")
        
        # Validate format
        if format_type not in ["json", "csv", "yaml"]:
            typer.secho("Error: format must be 'json', 'csv', or 'yaml'", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        # Generate default filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = format_type
            output_file = f"metrics_{timestamp}.{extension}"
        
        typer.echo(f"Generating metrics dump...")
        typer.echo(f"  Format: {format_type}")
        typer.echo(f"  Output: {output_file}")
        typer.echo(f"  Engine Filter: {engine_filter or 'All'}")
        typer.echo(f"  Database Stats Days: {days}")
        typer.echo("")
        
        # Collect metrics
        metrics_data = {
            "generated_at": datetime.now().isoformat(),
            "format": format_type,
            "filters": {
                "engine": engine_filter or None,
                "days": days
            }
        }
        
        # Get in-memory metrics
        if include_system or include_engines:
            collector = get_metrics_collector()
            
            if include_system:
                typer.echo("Collecting system metrics...")
                metrics_data["system"] = collector.get_system_metrics()
            
            if include_engines:
                typer.echo("Collecting engine metrics...")
                if engine_filter:
                    engine_metrics = collector.get_ocr_metrics(engine_filter)
                else:
                    engine_metrics = collector.get_ocr_metrics()
                metrics_data["engines"] = engine_metrics
        
        # Get database performance stats
        if include_database:
            typer.echo("Collecting database performance stats...")
            try:
                with get_db_session() as db:
                    ocr_query_service = OCRQueryService(db)
                    
                    # Get overall stats
                    overall_stats = ocr_query_service.get_ocr_performance_stats(days=days)
                    metrics_data["database"] = {
                        "overall_stats": overall_stats
                    }
                    
                    # Get per-engine stats if not filtering
                    if not engine_filter:
                        engine_stats = {}
                        for engine in ["azure", "google", "tesseract", "mistral", "easyocr"]:
                            try:
                                stats = ocr_query_service.get_ocr_performance_stats(days=days, ocr_engine=engine)
                                if stats.get("total_runs", 0) > 0:
                                    engine_stats[engine] = stats
                            except Exception as e:
                                logger.warning(f"Failed to get stats for engine {engine}: {e}")
                        
                        if engine_stats:
                            metrics_data["database"]["engine_stats"] = engine_stats
                    else:
                        # Get stats for specific engine
                        engine_stats = ocr_query_service.get_ocr_performance_stats(days=days, ocr_engine=engine_filter)
                        metrics_data["database"]["engine_stats"] = {engine_filter: engine_stats}
                        
            except Exception as e:
                logger.warning(f"Failed to collect database stats: {e}")
                metrics_data["database"] = {"error": str(e)}
        
        # Format output
        if format_type == "json":
            if pretty:
                output_content = json.dumps(metrics_data, indent=2, default=str)
            else:
                output_content = json.dumps(metrics_data, default=str)
        
        elif format_type == "yaml":
            try:
                output_content = yaml.dump(metrics_data, default_flow_style=False, indent=2)
            except ImportError:
                typer.secho("Error: PyYAML is required for YAML output. Install with: pip install PyYAML", fg=typer.colors.RED)
                raise typer.Exit(1)
        
        elif format_type == "csv":
            # Flatten metrics for CSV output
            output_buffer = StringIO()
            writer = csv.writer(output_buffer)
            
            # Write header
            writer.writerow(["metric_type", "metric_name", "value", "engine", "timestamp"])
            
            # Write system metrics
            if "system" in metrics_data:
                for key, value in metrics_data["system"].items():
                    writer.writerow(["system", key, value, "", metrics_data["generated_at"]])
            
            # Write engine metrics
            if "engines" in metrics_data:
                for engine, engine_data in metrics_data["engines"].items():
                    for key, value in engine_data.items():
                        writer.writerow(["engine", key, value, engine, metrics_data["generated_at"]])
            
            # Write database metrics
            if "database" in metrics_data and "overall_stats" in metrics_data["database"]:
                for key, value in metrics_data["database"]["overall_stats"].items():
                    writer.writerow(["database", key, value, "", metrics_data["generated_at"]])
            
            if "database" in metrics_data and "engine_stats" in metrics_data["database"]:
                for engine, engine_data in metrics_data["database"]["engine_stats"].items():
                    for key, value in engine_data.items():
                        writer.writerow(["database_engine", key, value, engine, metrics_data["generated_at"]])
            
            output_content = output_buffer.getvalue()
        
        # Write to file
        try:
            with open(output_file, 'w') as f:
                f.write(output_content)
            
            typer.secho(f"✓ Metrics dump saved to {output_file}", fg=typer.colors.GREEN)
            
            # Show summary
            typer.echo(f"\nMetrics Summary:")
            if "system" in metrics_data:
                typer.echo(f"  System metrics: {len(metrics_data['system'])} items")
            if "engines" in metrics_data:
                typer.echo(f"  Engine metrics: {len(metrics_data['engines'])} engines")
            if "database" in metrics_data:
                if "overall_stats" in metrics_data["database"]:
                    overall = metrics_data["database"]["overall_stats"]
                    typer.echo(f"  Database stats: {overall.get('total_runs', 0)} runs over {days} days")
                if "engine_stats" in metrics_data["database"]:
                    typer.echo(f"  Per-engine DB stats: {len(metrics_data['database']['engine_stats'])} engines")
            
            # Show file size
            import os
            file_size = os.path.getsize(output_file)
            if file_size > 1024 * 1024:
                typer.echo(f"  File size: {file_size / (1024 * 1024):.1f} MB")
            elif file_size > 1024:
                typer.echo(f"  File size: {file_size / 1024:.1f} KB")
            else:
                typer.echo(f"  File size: {file_size} bytes")
                
        except Exception as e:
            typer.secho(f"✗ Failed to write to {output_file}: {e}", fg=typer.colors.RED)
            typer.echo("Outputting to stdout instead:")
            typer.echo(output_content)
            
    except Exception as e:
        logger.error(f"Failed to generate metrics dump: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@metrics_app.command("summary")
def metrics_summary():
    """Show a quick summary of current system metrics.
    
    This command provides a quick overview of system performance without
    generating a full dump. Useful for quick health checks.
    
    Examples:
        python cli.py metrics summary
    """
    try:
        from utils.metrics import get_metrics_collector

        logger.info("Generating metrics summary")
        
        # Get metrics collector
        collector = get_metrics_collector()
        
        # Get system metrics
        system_metrics = collector.get_system_metrics()
        ocr_metrics = collector.get_ocr_metrics()
        
        typer.echo("System Metrics Summary")
        typer.echo("=" * 50)
        
        # System overview
        typer.echo(f"Total Requests: {system_metrics.get('total_requests', 0)}")
        typer.echo(f"Success Rate: {system_metrics.get('overall_success_rate', 0)}%")
        typer.echo(f"Total Cost: ${system_metrics.get('total_cost_cents', 0)/100:.2f}")
        typer.echo(f"Active Engines: {system_metrics.get('engines_count', 0)}")
        typer.echo(f"Last Updated: {system_metrics.get('last_updated', 'Unknown')}")
        typer.echo("")
        
        # Per-engine summary
        if ocr_metrics:
            typer.echo("Engine Performance:")
            typer.echo("-" * 30)
            for engine, metrics in ocr_metrics.items():
                if metrics.get('requests', 0) > 0:
                    typer.echo(f"{engine.upper():<12} | "
                             f"Requests: {metrics.get('requests', 0):<6} | "
                             f"Success: {metrics.get('success_rate', 0):<5.1f}% | "
                             f"Avg Latency: {metrics.get('avg_latency_ms', 0):<6.0f}ms")
        else:
            typer.echo("No engine metrics available")
            
    except Exception as e:
        logger.error(f"Failed to show metrics summary: {e}")
        typer.secho(f"Error: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def admin_help():
    """Show help for administrative commands.
    
    This command provides an overview of all available administrative
    commands organized by category.
    """
    typer.echo("[bold blue]Email & Document Ingestion System - Admin Commands[/bold blue]", markup=True)
    typer.echo("")
    
    typer.echo("[bold green]Gmail Label Management[/bold green]", markup=True)
    typer.echo("  labels list USER_ID      - List all Gmail labels")
    typer.echo("  labels ensure USER_ID LABEL_NAME - Create label if it doesn't exist") 
    typer.echo("  labels assign USER_ID MSG_IDS LABELS - Assign labels to messages")
    typer.echo("")
    
    typer.echo("[bold green]Gmail Watch (Push Notifications)[/bold green]", markup=True)
    typer.echo("  watch start USER_ID      - Start Gmail push notifications")
    typer.echo("  watch stop USER_ID       - Stop Gmail push notifications")
    typer.echo("  watch status USER_ID     - Check watch status and permissions")
    typer.echo("")
    
    typer.echo("[bold green]Email Processing[/bold green]", markup=True)
    typer.echo("  backfill USER_ID START_DATE - Backfill historical emails")
    typer.echo("  reprocess-email EMAIL_ID - Reprocess a specific email")
    typer.echo("  reprocess-document DOC_ID - Reprocess a specific document")
    typer.echo("")
    
    typer.echo("[bold green]System Metrics[/bold green]", markup=True)
    typer.echo("  metrics dump             - Export comprehensive metrics")
    typer.echo("  metrics summary          - Show quick metrics overview")
    typer.echo("")
    
    typer.echo("[bold green]System Management[/bold green]", markup=True)
    typer.echo("  run-api                  - Start the FastAPI server")
    typer.echo("  run-worker               - Start Celery worker")
    typer.echo("  celery-status            - Check Celery configuration")
    typer.echo("  migrate                  - Run database migrations")
    typer.echo("")
    
    typer.echo("Use [bold]--help[/bold] with any command for detailed options and examples.", markup=True)
    typer.echo("Example: [bold]python cli.py labels list --help[/bold]", markup=True)


if __name__ == "__main__":
    app()

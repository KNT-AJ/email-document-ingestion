"""OCR workflow CLI commands."""

import click
import json
from pathlib import Path
from typing import Optional

from workers.tasks.ocr_workflow import orchestrate_ocr_workflow
from services.ocr.workflow_config import get_default_workflow_config
from utils.logging import get_logger

logger = get_logger("cli.ocr_workflow")


@click.group()
def ocr():
    """OCR workflow management commands."""
    pass


@ocr.command()
@click.argument('document_path', type=click.Path(exists=True))
@click.option('--document-id', type=int, required=True, help='Database document ID')
@click.option('--workflow', default='azure_primary', 
              type=click.Choice(['azure_primary', 'google_primary', 'opensource']),
              help='Workflow configuration to use')
@click.option('--async-mode', is_flag=True, help='Run asynchronously (returns task ID)')
@click.option('--timeout', type=int, default=1800, help='Timeout in seconds')
@click.option('--config-override', type=str, help='JSON string with configuration overrides')
def process_document(document_path: str, document_id: int, workflow: str, 
                    async_mode: bool, timeout: int, config_override: Optional[str]):
    """Process a document through the OCR workflow.
    
    DOCUMENT_PATH: Path to the document file to process
    """
    try:
        logger.info(f"Starting OCR workflow for document {document_id}")
        
        # Parse configuration overrides if provided
        overrides = None
        if config_override:
            try:
                overrides = json.loads(config_override)
            except json.JSONDecodeError as e:
                click.echo(f"Error parsing config override JSON: {e}", err=True)
                return
        
        # Execute workflow
        if async_mode:
            # Run asynchronously
            task = orchestrate_ocr_workflow.delay(
                document_id=document_id,
                document_path=document_path,
                workflow_config_name=workflow,
                workflow_config_overrides=overrides
            )
            
            click.echo(f"OCR workflow started asynchronously")
            click.echo(f"Task ID: {task.id}")
            click.echo(f"Check status with: celery -A workers.celery_app inspect active")
            
        else:
            # Run synchronously
            click.echo(f"Processing document {document_path} with {workflow} workflow...")
            
            result = orchestrate_ocr_workflow.apply(
                args=[document_id, document_path, workflow, overrides],
                timeout=timeout
            ).get()
            
            # Display results
            click.echo("\n=== OCR Workflow Results ===")
            click.echo(f"Status: {result['status']}")
            click.echo(f"Execution ID: {result['execution_id']}")
            click.echo(f"Total Processing Time: {result['total_processing_time']:.2f} seconds")
            
            selected_result = result['selected_result']
            click.echo(f"\nSelected Engine: {selected_result['engine_name']}")
            click.echo(f"Confidence Score: {selected_result['ocr_result']['confidence_score']:.3f}")
            click.echo(f"Word Count: {selected_result['ocr_result']['word_count']}")
            click.echo(f"Page Count: {selected_result['ocr_result']['page_count']}")
            
            if result['fallback_results']:
                click.echo(f"\nFallback Engines Used: {len(result['fallback_results'])}")
                for i, fallback in enumerate(result['fallback_results'], 1):
                    if fallback.get('success'):
                        fb_result = fallback['ocr_result']
                        click.echo(f"  {i}. {fallback['engine_name']}: "
                                 f"confidence={fb_result['confidence_score']:.3f}, "
                                 f"words={fb_result['word_count']}")
            
            # Show extracted text preview
            extracted_text = selected_result['ocr_result']['extracted_text']
            if extracted_text:
                preview = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")
                click.echo(f"\nExtracted Text Preview:\n{preview}")
        
    except Exception as e:
        logger.error(f"OCR workflow failed: {e}")
        click.echo(f"Error: {e}", err=True)


@ocr.command()
@click.option('--workflow', default='azure_primary',
              type=click.Choice(['azure_primary', 'google_primary', 'opensource']),
              help='Workflow configuration to display')
def show_config(workflow: str):
    """Show the configuration for a workflow."""
    try:
        config = get_default_workflow_config(workflow)
        
        click.echo(f"=== {config.workflow_name} Configuration ===")
        click.echo(f"Workflow ID: {config.workflow_id}")
        click.echo(f"Version: {config.version}")
        
        click.echo(f"\nPrimary Engine:")
        primary = config.primary_engine
        click.echo(f"  Type: {primary.engine_type.value}")
        click.echo(f"  Name: {primary.engine_name}")
        click.echo(f"  Timeout: {primary.timeout_seconds}s")
        click.echo(f"  Preprocessing: {primary.preprocessing_enabled}")
        
        if config.fallback_engines:
            click.echo(f"\nFallback Engines ({len(config.fallback_engines)}):")
            for i, engine in enumerate(config.fallback_engines, 1):
                click.echo(f"  {i}. {engine.engine_name} ({engine.engine_type.value})")
                click.echo(f"     Timeout: {engine.timeout_seconds}s")
        
        click.echo(f"\nWorkflow Settings:")
        click.echo(f"  Stop on Success: {config.stop_on_success}")
        click.echo(f"  Parallel Fallbacks: {config.parallel_fallbacks}")
        click.echo(f"  Max Parallel Engines: {config.max_parallel_engines}")
        click.echo(f"  Result Selection: {config.result_selection_strategy}")
        click.echo(f"  Total Timeout: {config.total_workflow_timeout_seconds}s")
        
        click.echo(f"\nQuality Thresholds:")
        thresholds = config.global_quality_thresholds
        click.echo(f"  Min Confidence: {thresholds.min_confidence_score}")
        click.echo(f"  Min Word Recognition: {thresholds.min_word_recognition_rate}")
        click.echo(f"  Min Expected Fields: {thresholds.min_expected_fields_detected}")
        click.echo(f"  Max Processing Time: {thresholds.max_processing_time_seconds}s")
        
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)


@ocr.command()
@click.argument('task_id', type=str)
def check_status(task_id: str):
    """Check the status of an asynchronous OCR workflow task."""
    try:
        from workers.celery_app import celery_app
        
        # Get task result
        result = celery_app.AsyncResult(task_id)
        
        click.echo(f"Task ID: {task_id}")
        click.echo(f"Status: {result.status}")
        
        if result.status == 'PENDING':
            click.echo("Task is waiting to be processed")
        elif result.status == 'PROGRESS':
            info = result.info
            if isinstance(info, dict):
                progress = info.get('progress', 0)
                message = info.get('message', 'Processing...')
                click.echo(f"Progress: {progress:.1f}%")
                click.echo(f"Message: {message}")
        elif result.status == 'SUCCESS':
            click.echo("Task completed successfully")
            workflow_result = result.get()
            selected_result = workflow_result['selected_result']
            click.echo(f"Selected Engine: {selected_result['engine_name']}")
            click.echo(f"Confidence: {selected_result['ocr_result']['confidence_score']:.3f}")
            click.echo(f"Word Count: {selected_result['ocr_result']['word_count']}")
        elif result.status == 'FAILURE':
            click.echo(f"Task failed: {result.info}")
        else:
            click.echo(f"Unknown status: {result.status}")
            
    except Exception as e:
        click.echo(f"Error checking task status: {e}", err=True)


@ocr.command()
@click.argument('document_path', type=click.Path(exists=True))
@click.option('--engines', default='azure,google,tesseract',
              help='Comma-separated list of engines to test')
@click.option('--timeout', type=int, default=300, help='Timeout per engine')
def test_engines(document_path: str, engines: str, timeout: int):
    """Test multiple OCR engines on a document for comparison."""
    try:
        from services.ocr.workflow_config import EngineConfig, OCREngineType
        from services.ocr.workflow_engine import create_ocr_engine
        import time
        
        engine_names = [name.strip() for name in engines.split(',')]
        results = []
        
        click.echo(f"Testing OCR engines on {document_path}")
        click.echo(f"Engines: {', '.join(engine_names)}")
        click.echo("=" * 50)
        
        for engine_name in engine_names:
            try:
                # Map engine name to type
                engine_type_map = {
                    'azure': OCREngineType.AZURE,
                    'google': OCREngineType.GOOGLE,
                    'tesseract': OCREngineType.TESSERACT,
                    'paddle': OCREngineType.PADDLE,
                    'mistral': OCREngineType.MISTRAL,
                    'textract': OCREngineType.TEXTRACT
                }
                
                if engine_name not in engine_type_map:
                    click.echo(f"Unknown engine: {engine_name}")
                    continue
                
                click.echo(f"\nTesting {engine_name}...")
                start_time = time.time()
                
                # Create engine config
                config = EngineConfig(
                    engine_type=engine_type_map[engine_name],
                    engine_name=f"{engine_name.title()} OCR",
                    timeout_seconds=timeout
                )
                
                # Create and run engine
                engine = create_ocr_engine(config)
                result = engine.process_document(Path(document_path))
                
                processing_time = time.time() - start_time
                
                # Evaluate quality
                meets_quality, evaluation = engine.evaluate_quality(result)
                
                results.append({
                    'engine': engine_name,
                    'result': result,
                    'processing_time': processing_time,
                    'meets_quality': meets_quality,
                    'evaluation': evaluation
                })
                
                click.echo(f"✓ {engine_name}: confidence={result.confidence_score:.3f}, "
                         f"words={result.word_count}, time={processing_time:.1f}s")
                
            except Exception as e:
                click.echo(f"✗ {engine_name}: Failed - {e}")
        
        # Summary comparison
        if results:
            click.echo("\n" + "=" * 50)
            click.echo("COMPARISON SUMMARY")
            click.echo("=" * 50)
            
            # Sort by confidence score
            results.sort(key=lambda x: x['result'].confidence_score, reverse=True)
            
            for i, result_data in enumerate(results, 1):
                result = result_data['result']
                quality_status = "✓" if result_data['meets_quality'] else "✗"
                
                click.echo(f"{i}. {result_data['engine'].upper()}")
                click.echo(f"   Confidence: {result.confidence_score:.3f} {quality_status}")
                click.echo(f"   Words: {result.word_count}")
                click.echo(f"   Processing Time: {result_data['processing_time']:.1f}s")
                click.echo(f"   Quality Score: {result_data['evaluation']['quality_score']:.3f}")
                click.echo()
            
            # Show best result text preview
            best_result = results[0]['result']
            preview = best_result.extracted_text[:300] + ("..." if len(best_result.extracted_text) > 300 else "")
            click.echo(f"Best Result Text Preview ({results[0]['engine']}):")
            click.echo(preview)
        
    except Exception as e:
        click.echo(f"Error during engine testing: {e}", err=True)


if __name__ == '__main__':
    ocr()

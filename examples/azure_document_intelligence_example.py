#!/usr/bin/env python3
"""Example usage of Azure Document Intelligence OCR service."""

import asyncio
from pathlib import Path
from services.ocr.service import OCRService
from services.ocr.factory import get_ocr_service
from services.ocr.config import get_ocr_config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Demonstrate Azure Document Intelligence OCR service usage."""

    # Check configuration
    config = get_ocr_config()
    if not config.is_azure_configured():
        logger.error(
            "Azure Document Intelligence is not configured. "
            "Please set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_API_KEY "
            "environment variables."
        )
        return

    # Initialize OCR service
    try:
        ocr_service = OCRService(service_type="azure")
        logger.info(f"Initialized OCR service with supported features: {ocr_service.get_supported_features()}")
    except Exception as e:
        logger.error(f"Failed to initialize OCR service: {e}")
        return

    # Example document path (you'll need to provide an actual document)
    document_path = Path("./examples/sample_document.pdf")  # Replace with actual document

    if not document_path.exists():
        logger.error(f"Sample document not found: {document_path}")
        logger.info("Please provide a PDF or image file to test with.")
        return

    # Example 1: Basic text extraction
    try:
        logger.info("=== Example 1: Basic Text Extraction ===")
        text = ocr_service.extract_text(document_path)
        logger.info(f"Extracted text (first 500 chars): {text[:500]}...")

    except Exception as e:
        logger.error(f"Text extraction failed: {e}")

    # Example 2: Table extraction
    try:
        logger.info("=== Example 2: Table Extraction ===")
        tables = ocr_service.extract_tables(document_path)
        logger.info(f"Found {len(tables)} tables")
        for i, table in enumerate(tables):
            logger.info(f"Table {i+1}: {table['row_count']} rows, {table['column_count']} columns")

    except Exception as e:
        logger.error(f"Table extraction failed: {e}")

    # Example 3: Key-value pair extraction
    try:
        logger.info("=== Example 3: Key-Value Pair Extraction ===")
        kv_pairs = ocr_service.extract_key_value_pairs(document_path)
        logger.info(f"Found {len(kv_pairs)} key-value pairs")
        for kv in kv_pairs[:5]:  # Show first 5
            key = kv['key']['content'] if kv['key']['content'] else "N/A"
            value = kv['value']['content'] if kv['value']['content'] else "N/A"
            logger.info(f"  {key}: {value}")

    except Exception as e:
        logger.error(f"Key-value pair extraction failed: {e}")

    # Example 4: Comprehensive analysis
    try:
        logger.info("=== Example 4: Comprehensive Analysis ===")
        result = ocr_service.process_document_comprehensive(document_path)

        logger.info(f"Analysis completed!")
        logger.info(f"Pages: {result['metrics']['page_count']}")
        logger.info(f"Words: {result['metrics']['word_count']}")
        logger.info(f"Tables: {result['metrics']['table_count']}")
        logger.info(f"Key-Value Pairs: {result['metrics']['key_value_pair_count']}")
        logger.info(f"Average Confidence: {result['metrics']['average_confidence']:.2f}")

        if result['raw_response_blob_path']:
            logger.info(f"Raw response stored at: {result['raw_response_blob_path']}")

    except Exception as e:
        logger.error(f"Comprehensive analysis failed: {e}")


def direct_service_example():
    """Example using the service directly without the high-level wrapper."""

    logger.info("=== Direct Service Example ===")

    try:
        # Get the service directly from factory
        azure_service = get_ocr_service("azure")

        # Use the service directly
        document_path = Path("./examples/sample_document.pdf")

        if document_path.exists():
            result = azure_service.analyze_document(document_path)
            logger.info(f"Direct analysis result: {len(result.get('text', ''))} characters extracted")
        else:
            logger.info("No sample document found for direct service test")

    except Exception as e:
        logger.error(f"Direct service example failed: {e}")


if __name__ == "__main__":
    logger.info("Azure Document Intelligence OCR Service Example")
    logger.info("=" * 50)

    main()
    logger.info("")
    direct_service_example()

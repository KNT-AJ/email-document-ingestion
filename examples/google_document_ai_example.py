#!/usr/bin/env python3
"""Example script demonstrating Google Document AI integration."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.ocr_engines import GoogleDocumentAIOCREngine, OCREngineFactory, OCREngineType
from services.blob_storage.local_storage import LocalBlobStorage
from config import get_settings


def main():
    """Main function to demonstrate Google Document AI usage."""

    print("Google Document AI Example")
    print("=" * 40)

    # Check environment configuration
    settings = get_settings()

    if not settings.GOOGLE_CREDENTIALS_PATH:
        print("❌ GOOGLE_CREDENTIALS_PATH not configured")
        print("Please set the GOOGLE_CREDENTIALS_PATH environment variable")
        return

    if not settings.GOOGLE_DOCUMENT_AI_ENDPOINT:
        print("❌ GOOGLE_DOCUMENT_AI_ENDPOINT not configured")
        print("Please set the GOOGLE_DOCUMENT_AI_ENDPOINT environment variable")
        return

    # Initialize storage service (optional)
    storage_service = LocalBlobStorage(base_path="./data/blob_storage")

    try:
        # Method 1: Direct service usage
        print("\n1. Using GoogleDocumentAIOCREngine directly:")
        engine = GoogleDocumentAIOCREngine(storage_service=storage_service)

        # Check engine health
        health = engine.health_check()
        print(f"   Health status: {health.get('status', 'unknown')}")

        if health.get('status') == 'healthy':
            print(f"   Processor: {health.get('processor_name', 'unknown')}")
            print("   ✅ Engine is ready!")
        else:
            print(f"   ❌ Engine not ready: {health.get('error', 'unknown error')}")
            return

        # Method 2: Using factory
        print("\n2. Using OCREngineFactory:")
        factory_engine = OCREngineFactory.create_engine(
            OCREngineType.GOOGLE_DOCUMENT_AI,
            storage_service=storage_service
        )

        # Get engine info
        engine_info = factory_engine.get_engine_info()
        print(f"   Engine: {engine_info['display_name']}")
        print(f"   Description: {engine_info['description']}")
        print(f"   Supported formats: {', '.join(engine_info['supported_formats'])}")

        # Example document processing (would need an actual document)
        print("\n3. Document processing example:")
        print("   To process a document, you would call:")
        print("   result = engine.process_document(")
        print("       document_path='/path/to/document.pdf',")
        print("       mime_type='application/pdf',")
        print("       document_id='example_doc_001'")
        print("   )")
        print("   ")
        print("   The result would contain:")
        print("   - extracted_text: Full text content")
        print("   - confidence_score: Processing confidence (0.0-1.0)")
        print("   - pages_count: Number of pages")
        print("   - word_count: Number of words extracted")
        print("   - tables: Extracted table data")
        print("   - key_value_pairs: Extracted entities")
        print("   - raw_response_path: Path to stored raw API response")

        print("\n✅ Google Document AI integration example completed!")
        print("\nTo use with actual documents:")
        print("1. Ensure your Google Cloud credentials are properly configured")
        print("2. Set up a Document AI processor in Google Cloud Console")
        print("3. Update environment variables with correct paths")
        print("4. Call engine.process_document() with a document file")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

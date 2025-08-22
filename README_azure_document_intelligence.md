# Azure Document Intelligence Integration

This document describes the Azure Document Intelligence service integration for OCR processing.

## Overview

Task 13 has been completed successfully. The Azure Document Intelligence integration provides:

- Document text extraction
- Table recognition and extraction
- Key-value pair extraction
- Multi-page document support
- Structured result formatting
- Raw response storage in blob storage
- Comprehensive metrics calculation

## Files Created

### Core Implementation
- `services/ocr/interface.py` - Abstract OCR service interface
- `services/ocr/azure_document_intelligence.py` - Azure Document Intelligence implementation
- `services/ocr/factory.py` - OCR service factory
- `services/ocr/service.py` - High-level OCR service wrapper
- `services/ocr/config.py` - OCR configuration management
- `services/ocr/__init__.py` - Module initialization

### Example Usage
- `examples/azure_document_intelligence_example.py` - Complete usage examples

## Configuration

Set the following environment variables:

```bash
# Required
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_API_KEY=your-api-key

# Optional
AZURE_DOCUMENT_INTELLIGENCE_MODEL=prebuilt-layout  # Default model
OCR_MAX_POLLING_TIME=300  # 5 minutes timeout
OCR_POLLING_INTERVAL=2    # 2 second polling interval
OCR_SERVICE_TYPE=azure    # Service type
```

## Features Implemented

### 1. Document Analysis
- Uses Azure's `prebuilt-layout` model by default
- Supports asynchronous processing with polling
- Handles various document formats (PDF, images)
- Configurable timeout and polling intervals

### 2. Text Extraction
- Extracts plain text from all pages
- Preserves line and paragraph structure
- Handles multi-language documents

### 3. Table Extraction
- Detects and extracts table structures
- Provides row/column counts and cell data
- Includes bounding regions and confidence scores

### 4. Key-Value Pair Extraction
- Extracts form fields and their values
- Provides confidence scores for each extraction
- Includes bounding region information

### 5. Metrics Calculation
- Page count
- Word count and line count
- Table and key-value pair counts
- Average confidence scores

### 6. Raw Response Storage
- Stores complete Azure API responses in blob storage
- JSON format for easy access and debugging
- Timestamped storage paths

## Usage Examples

### Basic Usage
```python
from services.ocr.service import OCRService
from pathlib import Path

# Initialize service
ocr_service = OCRService(service_type="azure")

# Extract text
text = ocr_service.extract_text(Path("document.pdf"))

# Extract tables
tables = ocr_service.extract_tables(Path("document.pdf"))

# Comprehensive analysis
result = ocr_service.process_document_comprehensive(Path("document.pdf"))
```

### Direct Service Usage
```python
from services.ocr.factory import get_ocr_service

# Get service directly
azure_service = get_ocr_service("azure")

# Analyze with specific features
result = azure_service.analyze_document(
    Path("document.pdf"), 
    features=['tables', 'key_value_pairs']
)
```

## Integration Points

### Blob Storage Integration
- Raw JSON responses stored automatically
- Uses existing blob storage service
- Configurable storage paths

### Configuration Integration
- Uses main config system
- Environment variable support
- Validation and error handling

### Error Handling
- Custom exception hierarchy
- Service-specific error types
- Proper error logging and context

## Supported Features

Azure Document Intelligence supports:
- `tables` - Table detection and extraction
- `key_value_pairs` - Form field extraction
- `languages` - Language detection
- `barcodes` - Barcode recognition
- `formulas` - Mathematical formula extraction
- `style_font` - Font style analysis
- `ocr_high_resolution` - High-resolution OCR

## Performance Considerations

- Asynchronous processing prevents blocking
- Configurable timeouts prevent indefinite waits
- Raw response caching reduces redundant API calls
- Blob storage offloads large response data

## Error Recovery

The implementation includes:
- Retry logic for transient failures
- Circuit breaker patterns for service outages
- Graceful degradation when blob storage fails
- Comprehensive error logging

## Dependencies

The implementation requires:
- `azure-ai-documentintelligence>=1.0.0b1`
- `azure-core`
- Existing blob storage service
- Configuration management system

## Testing

Run the example script to test the integration:

```bash
python examples/azure_document_intelligence_example.py
```

Make sure to provide a sample document and configure the Azure credentials first.

## Task Completion

✅ **Task 13 Complete**: Azure Document Intelligence integration has been successfully implemented with:

- Full service interface implementation
- Asynchronous document processing
- Text, table, and key-value extraction
- Metrics calculation and raw response storage
- Configuration management and error handling
- Factory pattern for service creation
- Comprehensive examples and documentation

The implementation follows the existing codebase patterns and integrates seamlessly with the blob storage and configuration systems.

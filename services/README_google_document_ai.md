# Google Document AI Integration

This document describes the Google Document AI integration for the Data Ingestion MVP project.

## Overview

The Google Document AI service provides advanced OCR capabilities using Google's cloud-based document processing technology. It can extract text, tables, forms, and entities from various document types including PDFs and images.

## Features

- **Text Extraction**: Extract plain text from documents with high accuracy
- **Table Detection**: Identify and extract structured data from tables
- **Entity Recognition**: Extract key-value pairs and named entities
- **Layout Analysis**: Understand document structure and formatting
- **Multi-format Support**: Process PDFs, images (JPEG, PNG, TIFF)
- **Metrics Collection**: Track confidence scores, processing times, and word counts
- **Raw Response Storage**: Store complete API responses for debugging and analysis

## Setup Instructions

### 1. Google Cloud Project Setup

1. **Create a Google Cloud Project**:
   ```bash
   # Visit: https://console.cloud.google.com/
   # Create a new project or select an existing one
   ```

2. **Enable the Document AI API**:
   - Go to the Google Cloud Console
   - Navigate to "APIs & Services" > "Library"
   - Search for "Document AI API"
   - Enable the API

3. **Create a Document AI Processor**:
   - Go to Document AI in the Cloud Console
   - Create a new processor
   - Choose the appropriate processor type (e.g., "Form Parser", "Document OCR")
   - Note the processor endpoint path

### 2. Service Account and Credentials

1. **Create a Service Account**:
   ```bash
   gcloud iam service-accounts create document-ai-service \
       --description="Service account for Document AI" \
       --display-name="Document AI Service"
   ```

2. **Grant Permissions**:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:document-ai-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/documentai.user"
   ```

3. **Download Service Account Key**:
   - Go to IAM & Admin > Service Accounts
   - Select the document-ai-service account
   - Create and download a JSON key file
   - Store securely and never commit to version control

### 3. Environment Configuration

Set the following environment variables:

```bash
# Path to the service account JSON key file
export GOOGLE_CREDENTIALS_PATH="/path/to/service-account-key.json"

# Document AI processor endpoint
export GOOGLE_DOCUMENT_AI_ENDPOINT="projects/YOUR_PROJECT_ID/locations/YOUR_LOCATION/processors/YOUR_PROCESSOR_ID"

# Example:
export GOOGLE_DOCUMENT_AI_ENDPOINT="projects/my-project-123/locations/us/processors/12345678-1234-1234-1234-123456789012"
```

Add these to your `.env` file:

```env
GOOGLE_CREDENTIALS_PATH=/path/to/service-account-key.json
GOOGLE_DOCUMENT_AI_ENDPOINT=projects/my-project-123/locations/us/processors/12345678-1234-1234-1234-123456789012
```

## Usage

### Direct Service Usage

```python
from services.ocr_engines import GoogleDocumentAIOCREngine
from services.blob_storage.local_storage import LocalBlobStorage

# Initialize with storage service (optional)
storage = LocalBlobStorage(base_path="./data/blob_storage")
engine = GoogleDocumentAIOCREngine(storage_service=storage)

# Process a document
result = engine.process_document(
    document_path="/path/to/document.pdf",
    mime_type="application/pdf",
    document_id="doc_001"
)

print(f"Extracted text: {result['extracted_text']}")
print(f"Confidence score: {result['confidence_score']}")
print(f"Pages processed: {result['pages_count']}")
```

### Factory Pattern Usage

```python
from services.ocr_engines import OCREngineFactory, OCREngineType

# Create engine using factory
engine = OCREngineFactory.create_engine(
    OCREngineType.GOOGLE_DOCUMENT_AI,
    storage_service=storage
)

# Process document
result = engine.process_document("/path/to/document.pdf")
```

### Result Structure

The `process_document` method returns a standardized result dictionary:

```python
{
    'engine_name': 'google_document_ai',
    'document_id': 'doc_001',
    'extracted_text': 'Full extracted text content...',
    'confidence_score': 0.95,  # 0.0 to 1.0
    'pages_count': 5,
    'word_count': 1250,
    'processing_time_ms': 2345,
    'tables': [
        {
            'page': 1,
            'table_number': 1,
            'data': [
                ['Header 1', 'Header 2'],
                ['Row 1 Col 1', 'Row 1 Col 2']
            ],
            'confidence': 0.92
        }
    ],
    'key_value_pairs': [
        {
            'key': 'invoice_number',
            'value': 'INV-001',
            'confidence': 0.98
        }
    ],
    'raw_response_path': 'ocr-runs/google-document-ai/doc_001/raw_response.json',
    'success': True,
    'error_message': None
}
```

## Error Handling

The service includes comprehensive error handling:

- **Authentication Errors**: Invalid credentials or permissions
- **API Errors**: Rate limits, quota exceeded, invalid requests
- **Network Errors**: Connection timeouts, DNS resolution failures
- **Processing Errors**: Invalid document format, corrupted files

### Retry Logic

The service implements exponential backoff retry logic for transient errors:

```python
# Automatic retry for rate limits and server errors
@retry_on_google_api_error(max_retries=3, initial_delay=1.0, max_delay=32.0)
def process_document(self, document_path, mime_type, document_id):
    # Processing logic...
```

### Custom Exceptions

```python
from services.google_document_ai_service import GoogleDocumentAIError

try:
    result = engine.process_document("/path/to/document.pdf")
except GoogleDocumentAIError as e:
    print(f"Document AI error: {e}")
```

## Health Monitoring

Check the service health status:

```python
health = engine.health_check()
print(f"Status: {health['status']}")
if health['status'] == 'healthy':
    print(f"Processor: {health['processor_name']}")
    print(f"State: {health['processor_state']}")
else:
    print(f"Error: {health['error']}")
```

## Testing

Run the comprehensive test suite:

```bash
# Install test dependencies
pip install pytest pytest-mock

# Run Google Document AI tests
pytest tests/unit/test_google_document_ai_service.py -v

# Run with coverage
pytest tests/unit/test_google_document_ai_service.py --cov=services.google_document_ai_service
```

### Mock Testing

For testing without actual Google Cloud credentials:

```python
import pytest
from unittest.mock import patch, Mock

@patch('google.cloud.documentai_v1.DocumentProcessorServiceClient')
def test_process_document(mock_client):
    # Mock the client and response
    mock_instance = Mock()
    mock_client.from_service_account_file.return_value = mock_instance

    # Test your service logic...
```

## Integration with OCR Orchestration

The Google Document AI service integrates seamlessly with the OCR orchestration system:

```python
# In your OCR workflow
from services.ocr_engines import OCREngineFactory, OCREngineType

# Get available engines
engines = OCREngineFactory.get_available_engines()
print("Available engines:", list(engines.keys()))

# Check if Google Document AI is available
is_available = OCREngineFactory.is_engine_available(OCREngineType.GOOGLE_DOCUMENT_AI)

if is_available:
    engine = OCREngineFactory.create_engine(OCREngineType.GOOGLE_DOCUMENT_AI)
    result = engine.process_document(document_path)
    # Process result...
```

## Cost Optimization

To optimize costs when using Google Document AI:

1. **Batch Processing**: Process multiple documents in batches
2. **Caching**: Cache results for identical documents
3. **Conditional Processing**: Only process documents that need high accuracy
4. **Fallback Strategy**: Use cheaper OCR engines first, fallback to Google Document AI only when needed

## Troubleshooting

### Common Issues

1. **"Processor not found" error**:
   - Verify the `GOOGLE_DOCUMENT_AI_ENDPOINT` is correct
   - Ensure the processor exists in your Google Cloud project
   - Check that the service account has access to the processor

2. **Authentication errors**:
   - Verify the service account key file exists and is valid
   - Check that `GOOGLE_CREDENTIALS_PATH` points to the correct file
   - Ensure the service account has the necessary permissions

3. **Quota exceeded errors**:
   - The service implements automatic retries with exponential backoff
   - Consider increasing your Document AI quota in Google Cloud
   - Implement request throttling in your application

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)

# Process document with detailed logging
result = engine.process_document(document_path, document_id="debug_doc")
```

## Performance Considerations

- **Processing Time**: Google Document AI processing time varies based on document complexity
- **File Size Limits**: Check Google Document AI documentation for file size limits
- **Concurrent Requests**: Limit concurrent requests to avoid quota issues
- **Caching**: Implement result caching for frequently processed documents

## Security Best Practices

1. **Credential Management**:
   - Store service account keys securely
   - Never commit credentials to version control
   - Use environment variables or secret management systems
   - Rotate keys regularly

2. **Access Control**:
   - Use principle of least privilege for service accounts
   - Implement proper IAM roles and permissions
   - Monitor API usage and access patterns

3. **Data Privacy**:
   - Review Google's data processing terms
   - Implement data encryption in transit and at rest
   - Consider data residency requirements

## API Reference

### GoogleDocumentAIService

Main service class for Google Document AI integration.

**Methods:**
- `__init__(storage_service=None)`: Initialize the service
- `process_document(document_path, mime_type, document_id)`: Process a document
- `health_check()`: Check service health

### GoogleDocumentAIOCREngine

OCR engine adapter for integration with orchestration system.

**Methods:**
- `process_document(document_path, mime_type, **kwargs)`: Process document with standardized interface
- `get_engine_info()`: Get engine information
- `health_check()`: Check engine health

## Support

For issues specific to Google Document AI:
- Check the [Google Document AI documentation](https://cloud.google.com/document-ai/docs)
- Review the [Python client library documentation](https://cloud.google.com/python/docs/reference/documentai/latest)
- Check [Google Cloud support](https://cloud.google.com/support) for account-specific issues

For issues with this integration:
- Review the test files for usage examples
- Check the application logs for detailed error messages
- Verify configuration and credentials

# Blob Storage Service Tests

This directory contains comprehensive tests for the blob storage service implementation as described in Task 003.

## Test Coverage

The test suite covers all requirements from Task 003:

### 1. Storage Configuration & Factory Pattern
- Configuration loading from environment variables
- Factory pattern for creating appropriate storage implementations
- Validation of storage type settings

### 2. Local Filesystem Storage Adapter
- File upload, download, existence checks, and deletion
- Path traversal attack protection
- Large file handling (10MB+)
- Empty file handling
- Error handling for filesystem operations

### 3. S3-Compatible Storage Adapter
- File operations using AWS SDK (boto3)
- Mocked S3 client for unit testing
- Error handling for S3-specific errors
- Server-side encryption support
- MinIO compatibility testing

### 4. Content-Based Hashing & Deduplication
- SHA256 hash calculation consistency
- Identical content deduplication
- Different content produces different hashes
- Empty file and large file hash calculation
- Hash retrieval for stored blobs

### 5. Retry Logic & Advanced Error Handling
- Exponential backoff retry mechanism
- Transient vs permanent error classification
- Circuit breaker pattern implementation
- Detailed error logging with context
- Network error simulation and recovery

### 6. Integration & Workflow Tests
- Complete upload/download workflows
- Concurrent operations testing
- Error recovery scenarios
- Content deduplication workflows

## Test Structure

```
tests/unit/test_storage/
├── __init__.py                 # Package initialization
├── conftest.py                 # Shared fixtures and utilities
├── pytest.ini                  # Pytest configuration
├── test_blob_storage.py        # Main test suite
├── test_integration_workflow.py # Integration tests
└── README.md                   # This file
```

## Running the Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
# From project root
pytest tests/unit/test_storage/

# With verbose output
pytest tests/unit/test_storage/ -v

# With coverage report
pytest tests/unit/test_storage/ --cov=services.storage
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/test_storage/ -m unit

# Integration tests only
pytest tests/unit/test_storage/ -m integration

# Configuration tests only
pytest tests/unit/test_storage/test_blob_storage.py::TestBlobStorageConfiguration

# Local storage tests only
pytest tests/unit/test_storage/test_blob_storage.py::TestLocalFilesystemStorage

# S3 storage tests only
pytest tests/unit/test_storage/test_blob_storage.py::TestS3BlobStorage
```

### Run Tests with Different Storage Types

```bash
# Test with local storage (default)
STORAGE_TYPE=local pytest tests/unit/test_storage/

# Test with S3 storage
STORAGE_TYPE=s3 pytest tests/unit/test_storage/
```

## Test Fixtures

The test suite includes several useful fixtures:

- `temp_storage_path`: Temporary directory for local storage tests
- `mock_s3_client`: Mocked S3 client for testing
- `sample_file_data`: Sample file content for testing
- `test_files_data`: Dictionary of various test file types
- `settings`: Pydantic settings instance
- `mock_env`: Mocked environment variables

## Mocking Strategy

### S3 Client Mocking

The tests use comprehensive S3 client mocking:

```python
mock_s3_client = MagicMock()
mock_s3_client.upload_fileobj = AsyncMock()
mock_s3_client.get_object = AsyncMock(return_value={
    'Body': io.BytesIO(b"test content")
})
```

### Error Simulation

Tests simulate various error conditions:

- Network timeouts and connection errors
- S3-specific errors (NoSuchKey, InvalidBucketName)
- Filesystem permission errors
- Disk space errors

### Retry Testing

Retry logic is tested with:

- Transient error simulation
- Permanent error handling
- Exponential backoff verification
- Circuit breaker testing

## Code Coverage

The tests aim for 80%+ code coverage including:

- Happy path scenarios
- Error conditions and edge cases
- Concurrent operations
- Large file handling
- Empty file handling
- Path traversal protection

## Test Data

Tests use various types of test data:

- Text files with different encodings
- Binary files with special characters
- Empty files
- Large files (up to 100MB)
- Unicode content
- JSON data

## Continuous Integration

The tests are designed to run in CI/CD environments:

- All dependencies are mocked where appropriate
- No external services required (except when explicitly testing integration)
- Deterministic test execution
- Proper cleanup of temporary files

## Extending the Tests

To add new tests:

1. Add test methods to the appropriate test class
2. Use existing fixtures or create new ones in `conftest.py`
3. Follow the naming convention `test_<descriptive_name>`
4. Include docstrings explaining what each test verifies
5. Add appropriate markers for categorization

Example:
```python
def test_new_feature(self, temp_storage_path):
    """Test description of what this test verifies."""
    # Test implementation
    pass
```

## Troubleshooting

### Common Issues

1. **Import Errors**: If storage services don't exist yet, tests will be skipped
2. **Permission Errors**: Ensure test directories are writable
3. **Memory Issues**: Large file tests may require sufficient RAM
4. **Async Issues**: Ensure pytest-asyncio is properly configured

### Debug Mode

Run tests with debug output:
```bash
pytest tests/unit/test_storage/ -v -s --tb=long
```

### Coverage Analysis

Generate detailed coverage report:
```bash
pytest tests/unit/test_storage/ --cov=services.storage --cov-report=html
# Open htmlcov/index.html in browser
```

"""Shared fixtures and utilities for blob storage tests."""

import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, BinaryIO, Dict, Any

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config.settings import Settings


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_env() -> Dict[str, str]:
    """Mock environment variables for testing."""
    env_vars = {
        'STORAGE_TYPE': 'local',
        'LOCAL_STORAGE_PATH': '/tmp/test_storage',
        'S3_BUCKET_NAME': 'test-bucket',
        'S3_REGION': 'us-east-1',
        'S3_ACCESS_KEY_ID': 'test-key',
        'S3_SECRET_ACCESS_KEY': 'test-secret'
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def temp_storage_path() -> AsyncGenerator[str, None]:
    """Create a temporary storage directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def settings(mock_env: Dict[str, str]) -> Settings:
    """Create settings instance with mocked environment."""
    return Settings()


@pytest.fixture
def sample_file_data() -> bytes:
    """Sample file data for testing."""
    return b"This is sample test content for blob storage testing."


@pytest.fixture
def sample_binary_data() -> bytes:
    """Sample binary data for testing."""
    return b"\x00\x01\x02\x03\xFF\xFE\xFD\xFCBinary data test"


@pytest.fixture
def large_file_data() -> bytes:
    """Large file data for testing."""
    return b"A" * (5 * 1024 * 1024)  # 5MB


@pytest.fixture
def empty_file_data() -> bytes:
    """Empty file data for testing."""
    return b""


@pytest.fixture
def mock_s3_client():
    """Create mock S3 client for testing."""
    mock_client = MagicMock()

    # Mock successful operations
    mock_client.upload_fileobj = AsyncMock()
    mock_client.get_object = AsyncMock(return_value={
        'Body': io.BytesIO(b"test content")
    })
    mock_client.head_object = AsyncMock(return_value={
        'ETag': '"test-etag"'
    })
    mock_client.delete_object = AsyncMock()

    return mock_client


@pytest.fixture
def mock_s3_client_with_errors():
    """Create mock S3 client that raises various errors."""
    mock_client = MagicMock()

    # Mock connection error (transient)
    mock_client.get_object = AsyncMock(side_effect=[
        ConnectionError("Network timeout"),
        {'Body': io.BytesIO(b"success after retry")}
    ])

    # Mock permanent error
    mock_client.head_object = AsyncMock(side_effect=[
        {'Error': {'Code': 'NoSuchKey'}},
        {'ETag': '"test-etag"'}
    ])

    return mock_client


@pytest.fixture
def test_files_data() -> Dict[str, bytes]:
    """Dictionary of test files with different types."""
    return {
        'text.txt': b"This is a text file\nWith multiple lines",
        'binary.bin': b"\x00\x01\x02\x03\xFF\xFE\xFD\xFC",
        'json.json': b'{"key": "value", "number": 123}',
        'empty.txt': b"",
        'large.bin': b"X" * (1024 * 1024),  # 1MB
        'unicode.txt': "Hello, 世界! 🌍".encode('utf-8'),
    }


@pytest.fixture
def cleanup_temp_files():
    """Cleanup utility for temporary files created during tests."""
    temp_files = []

    def track_file(filepath: str):
        temp_files.append(filepath)
        return filepath

    yield track_file

    # Cleanup
    for filepath in temp_files:
        try:
            Path(filepath).unlink(missing_ok=True)
        except Exception:
            pass


# Utility functions for tests
def create_test_file(data: bytes, filename: str, temp_dir: str) -> str:
    """Create a test file in temporary directory."""
    filepath = Path(temp_dir) / filename
    filepath.write_bytes(data)
    return str(filepath)


def read_test_file(filepath: str) -> bytes:
    """Read test file content."""
    return Path(filepath).read_bytes()


def assert_file_content(filepath: str, expected_content: bytes):
    """Assert file content matches expected."""
    actual_content = Path(filepath).read_bytes()
    assert actual_content == expected_content


def mock_boto3_client(mock_client):
    """Context manager to mock boto3 client."""
    return patch('boto3.client', return_value=mock_client)


def create_blob_id_from_content(content: bytes) -> str:
    """Create a blob ID from content (mimics SHA256 hash)."""
    import hashlib
    return hashlib.sha256(content).hexdigest()


def simulate_network_failure(attempt_number: int, success_attempt: int = 3):
    """Simulate network failure that succeeds on specific attempt."""
    if attempt_number < success_attempt:
        raise ConnectionError(f"Network failure on attempt {attempt_number}")
    return "success"

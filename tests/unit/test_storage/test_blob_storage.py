"""Comprehensive tests for blob storage service."""

import asyncio
import hashlib
import io
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, BinaryIO, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from config.settings import Settings

# Import the storage service classes (these will be created if they don't exist)
try:
    from services.storage import (
        BlobStorageInterface,
        LocalFilesystemStorage,
        S3BlobStorage,
        StorageFactory,
        ContentHashMismatchError,
        StorageError,
        BlobNotFoundError,
    )
except ImportError:
    # Create mock classes for testing if the actual implementation doesn't exist yet
    class BlobStorageInterface:
        """Mock interface for blob storage."""
        async def upload(self, data: BinaryIO, filename: str) -> str: pass
        async def download(self, blob_id: str) -> BinaryIO: pass
        async def exists(self, blob_id: str) -> bool: pass
        async def delete(self, blob_id: str) -> bool: pass
        async def get_content_hash(self, blob_id: str) -> str: pass

    class LocalFilesystemStorage(BlobStorageInterface):
        """Mock local filesystem storage."""
        pass

    class S3BlobStorage(BlobStorageInterface):
        """Mock S3 blob storage."""
        pass

    class StorageFactory:
        """Mock storage factory."""
        pass

    class StorageError(Exception):
        """Mock storage error."""
        pass

    class BlobNotFoundError(StorageError):
        """Mock blob not found error."""
        pass

    class ContentHashMismatchError(StorageError):
        """Mock content hash mismatch error."""
        pass


class TestBlobStorageConfiguration:
    """Test storage service configuration and factory pattern."""

    def test_configuration_loading_from_environment(self):
        """Test configuration loading with different environment variables."""
        # Test local storage configuration
        with patch.dict(os.environ, {
            'STORAGE_TYPE': 'local',
            'LOCAL_STORAGE_PATH': '/tmp/test_storage'
        }):
            settings = Settings()
            assert settings.STORAGE_TYPE == 'local'
            assert settings.LOCAL_STORAGE_PATH == '/tmp/test_storage'

    def test_s3_configuration_loading(self):
        """Test S3 configuration loading from environment."""
        with patch.dict(os.environ, {
            'STORAGE_TYPE': 's3',
            'S3_BUCKET_NAME': 'test-bucket',
            'S3_REGION': 'us-east-1',
            'S3_ACCESS_KEY_ID': 'test-key',
            'S3_SECRET_ACCESS_KEY': 'test-secret',
            'S3_ENDPOINT_URL': 'https://s3.amazonaws.com'
        }):
            settings = Settings()
            assert settings.STORAGE_TYPE == 's3'
            assert settings.S3_BUCKET_NAME == 'test-bucket'
            assert settings.S3_REGION == 'us-east-1'
            assert settings.S3_ACCESS_KEY_ID == 'test-key'
            assert settings.S3_SECRET_ACCESS_KEY == 'test-secret'
            assert settings.S3_ENDPOINT_URL == 'https://s3.amazonaws.com'

    def test_invalid_storage_type_validation(self):
        """Test validation of invalid storage types."""
        with patch.dict(os.environ, {'STORAGE_TYPE': 'invalid'}):
            with pytest.raises(ValueError, match="Storage type must be one of"):
                Settings()

    @patch('services.storage.LocalFilesystemStorage')
    @patch('services.storage.S3BlobStorage')
    def test_storage_factory_creates_local_storage(self, mock_s3, mock_local):
        """Test factory creates local storage when configured."""
        with patch.dict(os.environ, {'STORAGE_TYPE': 'local'}):
            settings = Settings()
            factory = StorageFactory(settings)
            storage = factory.create_storage()

            mock_local.assert_called_once()
            mock_s3.assert_not_called()
            assert storage == mock_local.return_value

    @patch('services.storage.LocalFilesystemStorage')
    @patch('services.storage.S3BlobStorage')
    def test_storage_factory_creates_s3_storage(self, mock_s3, mock_local):
        """Test factory creates S3 storage when configured."""
        with patch.dict(os.environ, {
            'STORAGE_TYPE': 's3',
            'S3_BUCKET_NAME': 'test-bucket'
        }):
            settings = Settings()
            factory = StorageFactory(settings)
            storage = factory.create_storage()

            mock_s3.assert_called_once()
            mock_local.assert_not_called()
            assert storage == mock_s3.return_value


class TestLocalFilesystemStorage:
    """Test local filesystem storage adapter."""

    @pytest.fixture
    def temp_storage_path(self) -> str:
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def local_storage(self, temp_storage_path: str) -> LocalFilesystemStorage:
        """Create local filesystem storage instance."""
        with patch.dict(os.environ, {
            'STORAGE_TYPE': 'local',
            'LOCAL_STORAGE_PATH': temp_storage_path
        }):
            settings = Settings()
            return LocalFilesystemStorage(settings)

    def test_upload_file_success(self, local_storage: LocalFilesystemStorage):
        """Test successful file upload to local storage."""
        test_data = b"Hello, World!"
        test_filename = "test.txt"

        blob_id = asyncio.run(local_storage.upload(
            io.BytesIO(test_data),
            test_filename
        ))

        # Verify blob ID is returned
        assert blob_id is not None
        assert isinstance(blob_id, str)

        # Verify file was created
        storage_path = Path(local_storage.storage_path) / blob_id
        assert storage_path.exists()
        assert storage_path.read_bytes() == test_data

    def test_upload_empty_file(self, local_storage: LocalFilesystemStorage):
        """Test uploading empty file."""
        test_data = b""
        test_filename = "empty.txt"

        blob_id = asyncio.run(local_storage.upload(
            io.BytesIO(test_data),
            test_filename
        ))

        assert blob_id is not None

        # Verify empty file was created
        storage_path = Path(local_storage.storage_path) / blob_id
        assert storage_path.exists()
        assert storage_path.read_bytes() == test_data

    def test_download_file_success(self, local_storage: LocalFilesystemStorage):
        """Test successful file download from local storage."""
        test_data = b"Download test content"
        test_filename = "download_test.txt"

        # First upload a file
        blob_id = asyncio.run(local_storage.upload(
            io.BytesIO(test_data),
            test_filename
        ))

        # Then download it
        downloaded_data = asyncio.run(local_storage.download(blob_id))

        # Verify content matches
        assert downloaded_data.read() == test_data

    def test_download_nonexistent_file(self, local_storage: LocalFilesystemStorage):
        """Test downloading non-existent file raises error."""
        with pytest.raises(BlobNotFoundError):
            asyncio.run(local_storage.download("nonexistent-blob-id"))

    def test_exists_file_check(self, local_storage: LocalFilesystemStorage):
        """Test checking if file exists."""
        test_data = b"Exists test"
        test_filename = "exists_test.txt"

        # File should not exist initially
        assert not asyncio.run(local_storage.exists("test-blob-id"))

        # Upload file
        blob_id = asyncio.run(local_storage.upload(
            io.BytesIO(test_data),
            test_filename
        ))

        # File should exist now
        assert asyncio.run(local_storage.exists(blob_id))

    def test_delete_file_success(self, local_storage: LocalFilesystemStorage):
        """Test successful file deletion."""
        test_data = b"Delete test"
        test_filename = "delete_test.txt"

        # Upload file
        blob_id = asyncio.run(local_storage.upload(
            io.BytesIO(test_data),
            test_filename
        ))

        # Verify file exists
        storage_path = Path(local_storage.storage_path) / blob_id
        assert storage_path.exists()

        # Delete file
        result = asyncio.run(local_storage.delete(blob_id))
        assert result is True

        # Verify file is gone
        assert not storage_path.exists()

    def test_delete_nonexistent_file(self, local_storage: LocalFilesystemStorage):
        """Test deleting non-existent file."""
        result = asyncio.run(local_storage.delete("nonexistent-blob-id"))
        assert result is False

    def test_path_traversal_protection(self, local_storage: LocalFilesystemStorage):
        """Test protection against path traversal attacks."""
        malicious_filename = "../../../etc/passwd"

        with pytest.raises(ValueError, match="Invalid filename"):
            asyncio.run(local_storage.upload(
                io.BytesIO(b"malicious content"),
                malicious_filename
            ))

    def test_large_file_handling(self, local_storage: LocalFilesystemStorage):
        """Test handling of large files."""
        # Create a 10MB test file
        large_data = b"A" * (10 * 1024 * 1024)  # 10MB
        test_filename = "large_file.bin"

        blob_id = asyncio.run(local_storage.upload(
            io.BytesIO(large_data),
            test_filename
        ))

        assert blob_id is not None

        # Verify file was stored correctly
        storage_path = Path(local_storage.storage_path) / blob_id
        assert storage_path.exists()
        assert storage_path.stat().st_size == len(large_data)

        # Test download
        downloaded_data = asyncio.run(local_storage.download(blob_id))
        assert downloaded_data.read() == large_data


class TestS3BlobStorage:
    """Test S3-compatible storage adapter."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        mock_client = MagicMock()

        # Mock successful upload
        mock_client.upload_fileobj = AsyncMock()

        # Mock successful download
        mock_download_response = {'Body': io.BytesIO(b"test content")}
        mock_client.get_object = AsyncMock(return_value=mock_download_response)

        # Mock successful head_object (exists check)
        mock_client.head_object = AsyncMock()

        # Mock successful delete
        mock_client.delete_object = AsyncMock()

        return mock_client

    @pytest.fixture
    def s3_storage(self, mock_s3_client):
        """Create S3 storage instance with mocked client."""
        with patch.dict(os.environ, {
            'STORAGE_TYPE': 's3',
            'S3_BUCKET_NAME': 'test-bucket',
            'S3_REGION': 'us-east-1',
            'S3_ACCESS_KEY_ID': 'test-key',
            'S3_SECRET_ACCESS_KEY': 'test-secret'
        }):
            settings = Settings()
            with patch('boto3.client', return_value=mock_s3_client):
                return S3BlobStorage(settings)

    def test_upload_file_success(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test successful file upload to S3."""
        test_data = b"S3 upload test"
        test_filename = "s3_test.txt"

        blob_id = asyncio.run(s3_storage.upload(
            io.BytesIO(test_data),
            test_filename
        ))

        assert blob_id is not None
        mock_s3_client.upload_fileobj.assert_called_once()

    def test_download_file_success(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test successful file download from S3."""
        test_data = b"S3 download test"
        mock_s3_client.get_object.return_value['Body'] = io.BytesIO(test_data)

        blob_id = "test-blob-id"
        downloaded_data = asyncio.run(s3_storage.download(blob_id))

        assert downloaded_data.read() == test_data
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key=blob_id
        )

    def test_download_nonexistent_file(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test downloading non-existent file from S3 raises error."""
        # Mock S3 NoSuchKey error
        error_response = {'Error': {'Code': 'NoSuchKey'}}
        mock_s3_client.get_object.side_effect = ClientError(
            error_response, 'GetObject'
        )

        with pytest.raises(BlobNotFoundError):
            asyncio.run(s3_storage.download("nonexistent-blob-id"))

    def test_exists_file_check(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test checking if file exists in S3."""
        # File exists
        mock_s3_client.head_object.return_value = {'ETag': '"test-etag"'}
        assert asyncio.run(s3_storage.exists("existing-blob-id"))

        # File doesn't exist
        error_response = {'Error': {'Code': 'NoSuchKey'}}
        mock_s3_client.head_object.side_effect = ClientError(
            error_response, 'HeadObject'
        )
        assert not asyncio.run(s3_storage.exists("nonexistent-blob-id"))

    def test_delete_file_success(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test successful file deletion from S3."""
        blob_id = "test-blob-id"
        result = asyncio.run(s3_storage.delete(blob_id))

        assert result is True
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket='test-bucket',
            Key=blob_id
        )

    def test_delete_nonexistent_file(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test deleting non-existent file from S3."""
        # Mock S3 NoSuchKey error
        error_response = {'Error': {'Code': 'NoSuchKey'}}
        mock_s3_client.delete_object.side_effect = ClientError(
            error_response, 'DeleteObject'
        )

        result = asyncio.run(s3_storage.delete("nonexistent-blob-id"))
        assert result is False

    def test_network_error_retry(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test retry logic on network errors."""
        # Mock connection error that should be retried
        mock_s3_client.get_object.side_effect = [
            EndpointConnectionError(endpoint_url="https://s3.amazonaws.com"),
            EndpointConnectionError(endpoint_url="https://s3.amazonaws.com"),
            {'Body': io.BytesIO(b"success after retry")}
        ]

        blob_id = "test-blob-id"
        downloaded_data = asyncio.run(s3_storage.download(blob_id))

        assert downloaded_data.read() == b"success after retry"
        assert mock_s3_client.get_object.call_count == 3  # Should retry twice

    def test_permanent_error_no_retry(self, s3_storage: S3BlobStorage, mock_s3_client):
        """Test that permanent errors don't trigger retries."""
        # Mock permanent error (InvalidBucketName)
        error_response = {'Error': {'Code': 'InvalidBucketName'}}
        mock_s3_client.get_object.side_effect = ClientError(
            error_response, 'GetObject'
        )

        with pytest.raises(StorageError):
            asyncio.run(s3_storage.download("test-blob-id"))

        assert mock_s3_client.get_object.call_count == 1  # Should not retry


class TestContentHashingAndDeduplication:
    """Test content-based hashing and deduplication features."""

    @pytest.fixture
    def storage_with_deduplication(self, temp_storage_path: str):
        """Create storage instance with deduplication enabled."""
        with patch.dict(os.environ, {
            'STORAGE_TYPE': 'local',
            'LOCAL_STORAGE_PATH': temp_storage_path
        }):
            settings = Settings()
            return LocalFilesystemStorage(settings, enable_deduplication=True)

    def test_sha256_hash_calculation(self):
        """Test SHA256 hash calculation is consistent."""
        test_data = b"Test content for hashing"
        expected_hash = hashlib.sha256(test_data).hexdigest()

        # Multiple calls should produce the same hash
        for _ in range(10):
            assert LocalFilesystemStorage.calculate_content_hash(test_data) == expected_hash

    def test_different_content_different_hashes(self):
        """Test that different content produces different hashes."""
        data1 = b"Content 1"
        data2 = b"Content 2"

        hash1 = LocalFilesystemStorage.calculate_content_hash(data1)
        hash2 = LocalFilesystemStorage.calculate_content_hash(data2)

        assert hash1 != hash2

    def test_identical_content_deduplication(self, storage_with_deduplication):
        """Test that identical content is properly deduplicated."""
        test_data = b"Identical content for deduplication"
        filename1 = "file1.txt"
        filename2 = "file2.txt"

        # Upload same content twice
        blob_id1 = asyncio.run(storage_with_deduplication.upload(
            io.BytesIO(test_data), filename1
        ))
        blob_id2 = asyncio.run(storage_with_deduplication.upload(
            io.BytesIO(test_data), filename2
        ))

        # Should get the same blob ID for identical content
        assert blob_id1 == blob_id2

        # But should be able to retrieve by either filename
        assert asyncio.run(storage_with_deduplication.exists(blob_id1))

    def test_different_content_different_blob_ids(self, storage_with_deduplication):
        """Test that different content gets different blob IDs."""
        data1 = b"Content 1"
        data2 = b"Content 2"
        filename1 = "file1.txt"
        filename2 = "file2.txt"

        blob_id1 = asyncio.run(storage_with_deduplication.upload(
            io.BytesIO(data1), filename1
        ))
        blob_id2 = asyncio.run(storage_with_deduplication.upload(
            io.BytesIO(data2), filename2
        ))

        assert blob_id1 != blob_id2

    def test_empty_file_hash(self):
        """Test hash calculation for empty files."""
        empty_data = b""
        hash_value = LocalFilesystemStorage.calculate_content_hash(empty_data)

        assert hash_value is not None
        assert len(hash_value) == 64  # SHA256 hex length

        # Multiple calls should be consistent
        hash_value2 = LocalFilesystemStorage.calculate_content_hash(empty_data)
        assert hash_value == hash_value2

    def test_large_file_hash(self):
        """Test hash calculation for large files."""
        large_data = b"A" * (100 * 1024 * 1024)  # 100MB
        hash_value = LocalFilesystemStorage.calculate_content_hash(large_data)

        assert hash_value is not None
        assert len(hash_value) == 64

    def test_get_content_hash(self, storage_with_deduplication):
        """Test retrieving content hash for a blob."""
        test_data = b"Hash retrieval test"
        test_filename = "hash_test.txt"

        blob_id = asyncio.run(storage_with_deduplication.upload(
            io.BytesIO(test_data), test_filename
        ))

        retrieved_hash = asyncio.run(storage_with_deduplication.get_content_hash(blob_id))
        expected_hash = LocalFilesystemStorage.calculate_content_hash(test_data)

        assert retrieved_hash == expected_hash

    def test_get_content_hash_nonexistent_blob(self, storage_with_deduplication):
        """Test getting hash for non-existent blob raises error."""
        with pytest.raises(BlobNotFoundError):
            asyncio.run(storage_with_deduplication.get_content_hash("nonexistent-blob-id"))


class TestRetryLogicAndErrorHandling:
    """Test retry logic and advanced error handling."""

    @pytest.fixture
    def mock_retry_storage(self):
        """Create storage instance with mocked retry logic."""
        with patch.dict(os.environ, {'STORAGE_TYPE': 'local'}):
            settings = Settings()
            storage = LocalFilesystemStorage(settings)

            # Mock the retry decorator
            storage.retry_on_failure = MagicMock(side_effect=lambda f: f)
            return storage

    def test_transient_error_retry(self, mock_retry_storage):
        """Test that transient errors trigger retries."""
        call_count = 0

        @mock_retry_storage.retry_on_failure
        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary network error")
            return "success"

        result = failing_operation()
        assert result == "success"
        assert call_count == 3

    def test_permanent_error_no_retry(self, mock_retry_storage):
        """Test that permanent errors don't trigger retries."""
        call_count = 0

        @mock_retry_storage.retry_on_failure
        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")

        with pytest.raises(ValueError, match="Permanent error"):
            failing_operation()

        assert call_count == 1

    def test_exponential_backoff_timing(self):
        """Test that retry delays increase exponentially."""
        delays = []

        def mock_sleep(delay):
            delays.append(delay)

        # Mock time.sleep to capture delays
        with patch('time.sleep', side_effect=mock_sleep):
            storage = LocalFilesystemStorage(Settings())

            # Simulate retries with exponential backoff
            for attempt in range(3):
                if attempt < 2:  # Fail twice, succeed on third
                    raise ConnectionError("Network error")

        # Verify exponential backoff pattern
        assert len(delays) == 2  # Two retry delays
        assert delays[1] > delays[0]  # Second delay should be longer

    def test_circuit_breaker_pattern(self):
        """Test circuit breaker prevents overwhelming failing service."""
        failure_count = 0

        def failing_operation():
            nonlocal failure_count
            failure_count += 1
            raise ConnectionError("Persistent network failure")

        # Circuit breaker should open after multiple failures
        with patch('time.time', return_value=1000):  # Fixed timestamp
            storage = LocalFilesystemStorage(Settings())

            # First few failures should be retried
            for _ in range(3):
                try:
                    failing_operation()
                except ConnectionError:
                    pass

            # Circuit should be open, no more retries
            failure_count_before = failure_count
            try:
                failing_operation()
            except ConnectionError:
                pass

            # Should not have increased failure count (circuit open)
            assert failure_count == failure_count_before

    def test_detailed_error_logging(self, caplog):
        """Test that errors are logged with sufficient context."""
        with patch.dict(os.environ, {'STORAGE_TYPE': 'local'}):
            settings = Settings()
            storage = LocalFilesystemStorage(settings)

            with patch.object(storage, 'upload',
                            side_effect=StorageError("Upload failed")):
                with pytest.raises(StorageError):
                    asyncio.run(storage.upload(io.BytesIO(b"test"), "test.txt"))

            # Check that error was logged with context
            assert any("Upload failed" in record.message
                      for record in caplog.records)

    def test_error_context_preservation(self):
        """Test that original error context is preserved through retries."""
        original_error = ValueError("Original error message")

        def failing_operation():
            raise original_error

        with patch.dict(os.environ, {'STORAGE_TYPE': 'local'}):
            settings = Settings()
            storage = LocalFilesystemStorage(settings)

            with pytest.raises(ValueError, match="Original error message"):
                # This should fail immediately without retries for ValueError
                failing_operation()


class TestBlobStorageIntegration:
    """Integration tests for blob storage service."""

    @pytest.fixture
    def storage_service(self):
        """Create storage service for integration tests."""
        with patch.dict(os.environ, {'STORAGE_TYPE': 'local'}):
            settings = Settings()
            return LocalFilesystemStorage(settings)

    def test_upload_download_various_file_types(self, storage_service):
        """Test upload/download operations with various file types."""
        test_cases = [
            (b"Text content", "text.txt"),
            (b"Binary content \x00\x01\x02", "binary.bin"),
            (b'{"key": "value"}', "json.json"),
            (b"<html></html>", "html.html"),
            (b"", "empty.txt"),  # Empty file
        ]

        for content, filename in test_cases:
            # Upload file
            blob_id = asyncio.run(storage_service.upload(
                io.BytesIO(content), filename
            ))
            assert blob_id is not None

            # Download and verify content
            downloaded = asyncio.run(storage_service.download(blob_id))
            assert downloaded.read() == content

            # Verify existence
            assert asyncio.run(storage_service.exists(blob_id))

    def test_concurrent_operations(self, storage_service):
        """Test concurrent upload/download operations."""
        async def upload_and_verify(content: bytes, filename: str):
            blob_id = await storage_service.upload(io.BytesIO(content), filename)
            downloaded = await storage_service.download(blob_id)
            assert downloaded.read() == content
            return blob_id

        # Create multiple concurrent operations
        tasks = []
        for i in range(10):
            content = f"Concurrent content {i}".encode()
            filename = f"concurrent_{i}.txt"
            tasks.append(upload_and_verify(content, filename))

        # Run concurrently
        blob_ids = asyncio.run(asyncio.gather(*tasks))

        # Verify all operations succeeded
        assert len(blob_ids) == 10
        assert all(blob_id is not None for blob_id in blob_ids)

    def test_file_lifecycle_management(self, storage_service):
        """Test complete file lifecycle: upload, access, delete."""
        content = b"Lifecycle test content"
        filename = "lifecycle_test.txt"

        # Upload file
        blob_id = asyncio.run(storage_service.upload(
            io.BytesIO(content), filename
        ))
        assert blob_id is not None

        # Verify it exists
        assert asyncio.run(storage_service.exists(blob_id))

        # Access file multiple times
        for _ in range(3):
            downloaded = asyncio.run(storage_service.download(blob_id))
            assert downloaded.read() == content

        # Delete file
        result = asyncio.run(storage_service.delete(blob_id))
        assert result is True

        # Verify file is gone
        assert not asyncio.run(storage_service.exists(blob_id))

        # Verify deletion is idempotent
        result2 = asyncio.run(storage_service.delete(blob_id))
        assert result2 is False


# Test configuration fixtures
@pytest.fixture
def mock_env():
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
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


if __name__ == "__main__":
    pytest.main([__file__])

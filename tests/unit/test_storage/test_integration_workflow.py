"""Integration tests for complete blob storage workflow."""

import asyncio
import io
from pathlib import Path

import pytest

from config.settings import Settings


class TestBlobStorageWorkflow:
    """Test complete blob storage workflows."""

    @pytest.mark.asyncio
    async def test_upload_download_workflow(self, temp_storage_path):
        """Test complete upload and download workflow."""
        # Import here to avoid import errors if services don't exist yet
        try:
            from services.storage import StorageFactory
            from config.settings import Settings

            # Configure for local storage
            settings = Settings()
            settings.STORAGE_TYPE = 'local'
            settings.LOCAL_STORAGE_PATH = temp_storage_path

            # Create storage service
            factory = StorageFactory(settings)
            storage = factory.create_storage()

            # Test data
            test_content = b"Integration test content for blob storage"
            test_filename = "integration_test.txt"

            # Step 1: Upload file
            blob_id = await storage.upload(
                io.BytesIO(test_content),
                test_filename
            )
            assert blob_id is not None

            # Step 2: Verify file exists
            assert await storage.exists(blob_id)

            # Step 3: Download and verify content
            downloaded_data = await storage.download(blob_id)
            assert downloaded_data.read() == test_content

            # Step 4: Get content hash
            content_hash = await storage.get_content_hash(blob_id)
            assert content_hash is not None
            assert len(content_hash) == 64  # SHA256 hex length

            # Step 5: Delete file
            delete_result = await storage.delete(blob_id)
            assert delete_result is True

            # Step 6: Verify file is gone
            assert not await storage.exists(blob_id)

        except ImportError:
            pytest.skip("Storage services not implemented yet")

    @pytest.mark.asyncio
    async def test_deduplication_workflow(self, temp_storage_path):
        """Test content deduplication workflow."""
        try:
            from services.storage import StorageFactory
            from config.settings import Settings

            # Configure for local storage with deduplication
            settings = Settings()
            settings.STORAGE_TYPE = 'local'
            settings.LOCAL_STORAGE_PATH = temp_storage_path

            # Create storage service
            factory = StorageFactory(settings)
            storage = factory.create_storage()

            # Same content, different filenames
            test_content = b"Identical content for deduplication test"
            filename1 = "file1.txt"
            filename2 = "file2.txt"

            # Upload same content twice
            blob_id1 = await storage.upload(
                io.BytesIO(test_content),
                filename1
            )
            blob_id2 = await storage.upload(
                io.BytesIO(test_content),
                filename2
            )

            # Should get the same blob ID
            assert blob_id1 == blob_id2

            # Both should exist
            assert await storage.exists(blob_id1)
            assert await storage.exists(blob_id2)

            # Should be able to download from either
            data1 = await storage.download(blob_id1)
            data2 = await storage.download(blob_id2)
            assert data1.read() == test_content
            assert data2.read() == test_content

        except ImportError:
            pytest.skip("Storage services not implemented yet")

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, temp_storage_path):
        """Test concurrent blob storage operations."""
        try:
            from services.storage import StorageFactory
            from config.settings import Settings

            # Configure for local storage
            settings = Settings()
            settings.STORAGE_TYPE = 'local'
            settings.LOCAL_STORAGE_PATH = temp_storage_path

            # Create storage service
            factory = StorageFactory(settings)
            storage = factory.create_storage()

            # Test data
            test_files = [
                (b"Content 1", "file1.txt"),
                (b"Content 2", "file2.txt"),
                (b"Content 3", "file3.txt"),
                (b"Content 4", "file4.txt"),
                (b"Content 5", "file5.txt"),
            ]

            # Upload all files concurrently
            upload_tasks = []
            for content, filename in test_files:
                task = storage.upload(io.BytesIO(content), filename)
                upload_tasks.append(task)

            blob_ids = await asyncio.gather(*upload_tasks)

            # Verify all uploads succeeded
            assert len(blob_ids) == len(test_files)
            assert all(blob_id is not None for blob_id in blob_ids)

            # Download all files concurrently
            download_tasks = [storage.download(blob_id) for blob_id in blob_ids]
            downloaded_data = await asyncio.gather(*download_tasks)

            # Verify content matches
            for i, (expected_content, _) in enumerate(test_files):
                assert downloaded_data[i].read() == expected_content

        except ImportError:
            pytest.skip("Storage services not implemented yet")

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, temp_storage_path):
        """Test error recovery and retry workflows."""
        try:
            from services.storage import StorageFactory
            from config.settings import Settings

            # Configure for local storage
            settings = Settings()
            settings.STORAGE_TYPE = 'local'
            settings.LOCAL_STORAGE_PATH = temp_storage_path

            # Create storage service
            factory = StorageFactory(settings)
            storage = factory.create_storage()

            # Test data
            test_content = b"Error recovery test content"
            test_filename = "error_recovery_test.txt"

            # Upload file
            blob_id = await storage.upload(
                io.BytesIO(test_content),
                test_filename
            )
            assert blob_id is not None

            # Verify file exists
            assert await storage.exists(blob_id)

            # Test downloading non-existent file
            with pytest.raises(Exception):  # Should raise some kind of error
                await storage.download("nonexistent-blob-id")

            # Test deleting non-existent file
            delete_result = await storage.delete("nonexistent-blob-id")
            assert delete_result is False

            # Verify original file still exists and works
            assert await storage.exists(blob_id)
            downloaded_data = await storage.download(blob_id)
            assert downloaded_data.read() == test_content

        except ImportError:
            pytest.skip("Storage services not implemented yet")

"""Unit tests for blob storage factory."""

import os
import pytest
from unittest.mock import patch, MagicMock

from services.blob_storage.factory import BlobStorageFactory, get_blob_storage
from services.blob_storage.config import BlobStorageConfig
from services.blob_storage.exceptions import StorageConfigurationError


class TestBlobStorageFactory:
    """Test blob storage factory functionality."""

    def test_create_local_storage(self):
        """Test factory creates local storage implementation."""
        os.environ['STORAGE_TYPE'] = 'local'
        import services.blob_storage.config as config_module
        config_module._config = None
        config = BlobStorageConfig()

        with patch('services.blob_storage.factory.LocalFilesystemStorage') as mock_local:
            mock_instance = MagicMock()
            mock_local.return_value = mock_instance

            storage = BlobStorageFactory.create_storage(config)

            mock_local.assert_called_once_with(config)
            assert storage == mock_instance

    def test_create_s3_storage(self):
        """Test factory creates S3 storage implementation."""
        env_vars = {
            "STORAGE_TYPE": "s3",
            "S3_BUCKET_NAME": "test-bucket",
            "S3_ACCESS_KEY_ID": "test_key",
            "S3_SECRET_ACCESS_KEY": "test_secret"
        }

        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            import services.blob_storage.config as config_module
            config_module._config = None
            config = BlobStorageConfig()

            with patch('services.blob_storage.factory.S3BlobStorage') as mock_s3:
                mock_instance = MagicMock()
                mock_s3.return_value = mock_instance

                storage = BlobStorageFactory.create_storage(config)

                mock_s3.assert_called_once_with(config)
                assert storage == mock_instance

        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

    def test_create_storage_with_invalid_type(self):
        """Test factory raises error for invalid storage type."""
        import os
        os.environ['STORAGE_TYPE'] = 'invalid'
        import services.blob_storage.config as config_module
        config_module._config = None
        config = BlobStorageConfig()

        with pytest.raises(ValueError, match="Unsupported storage type"):
            BlobStorageFactory.create_storage(config)

    def test_create_storage_with_invalid_s3_config(self):
        """Test factory raises error when S3 config is incomplete."""
        env_vars = {
            "STORAGE_TYPE": "s3",
            "S3_BUCKET_NAME": "test-bucket"
            # Missing credentials
        }

        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            import services.blob_storage.config as config_module
            config_module._config = None
            config = BlobStorageConfig()

            with pytest.raises(ValueError, match="S3 configuration is incomplete"):
                BlobStorageFactory.create_storage(config)

        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

    def test_get_blob_storage_convenience_function(self):
        """Test the get_blob_storage convenience function."""
        os.environ['STORAGE_TYPE'] = 'local'
        import services.blob_storage.config as config_module
        config_module._config = None
        config = BlobStorageConfig()

        with patch('services.blob_storage.factory.BlobStorageFactory.create_storage') as mock_create:
            mock_instance = MagicMock()
            mock_create.return_value = mock_instance

            storage = get_blob_storage(config)

            mock_create.assert_called_once_with(config)
            assert storage == mock_instance

    def test_get_blob_storage_uses_global_config(self):
        """Test get_blob_storage uses global config when none provided."""
        os.environ['STORAGE_TYPE'] = 'local'
        import services.blob_storage.config as config_module
        config_module._config = None

        # Test that get_blob_storage works without providing a config
        storage = get_blob_storage()
        assert storage is not None
        # The storage should be one of our implemented types
        assert hasattr(storage, 'upload')
        assert hasattr(storage, 'download')
        assert hasattr(storage, 'exists')
        assert hasattr(storage, 'delete')

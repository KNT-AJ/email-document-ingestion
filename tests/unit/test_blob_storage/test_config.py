"""Unit tests for blob storage configuration."""

import os
import pytest
from pathlib import Path

from services.blob_storage.config import BlobStorageConfig, get_config


class TestBlobStorageConfig:
    """Test blob storage configuration loading."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BlobStorageConfig()

        assert config.storage_type == "local"
        assert config.local_storage_path == Path("./data/blobs")
        assert config.max_retries == 3
        assert config.retry_backoff_factor == 1.0
        assert config.connection_timeout == 30

    def test_environment_variable_override(self):
        """Test configuration from environment variables."""
        env_vars = {
            "STORAGE_TYPE": "s3",
            "LOCAL_STORAGE_PATH": "/tmp/test_blobs",
            "S3_BUCKET_NAME": "test-bucket",
            "S3_ENDPOINT_URL": "https://minio.example.com",
            "S3_REGION": "us-west-2",
            "S3_ACCESS_KEY_ID": "test_key",
            "S3_SECRET_ACCESS_KEY": "test_secret",
            "MAX_RETRIES": "5",
            "RETRY_BACKOFF_FACTOR": "2.0",
            "CONNECTION_TIMEOUT": "60",
        }

        # Set environment variables
        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            # Clear the cached config instance
            import services.blob_storage.config as config_module
            config_module._config = None

            config = BlobStorageConfig()

            assert config.storage_type == "s3"
            assert config.local_storage_path == Path("/tmp/test_blobs")
            assert config.s3_bucket_name == "test-bucket"
            assert config.s3_endpoint_url == "https://minio.example.com"
            assert config.s3_region == "us-west-2"
            assert config.s3_access_key_id == "test_key"
            assert config.s3_secret_access_key == "test_secret"
            assert config.max_retries == 5
            assert config.retry_backoff_factor == 2.0
            assert config.connection_timeout == 60

        finally:
            # Restore environment variables
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

    def test_s3_configuration_validation(self):
        """Test S3 configuration validation methods."""
        # Test incomplete S3 configuration
        env_vars = {
            "STORAGE_TYPE": "s3",
            "S3_BUCKET_NAME": "test-bucket",
            "S3_ACCESS_KEY_ID": "test_key"
            # Missing S3_SECRET_ACCESS_KEY
        }

        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            import services.blob_storage.config as config_module
            config_module._config = None

            config = BlobStorageConfig()
            assert not config.is_s3_configured()

        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        # Test complete S3 configuration
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
            assert config.is_s3_configured()

        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

    def test_storage_type_validation(self):
        """Test storage type validation."""
        # Test valid local storage type
        os.environ['STORAGE_TYPE'] = 'local'
        import services.blob_storage.config as config_module
        config_module._config = None
        config = BlobStorageConfig()
        assert config.get_storage_type() == "local"

        # Test valid S3 storage type with complete config
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
            config_module._config = None
            config = BlobStorageConfig()
            assert config.get_storage_type() == "s3"

        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        # Test invalid S3 storage type with incomplete config
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
            config_module._config = None
            config = BlobStorageConfig()

            with pytest.raises(ValueError, match="S3 configuration is incomplete"):
                config.get_storage_type()

        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        # Test invalid storage type
        os.environ['STORAGE_TYPE'] = 'invalid'
        config_module._config = None
        config = BlobStorageConfig()

        # This should not raise an error during config loading
        assert config.storage_type == "invalid"
        # But should raise an error when validated
        with pytest.raises(ValueError, match="Unsupported storage type"):
            config.get_storage_type()

    def test_get_config_function(self):
        """Test the get_config function for caching behavior."""
        # Clear any existing config
        import services.blob_storage.config as config_module
        config_module._config = None

        # First call should create a new config
        config1 = get_config()
        assert isinstance(config1, BlobStorageConfig)

        # Second call should return the same instance (caching)
        config2 = get_config()
        assert config1 is config2

        # Reset for other tests
        config_module._config = None

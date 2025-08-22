"""Factory for creating blob storage implementations."""

from typing import Optional
import logging

from .interface import BlobStorageInterface
from .config import get_config, BlobStorageConfig
from .exceptions import StorageConfigurationError


logger = logging.getLogger(__name__)


# Import storage implementations
try:
    from .local_storage import LocalFilesystemStorage
    from .s3_storage import S3BlobStorage
except ImportError as e:
    logger.error(f"Failed to import storage implementations: {e}")
    raise


class BlobStorageFactory:
    """Factory for creating blob storage implementations."""

    @staticmethod
    def create_storage(config: Optional[BlobStorageConfig] = None) -> BlobStorageInterface:
        """
        Create a blob storage implementation based on configuration.

        Args:
            config: Blob storage configuration. If None, uses global config.

        Returns:
            Configured blob storage implementation

        Raises:
            StorageConfigurationError: If configuration is invalid
        """
        if config is None:
            config = get_config()

        storage_type = config.get_storage_type()
        logger.info(f"Creating {storage_type} blob storage implementation")

        if storage_type == "local":
            return LocalFilesystemStorage(config)

        elif storage_type == "s3":
            return S3BlobStorage(config)

        else:
            raise StorageConfigurationError(f"Unsupported storage type: {storage_type}")


def get_blob_storage(config: Optional[BlobStorageConfig] = None) -> BlobStorageInterface:
    """
    Get a configured blob storage instance.

    This is a convenience function that uses the factory to create storage instances.
    It caches the storage instance to avoid recreating it on every call.

    Args:
        config: Blob storage configuration. If None, uses global config.

    Returns:
        Configured blob storage implementation
    """
    # For now, we'll create a new instance each time
    # In a future enhancement, we could add caching here
    return BlobStorageFactory.create_storage(config)

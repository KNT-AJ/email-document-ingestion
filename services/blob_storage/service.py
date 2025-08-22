"""Main blob storage service with logging and high-level operations."""

import logging
import time
from typing import Optional, BinaryIO, Tuple
from pathlib import Path

from .interface import BlobStorageInterface
from .factory import get_blob_storage
from .config import get_config, BlobStorageConfig
from .exceptions import StorageError


logger = logging.getLogger(__name__)


class BlobStorageService:
    """High-level blob storage service with logging and error handling."""

    def __init__(self, config: Optional[BlobStorageConfig] = None):
        """
        Initialize blob storage service.

        Args:
            config: Optional blob storage configuration
        """
        self.config = config or get_config()
        self._storage: Optional[BlobStorageInterface] = None

        logger.info(
            f"Initializing blob storage service with type: {self.config.get_storage_type()}"
        )

    @property
    def storage(self) -> BlobStorageInterface:
        """Get the underlying storage implementation."""
        if self._storage is None:
            self._storage = get_blob_storage(self.config)
        return self._storage

    def upload_blob(
        self,
        blob_path: str,
        data: BinaryIO,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a blob with logging and error handling.

        Args:
            blob_path: Path/key for the blob
            data: Binary data to upload
            content_type: MIME type of the content

        Returns:
            The blob path that was used for storage
        """
        start_time = time.time()

        try:
            logger.info(f"Uploading blob: {blob_path}")
            result = self.storage.upload(blob_path, data, content_type)

            elapsed = time.time() - start_time
            logger.info(f"Successfully uploaded blob: {blob_path} (took {elapsed:.2f}s)")

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Failed to upload blob: {blob_path} (took {elapsed:.2f}s)",
                exc_info=True
            )
            raise

    def download_blob(self, blob_path: str) -> Tuple[BinaryIO, Optional[str]]:
        """
        Download a blob with logging and error handling.

        Args:
            blob_path: Path/key of the blob to download

        Returns:
            Tuple of (data stream, content_type)
        """
        start_time = time.time()

        try:
            logger.info(f"Downloading blob: {blob_path}")
            data, content_type = self.storage.download(blob_path)

            elapsed = time.time() - start_time
            logger.info(f"Successfully downloaded blob: {blob_path} (took {elapsed:.2f}s)")

            return data, content_type

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Failed to download blob: {blob_path} (took {elapsed:.2f}s)",
                exc_info=True
            )
            raise

    def blob_exists(self, blob_path: str) -> bool:
        """
        Check if a blob exists.

        Args:
            blob_path: Path/key of the blob to check

        Returns:
            True if blob exists, False otherwise
        """
        try:
            exists = self.storage.exists(blob_path)
            logger.debug(f"Blob existence check: {blob_path} -> {exists}")
            return exists

        except Exception as e:
            logger.error(f"Failed to check blob existence: {blob_path}", exc_info=True)
            raise

    def delete_blob(self, blob_path: str) -> bool:
        """
        Delete a blob with logging and error handling.

        Args:
            blob_path: Path/key of the blob to delete

        Returns:
            True if blob was deleted, False if it didn't exist
        """
        start_time = time.time()

        try:
            logger.info(f"Deleting blob: {blob_path}")
            result = self.storage.delete(blob_path)

            elapsed = time.time() - start_time
            if result:
                logger.info(f"Successfully deleted blob: {blob_path} (took {elapsed:.2f}s)")
            else:
                logger.info(f"Blob not found for deletion: {blob_path} (took {elapsed:.2f}s)")

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Failed to delete blob: {blob_path} (took {elapsed:.2f}s)",
                exc_info=True
            )
            raise

    def get_blob_url(self, blob_path: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """
        Get a temporary URL for accessing a blob.

        Args:
            blob_path: Path/key of the blob
            expires_in_seconds: How long the URL should be valid

        Returns:
            Temporary URL if supported, None otherwise
        """
        try:
            url = self.storage.get_url(blob_path, expires_in_seconds)
            if url:
                logger.debug(f"Generated blob URL for: {blob_path}")
            else:
                logger.debug(f"No URL available for blob: {blob_path}")
            return url

        except Exception as e:
            logger.error(f"Failed to get blob URL: {blob_path}", exc_info=True)
            raise


def create_blob_storage_service(config: Optional[BlobStorageConfig] = None) -> BlobStorageService:
    """
    Factory function to create a blob storage service instance.

    Args:
        config: Optional blob storage configuration

    Returns:
        Configured blob storage service
    """
    return BlobStorageService(config)

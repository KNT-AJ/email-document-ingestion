"""Abstract interface for blob storage services."""

from abc import ABC, abstractmethod
from typing import Optional, BinaryIO, Tuple
from pathlib import Path


class BlobStorageInterface(ABC):
    """Abstract base class for blob storage implementations."""

    @abstractmethod
    def upload(self, blob_path: str, data: BinaryIO, content_type: Optional[str] = None) -> str:
        """
        Upload data to blob storage.

        Args:
            blob_path: Path/key for the blob in storage
            data: Binary data stream to upload
            content_type: MIME type of the content

        Returns:
            The blob path/key that was used for storage

        Raises:
            StorageError: If upload fails
        """
        pass

    @abstractmethod
    def download(self, blob_path: str) -> Tuple[BinaryIO, Optional[str]]:
        """
        Download data from blob storage.

        Args:
            blob_path: Path/key of the blob to download

        Returns:
            Tuple of (data stream, content_type)

        Raises:
            BlobNotFoundError: If blob doesn't exist
            StorageError: If download fails
        """
        pass

    @abstractmethod
    def exists(self, blob_path: str) -> bool:
        """
        Check if a blob exists in storage.

        Args:
            blob_path: Path/key of the blob to check

        Returns:
            True if blob exists, False otherwise
        """
        pass

    @abstractmethod
    def delete(self, blob_path: str) -> bool:
        """
        Delete a blob from storage.

        Args:
            blob_path: Path/key of the blob to delete

        Returns:
            True if blob was deleted, False if it didn't exist

        Raises:
            StorageError: If deletion fails
        """
        pass

    @abstractmethod
    def get_url(self, blob_path: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """
        Get a temporary URL for accessing the blob.

        Args:
            blob_path: Path/key of the blob
            expires_in_seconds: How long the URL should be valid

        Returns:
            Temporary URL if supported, None otherwise
        """
        pass

"""Local filesystem implementation of blob storage."""

from typing import Optional, BinaryIO, Tuple
from pathlib import Path
import io
import os

from .interface import BlobStorageInterface
from .config import BlobStorageConfig
from .exceptions import BlobNotFoundError, StorageError


class LocalFilesystemStorage(BlobStorageInterface):
    """Local filesystem implementation of blob storage."""

    def __init__(self, config: BlobStorageConfig):
        """
        Initialize local filesystem storage.

        Args:
            config: Blob storage configuration
        """
        self.config = config
        self.storage_path = Path(config.local_storage_path)
        self._ensure_storage_directory()

    def _ensure_storage_directory(self) -> None:
        """Ensure the storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, blob_path: str) -> Path:
        """Get the full file path for a blob."""
        # Normalize blob path to prevent directory traversal
        normalized_path = os.path.normpath(blob_path)
        if normalized_path.startswith("..") or normalized_path.startswith("/"):
            raise StorageError(f"Invalid blob path: {blob_path}")

        return self.storage_path / normalized_path

    def upload(self, blob_path: str, data: BinaryIO, content_type: Optional[str] = None) -> str:
        """Upload data to local filesystem storage."""
        file_path = self._get_file_path(blob_path)

        try:
            # Ensure parent directories exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write data to file
            with open(file_path, 'wb') as f:
                f.write(data.read())

            return blob_path

        except Exception as e:
            raise StorageError(f"Failed to upload blob: {blob_path}", blob_path, e)

    def download(self, blob_path: str) -> Tuple[BinaryIO, Optional[str]]:
        """Download data from local filesystem storage."""
        file_path = self._get_file_path(blob_path)

        if not file_path.exists():
            raise BlobNotFoundError(blob_path)

        try:
            with open(file_path, 'rb') as f:
                data = io.BytesIO(f.read())

            # Try to determine content type from file extension
            content_type = self._guess_content_type(blob_path)

            return data, content_type

        except BlobNotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to download blob: {blob_path}", blob_path, e)

    def exists(self, blob_path: str) -> bool:
        """Check if a blob exists in local filesystem storage."""
        file_path = self._get_file_path(blob_path)
        return file_path.exists() and file_path.is_file()

    def delete(self, blob_path: str) -> bool:
        """Delete a blob from local filesystem storage."""
        file_path = self._get_file_path(blob_path)

        if not file_path.exists():
            return False

        try:
            file_path.unlink()
            return True

        except Exception as e:
            raise StorageError(f"Failed to delete blob: {blob_path}", blob_path, e)

    def get_url(self, blob_path: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """Get a file:// URL for accessing the blob."""
        file_path = self._get_file_path(blob_path)

        if not file_path.exists():
            return None

        # Return file:// URL for local access
        return file_path.resolve().as_uri()

    def _guess_content_type(self, blob_path: str) -> Optional[str]:
        """Guess content type based on file extension."""
        extension = Path(blob_path).suffix.lower()

        content_types = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }

        return content_types.get(extension)

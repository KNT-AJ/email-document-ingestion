"""Custom exceptions for blob storage operations."""


class StorageError(Exception):
    """Base exception for storage-related errors."""

    def __init__(self, message: str, blob_path: str = None, cause: Exception = None):
        self.message = message
        self.blob_path = blob_path
        self.cause = cause
        super().__init__(self.message)


class BlobNotFoundError(StorageError):
    """Raised when a blob is not found in storage."""

    def __init__(self, blob_path: str, cause: Exception = None):
        super().__init__(f"Blob not found: {blob_path}", blob_path, cause)


class StorageConnectionError(StorageError):
    """Raised when there are connection issues with storage."""

    def __init__(self, message: str, blob_path: str = None, cause: Exception = None):
        super().__init__(message, blob_path, cause)


class StorageTimeoutError(StorageError):
    """Raised when storage operations timeout."""

    def __init__(self, blob_path: str = None, cause: Exception = None):
        super().__init__(f"Storage operation timed out", blob_path, cause)


class StorageConfigurationError(Exception):
    """Raised when storage is misconfigured."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

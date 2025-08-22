"""Configuration for blob storage service."""

import os
from typing import Optional
from pathlib import Path
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field


class BlobStorageConfig(BaseSettings):
    """Configuration for blob storage service."""

    model_config = {
        "extra": "ignore",  # Ignore extra environment variables
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }

    # Storage type selection
    storage_type: str = Field(
        default="local",
        alias="STORAGE_TYPE",
        description="Storage backend type: 'local' or 's3'"
    )

    # Local storage configuration
    local_storage_path: Path = Field(
        default=Path("./data/blobs"),
        alias="LOCAL_STORAGE_PATH",
        description="Local directory for blob storage"
    )

    # S3-compatible storage configuration
    s3_bucket_name: Optional[str] = Field(
        default=None,
        alias="S3_BUCKET_NAME",
        description="S3 bucket name"
    )
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        alias="S3_ENDPOINT_URL",
        description="S3-compatible endpoint URL (optional for AWS S3)"
    )
    s3_region: str = Field(
        default="us-east-1",
        alias="S3_REGION",
        description="S3 region"
    )
    s3_access_key_id: Optional[str] = Field(
        default=None,
        alias="S3_ACCESS_KEY_ID",
        description="S3 access key ID"
    )
    s3_secret_access_key: Optional[str] = Field(
        default=None,
        alias="S3_SECRET_ACCESS_KEY",
        description="S3 secret access key"
    )

    # Common settings
    max_retries: int = Field(
        default=3,
        alias="MAX_RETRIES",
        description="Maximum number of retries for storage operations"
    )
    retry_backoff_factor: float = Field(
        default=1.0,
        alias="RETRY_BACKOFF_FACTOR",
        description="Backoff factor for retry delays"
    )
    connection_timeout: int = Field(
        default=30,
        alias="CONNECTION_TIMEOUT",
        description="Connection timeout in seconds"
    )



    def is_s3_configured(self) -> bool:
        """Check if S3 configuration is complete."""
        return (
            self.s3_bucket_name is not None
            and self.s3_access_key_id is not None
            and self.s3_secret_access_key is not None
        )

    def get_storage_type(self) -> str:
        """Get the configured storage type, with validation."""
        if self.storage_type == "s3" and not self.is_s3_configured():
            raise ValueError(
                "S3 storage type selected but S3 configuration is incomplete. "
                "Please set BLOB_S3_BUCKET_NAME, BLOB_S3_ACCESS_KEY_ID, "
                "and BLOB_S3_SECRET_ACCESS_KEY environment variables."
            )
        elif self.storage_type not in ["local", "s3"]:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
        return self.storage_type


# Global configuration instance
_config: Optional[BlobStorageConfig] = None


def get_config() -> BlobStorageConfig:
    """Get the blob storage configuration."""
    global _config
    if _config is None:
        _config = BlobStorageConfig()
    return _config

"""S3-compatible blob storage implementation."""

from typing import Optional, BinaryIO, Tuple
import io

from .interface import BlobStorageInterface
from .config import BlobStorageConfig
from .exceptions import BlobNotFoundError, StorageError, StorageConfigurationError


class S3BlobStorage(BlobStorageInterface):
    """S3-compatible implementation of blob storage."""

    def __init__(self, config: BlobStorageConfig):
        """
        Initialize S3 blob storage.

        Args:
            config: Blob storage configuration

        Raises:
            StorageConfigurationError: If S3 configuration is incomplete
        """
        if not config.is_s3_configured():
            raise StorageConfigurationError(
                "S3 configuration is incomplete. Please check environment variables."
            )

        self.config = config
        self.bucket_name = config.s3_bucket_name
        self._client = None  # Will be initialized when needed

    def _get_client(self):
        """Get or create S3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    's3',
                    endpoint_url=self.config.s3_endpoint_url,
                    region_name=self.config.s3_region,
                    aws_access_key_id=self.config.s3_access_key_id,
                    aws_secret_access_key=self.config.s3_secret_access_key,
                    config=boto3.Config(
                        retries={'max_attempts': self.config.max_retries},
                        connect_timeout=self.config.connection_timeout,
                        read_timeout=self.config.connection_timeout,
                    )
                )
            except ImportError:
                raise StorageConfigurationError(
                    "boto3 is required for S3 storage. Install with: pip install boto3"
                )
            except Exception as e:
                raise StorageConnectionError(f"Failed to create S3 client", cause=e)

        return self._client

    def upload(self, blob_path: str, data: BinaryIO, content_type: Optional[str] = None) -> str:
        """Upload data to S3-compatible storage."""
        client = self._get_client()

        # Prepare extra args
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        try:
            # Reset stream position in case it was read before
            if hasattr(data, 'seek'):
                data.seek(0)

            client.put_object(
                Bucket=self.bucket_name,
                Key=blob_path,
                Body=data,
                **extra_args
            )

            return blob_path

        except Exception as e:
            raise StorageError(f"Failed to upload blob: {blob_path}", blob_path, e)

    def download(self, blob_path: str) -> Tuple[BinaryIO, Optional[str]]:
        """Download data from S3-compatible storage."""
        client = self._get_client()

        try:
            response = client.get_object(Bucket=self.bucket_name, Key=blob_path)

            # Create a BytesIO object with the content
            data = io.BytesIO(response['Body'].read())

            # Get content type from response
            content_type = response.get('ContentType')

            return data, content_type

        except client.exceptions.NoSuchKey:
            raise BlobNotFoundError(blob_path)
        except Exception as e:
            raise StorageError(f"Failed to download blob: {blob_path}", blob_path, e)

    def exists(self, blob_path: str) -> bool:
        """Check if a blob exists in S3-compatible storage."""
        client = self._get_client()

        try:
            client.head_object(Bucket=self.bucket_name, Key=blob_path)
            return True

        except client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            # Log the error but return False for existence check
            # This prevents false negatives for temporary network issues
            return False

    def delete(self, blob_path: str) -> bool:
        """Delete a blob from S3-compatible storage."""
        client = self._get_client()

        try:
            client.delete_object(Bucket=self.bucket_name, Key=blob_path)
            return True

        except client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            raise StorageError(f"Failed to delete blob: {blob_path}", blob_path, e)

    def get_url(self, blob_path: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """Get a presigned URL for accessing the blob."""
        client = self._get_client()

        try:
            url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': blob_path},
                ExpiresIn=expires_in_seconds
            )
            return url

        except Exception as e:
            # Log error but don't raise - URL generation failure shouldn't break the app
            return None

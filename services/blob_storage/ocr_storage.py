"""OCR-specific blob storage service for handling raw OCR response data."""

import json
import gzip
import logging
import hashlib
from datetime import datetime
from io import BytesIO
from typing import Dict, Any, Optional

from .service import BlobStorageService
from .config import BlobStorageConfig


logger = logging.getLogger(__name__)


class OCRBlobStorageService:
    """Specialized blob storage service for OCR responses with compression and structured naming."""

    def __init__(self, blob_storage_service: BlobStorageService):
        """
        Initialize OCR blob storage service.

        Args:
            blob_storage_service: Base blob storage service instance
        """
        self.storage_service = blob_storage_service

    def store_ocr_response(
        self,
        ocr_run_id: int,
        json_response: Dict[str, Any],
        ocr_engine: str
    ) -> str:
        """
        Store OCR response JSON with compression and structured naming.

        Args:
            ocr_run_id: OCR run ID for naming
            json_response: Raw JSON response from OCR engine
            ocr_engine: Name of the OCR engine (for metadata)

        Returns:
            Storage path where the response was stored
        """
        try:
            # Generate structured blob path
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            blob_path = f"ocr-runs/{ocr_run_id}/{timestamp}.json.gz"

            # Convert to JSON string and compress
            json_str = json.dumps(json_response, indent=2)
            compressed_data = gzip.compress(json_str.encode('utf-8'))

            # Upload compressed data
            blob_io = BytesIO(compressed_data)
            stored_path = self.storage_service.upload_blob(
                blob_path,
                blob_io,
                content_type="application/json"
            )

            logger.info(
                f"Stored OCR response for run {ocr_run_id} at {stored_path} "
                f"(original size: {len(json_str)} bytes, "
                f"compressed: {len(compressed_data)} bytes, "
                f"ratio: {len(compressed_data)/len(json_str):.2f})"
            )

            return stored_path

        except Exception as e:
            logger.error(f"Failed to store OCR response for run {ocr_run_id}: {e}")
            raise

    def retrieve_ocr_response(self, blob_path: str) -> Dict[str, Any]:
        """
        Retrieve and decompress OCR response JSON.

        Args:
            blob_path: Storage path of the OCR response

        Returns:
            Decompressed JSON response as dictionary
        """
        try:
            # Download compressed data
            data_stream, content_type = self.storage_service.download_blob(blob_path)

            # Read and decompress
            compressed_data = data_stream.read()
            decompressed_data = gzip.decompress(compressed_data)
            json_str = decompressed_data.decode('utf-8')

            # Parse JSON
            json_response = json.loads(json_str)

            logger.info(
                f"Retrieved OCR response from {blob_path} "
                f"(compressed: {len(compressed_data)} bytes, "
                f"decompressed: {len(decompressed_data)} bytes)"
            )

            return json_response

        except Exception as e:
            logger.error(f"Failed to retrieve OCR response from {blob_path}: {e}")
            raise

    def delete_ocr_response(self, blob_path: str) -> bool:
        """
        Delete OCR response from storage.

        Args:
            blob_path: Storage path to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            result = self.storage_service.delete_blob(blob_path)

            if result:
                logger.info(f"Deleted OCR response from {blob_path}")
            else:
                logger.info(f"OCR response not found for deletion: {blob_path}")

            return result

        except Exception as e:
            logger.error(f"Failed to delete OCR response from {blob_path}: {e}")
            raise

    def get_ocr_response_url(self, blob_path: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """
        Get temporary URL for OCR response access.

        Args:
            blob_path: Storage path of the OCR response
            expires_in_seconds: URL expiration time

        Returns:
            Temporary URL if supported, None otherwise
        """
        try:
            return self.storage_service.get_blob_url(blob_path, expires_in_seconds)
        except Exception as e:
            logger.error(f"Failed to get OCR response URL for {blob_path}: {e}")
            raise

    def ocr_response_exists(self, blob_path: str) -> bool:
        """
        Check if OCR response exists in storage.

        Args:
            blob_path: Storage path to check

        Returns:
            True if exists, False otherwise
        """
        try:
            return self.storage_service.blob_exists(blob_path)
        except Exception as e:
            logger.error(f"Failed to check OCR response existence at {blob_path}: {e}")
            raise


def create_ocr_blob_storage_service(
    blob_storage_service: Optional[BlobStorageService] = None,
    config: Optional[BlobStorageConfig] = None
) -> OCRBlobStorageService:
    """
    Factory function to create an OCR blob storage service.

    Args:
        blob_storage_service: Optional existing blob storage service
        config: Optional blob storage configuration

    Returns:
        Configured OCR blob storage service
    """
    if blob_storage_service is None:
        blob_storage_service = BlobStorageService(config)

    return OCRBlobStorageService(blob_storage_service)

"""Pytesseract OCR service implementation."""

import json
import time
import tempfile
from typing import Dict, Any, Optional, List
from pathlib import Path

import pytesseract
from PIL import Image
import numpy as np
from pdf2image import convert_from_path

from .interface import OCRServiceInterface, OCRError, OCRConfigurationError, OCRProcessingError
from services.blob_storage.interface import BlobStorageInterface
from utils.logging import get_logger, log_ocr_operation
from utils.metrics import record_ocr_metrics, MetricsTimer

logger = get_logger(__name__)


class PytesseractOCRService(OCRServiceInterface):
    """OCR service using Pytesseract (Tesseract OCR)."""

    def __init__(
        self,
        storage_service: Optional[BlobStorageInterface] = None,
        tesseract_cmd: Optional[str] = None,
        language: str = "eng",
        config: Optional[str] = None
    ):
        """
        Initialize Pytesseract OCR service.

        Args:
            storage_service: Optional blob storage service for storing raw responses
            tesseract_cmd: Path to tesseract executable (auto-detected if None)
            language: Language for OCR (default: 'eng')
            config: Additional tesseract configuration options
        """
        self.storage_service = storage_service
        self.language = language
        self.config = config or ""
        
        # Set tesseract executable path if provided
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # Test tesseract availability
        self._validate_tesseract()
        
        logger.info(
            "Pytesseract OCR service initialized",
            language=self.language,
            tesseract_cmd=pytesseract.pytesseract.tesseract_cmd
        )

    def _validate_tesseract(self):
        """Validate that Tesseract is properly installed and accessible."""
        try:
            # Test with a small dummy image
            test_image = Image.new('RGB', (100, 50), color='white')
            pytesseract.image_to_string(test_image)
            logger.info("Tesseract validation successful")
        except Exception as e:
            logger.error("Tesseract validation failed", error=str(e))
            raise OCRConfigurationError(
                f"Tesseract is not properly configured: {str(e)}",
                service_name="pytesseract",
                original_error=e
            )

    def analyze_document(self, document_path: Path, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a document using Pytesseract OCR.

        Args:
            document_path: Path to the document file
            features: List of features to enable (not used for Pytesseract)

        Returns:
            Dictionary containing OCR results and metadata

        Raises:
            OCRError: If document analysis fails
        """
        document_id = document_path.stem

        # Use metrics timer for automatic metrics collection
        with MetricsTimer("pytesseract") as timer:
            log_ocr_operation(
                logger,
                engine="pytesseract",
                operation="analyze_document",
                document_id=document_id,
                document_path=str(document_path)
            )
            
            # Convert document to images if needed
            images = self._convert_to_images(document_path)

            # Process each image/page
            all_text = []
            all_data = []
            total_confidence = 0.0
            confidence_count = 0

            for page_num, image in enumerate(images, 1):
                log_ocr_operation(
                    logger,
                    engine="pytesseract",
                    operation="process_page",
                    document_id=document_id,
                    page_num=page_num,
                    total_pages=len(images)
                )

                # Extract text
                page_text = pytesseract.image_to_string(
                    image,
                    lang=self.language,
                    config=self.config
                ).strip()

                # Get detailed data with confidence scores
                page_data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    config=self.config,
                    output_type=pytesseract.Output.DICT
                )

                # Calculate page confidence (average of word confidences > 0)
                word_confidences = [conf for conf in page_data['conf'] if conf > 0]
                page_confidence = sum(word_confidences) / len(word_confidences) if word_confidences else 0.0

                all_text.append(page_text)
                all_data.append({
                    'page': page_num,
                    'text': page_text,
                    'confidence': page_confidence / 100.0,  # Convert to 0-1 scale
                    'word_count': len(page_text.split()) if page_text else 0,
                    'data': page_data
                })

                total_confidence += page_confidence
                confidence_count += 1

            # Calculate overall metrics
            extracted_text = "\n\n".join(all_text)
            word_count = len(extracted_text.split()) if extracted_text else 0
            average_confidence = (total_confidence / confidence_count / 100.0) if confidence_count > 0 else 0.0

            # Set metrics for the timer
            timer.set_pages(len(images))
            timer.set_words(word_count)
            timer.set_confidence(average_confidence)

            # Prepare result
            result = {
                'text': extracted_text,
                'tables': [],  # Pytesseract doesn't extract structured tables
                'key_value_pairs': [],  # Pytesseract doesn't extract key-value pairs
                'pages': all_data,
                'raw_response': {
                    'engine': 'pytesseract',
                    'language': self.language,
                    'config': self.config,
                    'pages_data': all_data
                },
                'metrics': {
                    'page_count': len(images),
                    'word_count': word_count,
                    'average_confidence': average_confidence,
                    'table_count': 0,
                    'latency_ms': timer.start_time and (time.time() - timer.start_time) * 1000 or 0
                }
            }

            # Store raw response if storage service is available
            if self.storage_service:
                raw_response_path = self._store_raw_response(document_id, result['raw_response'])
                result['raw_response_path'] = raw_response_path

            log_ocr_operation(
                logger,
                engine="pytesseract",
                operation="analyze_document",
                document_id=document_id,
                success=True,
                page_count=len(images),
                word_count=word_count,
                confidence=average_confidence
            )

            return result
            
        except Exception as e:
            # Record failed metrics
            record_ocr_metrics(
                engine="pytesseract",
                success=False,
                latency_ms=timer.start_time and (time.time() - timer.start_time) * 1000 or 0
            )

            log_ocr_operation(
                logger,
                engine="pytesseract",
                operation="analyze_document",
                document_id=document_id,
                success=False,
                error=str(e)
            )

            raise OCRProcessingError(
                f"Failed to process document with Pytesseract: {str(e)}",
                service_name="pytesseract",
                original_error=e
            )

    def extract_text(self, analysis_result: Dict[str, Any]) -> str:
        """Extract plain text from analysis results."""
        return analysis_result.get('text', '')

    def extract_tables(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables from analysis results (not supported by Pytesseract)."""
        return analysis_result.get('tables', [])

    def extract_key_value_pairs(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key-value pairs from analysis results (not supported by Pytesseract)."""
        return analysis_result.get('key_value_pairs', [])

    def calculate_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics from analysis results."""
        return analysis_result.get('metrics', {})

    def get_supported_features(self) -> List[str]:
        """Get list of supported features for Pytesseract."""
        return ['text_recognition', 'multi_page', 'confidence_scores']

    def _convert_to_images(self, document_path: Path) -> List[Image.Image]:
        """
        Convert document to PIL Images.
        
        Args:
            document_path: Path to document file
            
        Returns:
            List of PIL Images (one per page)
        """
        file_extension = document_path.suffix.lower()
        
        if file_extension == '.pdf':
            # Convert PDF to images
            try:
                logger.debug("Converting PDF to images", document_path=str(document_path))
                images = convert_from_path(str(document_path))
                logger.debug(f"Converted PDF to {len(images)} images")
                return images
            except Exception as e:
                raise OCRProcessingError(
                    f"Failed to convert PDF to images: {str(e)}",
                    service_name="pytesseract",
                    original_error=e
                )
        else:
            # Load single image
            try:
                logger.debug("Loading image file", document_path=str(document_path))
                image = Image.open(document_path)
                # Convert to RGB if needed
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                return [image]
            except Exception as e:
                raise OCRProcessingError(
                    f"Failed to load image: {str(e)}",
                    service_name="pytesseract",
                    original_error=e
                )

    def _store_raw_response(self, document_id: str, raw_response: Dict[str, Any]) -> str:
        """Store raw Pytesseract response in blob storage."""
        if not self.storage_service:
            raise OCRError("Storage service not available", service_name="pytesseract")
        
        try:
            # Create blob path
            blob_path = f"ocr-runs/pytesseract/{document_id}/raw_response.json"
            
            # Convert to JSON and store
            json_data = json.dumps(raw_response, indent=2, default=str)
            
            # Use upload_string method if available, otherwise create temp file
            if hasattr(self.storage_service, 'upload_string'):
                self.storage_service.upload_string(json_data, blob_path, "application/json")
            else:
                # Fallback to binary upload
                import io
                data_stream = io.BytesIO(json_data.encode('utf-8'))
                self.storage_service.upload(blob_path, data_stream, "application/json")
            
            logger.info(
                "Raw Pytesseract response stored",
                document_id=document_id,
                blob_path=blob_path
            )
            
            return blob_path
            
        except Exception as e:
            logger.error(
                "Failed to store raw Pytesseract response",
                error=str(e),
                document_id=document_id
            )
            raise OCRError(
                f"Storage failed: {str(e)}",
                service_name="pytesseract",
                original_error=e
            )

    def get_languages(self) -> List[str]:
        """Get list of available languages in Tesseract."""
        try:
            languages = pytesseract.get_languages(config='')
            return languages
        except Exception as e:
            logger.warning("Failed to get available languages", error=str(e))
            return ['eng']  # Default fallback

    def health_check(self) -> Dict[str, Any]:
        """Check if Pytesseract service is healthy."""
        try:
            # Test with a small image
            test_image = Image.new('RGB', (100, 30), color='white')
            pytesseract.image_to_string(test_image)
            
            # Get version
            version = pytesseract.get_tesseract_version()
            
            return {
                'status': 'healthy',
                'service': 'pytesseract',
                'version': str(version),
                'languages': self.get_languages()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'service': 'pytesseract',
                'error': str(e)
            }

"""PaddleOCR service implementation."""

import json
import time
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from paddleocr import PaddleOCR

from .interface import OCRServiceInterface, OCRError, OCRConfigurationError, OCRProcessingError
from services.blob_storage.interface import BlobStorageInterface
from utils.logging import get_logger

logger = get_logger(__name__)


class PaddleOCRService(OCRServiceInterface):
    """OCR service using PaddleOCR."""

    def __init__(
        self,
        storage_service: Optional[BlobStorageInterface] = None,
        lang: str = 'en',
        use_angle_cls: bool = True,
        use_gpu: bool = False,
        show_log: bool = False
    ):
        """
        Initialize PaddleOCR service.

        Args:
            storage_service: Optional blob storage service for storing raw responses
            lang: Language for OCR (default: 'en')
            use_angle_cls: Whether to use angle classification
            use_gpu: Whether to use GPU acceleration
            show_log: Whether to show PaddleOCR logs
        """
        self.storage_service = storage_service
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.use_gpu = use_gpu
        
        # Initialize PaddleOCR
        try:
            logger.info(
                "Initializing PaddleOCR",
                lang=lang,
                use_angle_cls=use_angle_cls,
                use_gpu=use_gpu
            )
            
            self.ocr = PaddleOCR(
                lang=lang,
                use_angle_cls=use_angle_cls,
                use_gpu=use_gpu,
                show_log=show_log
            )
            
            # Test PaddleOCR with a dummy image
            self._validate_paddleocr()
            
            logger.info("PaddleOCR service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize PaddleOCR", error=str(e))
            raise OCRConfigurationError(
                f"PaddleOCR initialization failed: {str(e)}",
                service_name="paddleocr",
                original_error=e
            )

    def _validate_paddleocr(self):
        """Validate that PaddleOCR is properly configured."""
        try:
            # Test with a small dummy image
            test_image = np.ones((50, 100, 3), dtype=np.uint8) * 255
            result = self.ocr.ocr(test_image, cls=self.use_angle_cls)
            logger.info("PaddleOCR validation successful")
        except Exception as e:
            logger.error("PaddleOCR validation failed", error=str(e))
            raise OCRConfigurationError(
                f"PaddleOCR is not properly configured: {str(e)}",
                service_name="paddleocr",
                original_error=e
            )

    def analyze_document(self, document_path: Path, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a document using PaddleOCR.

        Args:
            document_path: Path to the document file
            features: List of features to enable (not used for PaddleOCR)

        Returns:
            Dictionary containing OCR results and metadata

        Raises:
            OCRError: If document analysis fails
        """
        start_time = time.time()
        
        try:
            logger.info("Starting PaddleOCR processing", document_path=str(document_path))
            
            # Convert document to images if needed
            images = self._convert_to_images(document_path)
            
            # Process each image/page
            all_text = []
            all_data = []
            total_confidence = 0.0
            confidence_count = 0
            
            for page_num, image in enumerate(images, 1):
                logger.debug(f"Processing page {page_num}/{len(images)}")
                
                # Convert PIL Image to numpy array for PaddleOCR
                image_array = np.array(image)
                
                # Run OCR on the image
                result = self.ocr.ocr(image_array, cls=self.use_angle_cls)
                
                # Extract text and confidence from result
                page_text_lines = []
                page_confidences = []
                bounding_boxes = []
                
                if result and result[0]:  # Check if result is not None and not empty
                    for line in result[0]:
                        if line and len(line) >= 2:
                            bbox, (text, confidence) = line
                            page_text_lines.append(text)
                            page_confidences.append(confidence)
                            bounding_boxes.append(bbox)
                
                page_text = '\n'.join(page_text_lines)
                page_confidence = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0
                
                all_text.append(page_text)
                all_data.append({
                    'page': page_num,
                    'text': page_text,
                    'confidence': page_confidence,
                    'word_count': len(page_text.split()) if page_text else 0,
                    'bounding_boxes': bounding_boxes,
                    'line_confidences': page_confidences,
                    'raw_result': result
                })
                
                total_confidence += page_confidence
                confidence_count += 1
            
            # Calculate overall metrics
            latency_ms = int((time.time() - start_time) * 1000)
            extracted_text = "\n\n".join(all_text)
            word_count = len(extracted_text.split()) if extracted_text else 0
            average_confidence = total_confidence / confidence_count if confidence_count > 0 else 0.0
            
            # Prepare result
            result = {
                'text': extracted_text,
                'tables': [],  # PaddleOCR can detect tables but basic version doesn't extract structured data
                'key_value_pairs': [],  # PaddleOCR doesn't extract key-value pairs in basic mode
                'pages': all_data,
                'raw_response': {
                    'engine': 'paddleocr',
                    'language': self.lang,
                    'use_angle_cls': self.use_angle_cls,
                    'use_gpu': self.use_gpu,
                    'pages_data': all_data
                },
                'metrics': {
                    'page_count': len(images),
                    'word_count': word_count,
                    'average_confidence': average_confidence,
                    'table_count': 0,
                    'latency_ms': latency_ms
                }
            }
            
            # Store raw response if storage service is available
            if self.storage_service:
                document_id = document_path.stem
                raw_response_path = self._store_raw_response(document_id, result['raw_response'])
                result['raw_response_path'] = raw_response_path
            
            logger.info(
                "PaddleOCR processing completed",
                document_path=str(document_path),
                page_count=len(images),
                word_count=word_count,
                confidence=average_confidence,
                latency_ms=latency_ms
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "PaddleOCR processing failed",
                document_path=str(document_path),
                error=str(e)
            )
            raise OCRProcessingError(
                f"Failed to process document with PaddleOCR: {str(e)}",
                service_name="paddleocr",
                original_error=e
            )

    def extract_text(self, analysis_result: Dict[str, Any]) -> str:
        """Extract plain text from analysis results."""
        return analysis_result.get('text', '')

    def extract_tables(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables from analysis results (basic PaddleOCR doesn't support structured table extraction)."""
        return analysis_result.get('tables', [])

    def extract_key_value_pairs(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key-value pairs from analysis results (not supported by basic PaddleOCR)."""
        return analysis_result.get('key_value_pairs', [])

    def calculate_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics from analysis results."""
        return analysis_result.get('metrics', {})

    def get_supported_features(self) -> List[str]:
        """Get list of supported features for PaddleOCR."""
        features = ['text_recognition', 'multi_page', 'confidence_scores', 'bounding_boxes']
        if self.use_angle_cls:
            features.append('angle_classification')
        return features

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
                    service_name="paddleocr",
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
                    service_name="paddleocr",
                    original_error=e
                )

    def _store_raw_response(self, document_id: str, raw_response: Dict[str, Any]) -> str:
        """Store raw PaddleOCR response in blob storage."""
        if not self.storage_service:
            raise OCRError("Storage service not available", service_name="paddleocr")
        
        try:
            # Create blob path
            blob_path = f"ocr-runs/paddleocr/{document_id}/raw_response.json"
            
            # Convert to JSON and store (handle numpy arrays)
            json_data = json.dumps(raw_response, indent=2, default=self._json_serializer)
            
            # Use upload_string method if available, otherwise create temp file
            if hasattr(self.storage_service, 'upload_string'):
                self.storage_service.upload_string(json_data, blob_path, "application/json")
            else:
                # Fallback to binary upload
                import io
                data_stream = io.BytesIO(json_data.encode('utf-8'))
                self.storage_service.upload(blob_path, data_stream, "application/json")
            
            logger.info(
                "Raw PaddleOCR response stored",
                document_id=document_id,
                blob_path=blob_path
            )
            
            return blob_path
            
        except Exception as e:
            logger.error(
                "Failed to store raw PaddleOCR response",
                error=str(e),
                document_id=document_id
            )
            raise OCRError(
                f"Storage failed: {str(e)}",
                service_name="paddleocr",
                original_error=e
            )

    def _json_serializer(self, obj):
        """Custom JSON serializer for numpy arrays and other non-serializable objects."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        else:
            return str(obj)

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages for PaddleOCR."""
        # PaddleOCR supports many languages
        return [
            'ch', 'en', 'fr', 'german', 'korean', 'japan',
            'chinese_cht', 'ta', 'te', 'ka', 'latin', 'arabic',
            'cyrillic', 'devanagari'
        ]

    def health_check(self) -> Dict[str, Any]:
        """Check if PaddleOCR service is healthy."""
        try:
            # Test with a small image
            test_image = np.ones((50, 100, 3), dtype=np.uint8) * 255
            result = self.ocr.ocr(test_image, cls=self.use_angle_cls)
            
            return {
                'status': 'healthy',
                'service': 'paddleocr',
                'language': self.lang,
                'use_angle_cls': self.use_angle_cls,
                'use_gpu': self.use_gpu,
                'supported_languages': self.get_supported_languages()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'service': 'paddleocr',
                'error': str(e)
            }

    def detect_and_recognize(self, image_path: str) -> Dict[str, Any]:
        """
        Perform text detection and recognition on an image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dictionary with detection and recognition results
        """
        try:
            result = self.ocr.ocr(image_path, cls=self.use_angle_cls)
            
            # Parse results
            texts = []
            boxes = []
            scores = []
            
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        bbox, (text, confidence) = line
                        texts.append(text)
                        boxes.append(bbox)
                        scores.append(confidence)
            
            return {
                'texts': texts,
                'boxes': boxes,
                'scores': scores,
                'raw_result': result
            }
            
        except Exception as e:
            logger.error("PaddleOCR detection and recognition failed", error=str(e))
            raise OCRProcessingError(
                f"Detection and recognition failed: {str(e)}",
                service_name="paddleocr",
                original_error=e
            )

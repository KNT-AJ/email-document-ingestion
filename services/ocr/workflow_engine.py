"""Enhanced OCR engine base class for workflow orchestration."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import time
import logging
from datetime import datetime

from .interface import OCRServiceInterface, OCRError
from .workflow_config import OCRResult, EngineConfig, QualityThresholds


logger = logging.getLogger(__name__)


class OCREngine(ABC):
    """Abstract base class for OCR engines in the orchestration workflow.
    
    This class extends the basic OCR interface with workflow-specific features
    including quality metrics, preprocessing, and structured result format.
    """
    
    def __init__(self, config: EngineConfig):
        """Initialize OCR engine with configuration.
        
        Args:
            config: Engine configuration containing settings and thresholds
        """
        self.config = config
        self.logger = logging.getLogger(f"ocr.engine.{self.config.engine_name}")
        self._service: Optional[OCRServiceInterface] = None
        
    @property
    def engine_name(self) -> str:
        """Get the engine name."""
        return self.config.engine_name
    
    @property
    def engine_type(self) -> str:
        """Get the engine type."""
        return self.config.engine_type.value
    
    @abstractmethod
    def _create_service(self) -> OCRServiceInterface:
        """Create the underlying OCR service implementation.
        
        Returns:
            Configured OCR service instance
        """
        pass
    
    def _get_service(self) -> OCRServiceInterface:
        """Get or create the underlying OCR service."""
        if self._service is None:
            self._service = self._create_service()
        return self._service
    
    def preprocess_document(self, document_path: Path) -> Path:
        """Preprocess document for optimal OCR results.
        
        Args:
            document_path: Path to the original document
            
        Returns:
            Path to the preprocessed document
        """
        if not self.config.preprocessing_enabled:
            return document_path
            
        try:
            self.logger.info(f"Preprocessing document: {document_path}")
            
            # Import image processing libraries
            try:
                from PIL import Image, ImageEnhance, ImageFilter
                import cv2
                import numpy as np
            except ImportError as e:
                self.logger.warning(f"Image processing libraries not available: {e}")
                return document_path
            
            # Load image
            if document_path.suffix.lower() in ['.pdf']:
                # For PDFs, we would need pdf2image, but for now return original
                self.logger.info("PDF preprocessing not implemented, using original")
                return document_path
                
            # Load and process image
            image = Image.open(document_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply preprocessing based on configuration
            preprocessing_config = self.config.preprocessing_config
            
            if preprocessing_config.get('grayscale', False):
                image = image.convert('L')
                self.logger.debug("Applied grayscale conversion")
            
            if preprocessing_config.get('noise_reduction', False):
                # Apply noise reduction
                image = image.filter(ImageFilter.MedianFilter(size=3))
                self.logger.debug("Applied noise reduction")
            
            if preprocessing_config.get('adaptive_threshold', False) and image.mode == 'L':
                # Convert PIL to OpenCV for adaptive thresholding
                cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_GRAY2BGR)
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                adaptive_thresh = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )
                image = Image.fromarray(adaptive_thresh)
                self.logger.debug("Applied adaptive thresholding")
            
            if preprocessing_config.get('dpi_optimization', False):
                # Ensure minimum DPI for OCR
                min_dpi = 300
                current_dpi = image.info.get('dpi', (72, 72))
                if isinstance(current_dpi, tuple):
                    current_dpi = current_dpi[0]
                
                if current_dpi < min_dpi:
                    scale_factor = min_dpi / current_dpi
                    new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
                    image = image.resize(new_size, Image.LANCZOS)
                    self.logger.debug(f"Upscaled image from {current_dpi} DPI to {min_dpi} DPI")
            
            # Save preprocessed image
            preprocessed_path = document_path.parent / f"preprocessed_{document_path.name}"
            image.save(preprocessed_path)
            
            self.logger.info(f"Preprocessing completed: {preprocessed_path}")
            return preprocessed_path
            
        except Exception as e:
            self.logger.error(f"Preprocessing failed: {e}")
            # Return original path if preprocessing fails
            return document_path
    
    def process_document(self, document_path: Path, features: Optional[List[str]] = None) -> OCRResult:
        """Process a document and return standardized result.
        
        Args:
            document_path: Path to the document file
            features: List of features to enable
            
        Returns:
            Standardized OCR result
            
        Raises:
            OCRError: If processing fails
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting OCR processing with {self.engine_name}")
            
            # Preprocess document if enabled
            processed_path = self.preprocess_document(document_path)
            
            # Get the underlying service
            service = self._get_service()
            
            # Perform OCR analysis
            analysis_result = service.analyze_document(processed_path, features)
            
            # Extract structured content
            extracted_text = service.extract_text(analysis_result)
            extracted_tables = service.extract_tables(analysis_result)
            extracted_key_value_pairs = service.extract_key_value_pairs(analysis_result)
            
            # Calculate metrics
            metrics = service.calculate_metrics(analysis_result)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Create standardized result
            result = OCRResult(
                engine_type=self.config.engine_type,
                engine_name=self.config.engine_name,
                processing_time_seconds=processing_time,
                processed_at=datetime.utcnow().isoformat(),
                confidence_score=self._extract_confidence_score(analysis_result, metrics),
                word_count=metrics.get('word_count', 0),
                page_count=metrics.get('page_count', 1),
                extracted_text=extracted_text,
                extracted_tables=extracted_tables,
                extracted_key_value_pairs=extracted_key_value_pairs,
                language_detected=analysis_result.get('language', None),
                quality_metrics=self._calculate_quality_metrics(analysis_result, metrics)
            )
            
            # Clean up preprocessed file if it's different from original
            if processed_path != document_path and processed_path.exists():
                try:
                    processed_path.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to clean up preprocessed file: {e}")
            
            self.logger.info(
                f"OCR processing completed successfully",
                extra={
                    'engine': self.engine_name,
                    'processing_time': processing_time,
                    'confidence': result.confidence_score,
                    'word_count': result.word_count,
                    'page_count': result.page_count
                }
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(
                f"OCR processing failed",
                extra={
                    'engine': self.engine_name,
                    'processing_time': processing_time,
                    'error': str(e)
                }
            )
            raise OCRError(
                f"OCR processing failed with {self.engine_name}: {str(e)}",
                service_name=self.engine_name,
                original_error=e
            )
    
    def _extract_confidence_score(self, analysis_result: Dict[str, Any], metrics: Dict[str, Any]) -> float:
        """Extract confidence score from analysis result.
        
        Args:
            analysis_result: Raw analysis result from OCR service
            metrics: Calculated metrics
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Try to get confidence from metrics first
        confidence = metrics.get('average_confidence', 0.0)
        
        # If not available, try to extract from raw response
        if confidence == 0.0:
            # This would be engine-specific logic
            confidence = analysis_result.get('confidence', 0.8)  # Default fallback
        
        # Ensure confidence is in range [0.0, 1.0]
        if confidence > 1.0:
            confidence = confidence / 100.0  # Convert percentage to decimal
        
        return max(0.0, min(1.0, confidence))
    
    def _calculate_quality_metrics(self, analysis_result: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate detailed quality metrics for the result.
        
        Args:
            analysis_result: Raw analysis result from OCR service
            metrics: Calculated metrics
            
        Returns:
            Dictionary of quality metrics
        """
        quality_metrics = {
            'confidence_score': self._extract_confidence_score(analysis_result, metrics),
            'word_count': metrics.get('word_count', 0),
            'page_count': metrics.get('page_count', 1),
            'table_count': metrics.get('table_count', 0),
            'processing_time_seconds': analysis_result.get('processing_time', 0),
        }
        
        # Calculate derived metrics
        text_length = len(analysis_result.get('text', ''))
        quality_metrics['text_length'] = text_length
        quality_metrics['average_word_length'] = (
            text_length / quality_metrics['word_count'] if quality_metrics['word_count'] > 0 else 0
        )
        
        # Engine-specific quality metrics would be added by subclasses
        return quality_metrics
    
    def evaluate_quality(self, result: OCRResult, thresholds: Optional[QualityThresholds] = None) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate if the OCR result meets quality thresholds.
        
        Args:
            result: OCR result to evaluate
            thresholds: Quality thresholds to use (defaults to engine config)
            
        Returns:
            Tuple of (meets_quality, evaluation_details)
        """
        if thresholds is None:
            thresholds = self.config.quality_thresholds or QualityThresholds()
        
        evaluation = {
            'confidence_check': result.confidence_score >= thresholds.min_confidence_score,
            'word_count_check': result.word_count > 0,
            'page_count_check': result.page_count >= thresholds.min_pages_processed,
            'processing_time_check': result.processing_time_seconds <= thresholds.max_processing_time_seconds,
        }
        
        # Calculate word recognition rate (simplified)
        expected_words = max(100, result.word_count)  # Assume at least 100 words expected
        word_recognition_rate = min(1.0, result.word_count / expected_words)
        evaluation['word_recognition_rate'] = word_recognition_rate
        evaluation['word_recognition_check'] = word_recognition_rate >= thresholds.min_word_recognition_rate
        
        # Overall quality assessment
        all_checks_passed = all(evaluation[key] for key in evaluation if key.endswith('_check'))
        
        evaluation['overall_quality'] = all_checks_passed
        evaluation['quality_score'] = sum(1 for key in evaluation if key.endswith('_check') and evaluation[key]) / len([key for key in evaluation if key.endswith('_check')])
        
        self.logger.info(
            f"Quality evaluation completed",
            extra={
                'engine': self.engine_name,
                'overall_quality': all_checks_passed,
                'quality_score': evaluation['quality_score'],
                'confidence': result.confidence_score,
                'word_count': result.word_count
            }
        )
        
        return all_checks_passed, evaluation


class AzureOCREngine(OCREngine):
    """Azure Document Intelligence OCR engine."""
    
    def _create_service(self) -> OCRServiceInterface:
        """Create Azure Document Intelligence service."""
        from .azure_document_intelligence import AzureDocumentIntelligenceService
        return AzureDocumentIntelligenceService()


class GoogleOCREngine(OCREngine):
    """Google Document AI OCR engine."""
    
    def _create_service(self) -> OCRServiceInterface:
        """Create Google Document AI service."""
        from ..google_document_ai_service import GoogleDocumentAIService
        return GoogleDocumentAIService()


class MistralOCREngine(OCREngine):
    """Mistral Document AI OCR engine."""
    
    def _create_service(self) -> OCRServiceInterface:
        """Create Mistral Document AI service."""
        from .mistral_document_ai_service import MistralDocumentAIService
        return MistralDocumentAIService()


class TesseractOCREngine(OCREngine):
    """Tesseract OCR engine."""
    
    def _create_service(self) -> OCRServiceInterface:
        """Create Tesseract OCR service."""
        from .pytesseract_service import PyTesseractOCRService
        return PyTesseractOCRService()


class PaddleOCREngine(OCREngine):
    """PaddleOCR engine."""
    
    def _create_service(self) -> OCRServiceInterface:
        """Create PaddleOCR service."""
        from .paddleocr_service import PaddleOCRService
        return PaddleOCRService()


class TextractOCREngine(OCREngine):
    """AWS Textract OCR engine."""
    
    def _create_service(self) -> OCRServiceInterface:
        """Create AWS Textract service."""
        from .textract_service import TextractOCRService
        return TextractOCRService()


def create_ocr_engine(config: EngineConfig) -> OCREngine:
    """Factory function to create OCR engines based on configuration.
    
    Args:
        config: Engine configuration
        
    Returns:
        Configured OCR engine instance
        
    Raises:
        ValueError: If engine type is not supported
    """
    engine_classes = {
        'azure': AzureOCREngine,
        'google': GoogleOCREngine,
        'mistral': MistralOCREngine,
        'tesseract': TesseractOCREngine,
        'paddle': PaddleOCREngine,
        'textract': TextractOCREngine,
    }
    
    engine_type = config.engine_type.value
    if engine_type not in engine_classes:
        raise ValueError(f"Unsupported engine type: {engine_type}")
    
    return engine_classes[engine_type](config)

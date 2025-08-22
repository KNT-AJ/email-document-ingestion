"""High-level OCR service that provides unified interface for document processing."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .interface import OCRServiceInterface, OCRError
from .factory import get_ocr_service


logger = logging.getLogger(__name__)


class OCRService:
    """High-level OCR service for document processing."""

    def __init__(self, service_type: str = "azure"):
        """
        Initialize the OCR service.

        Args:
            service_type: Type of OCR service to use ('azure')
        """
        self.service_type = service_type
        self._ocr_service: Optional[OCRServiceInterface] = None

    @property
    def ocr_service(self) -> OCRServiceInterface:
        """Get the underlying OCR service implementation."""
        if self._ocr_service is None:
            try:
                self._ocr_service = get_ocr_service(self.service_type)
                logger.info(f"Initialized {self.service_type} OCR service")
            except Exception as e:
                logger.error(f"Failed to initialize OCR service: {e}")
                raise
        return self._ocr_service

    def analyze_document(self, document_path: Path, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a document using OCR.

        Args:
            document_path: Path to the document file
            features: List of features to enable

        Returns:
            Dictionary containing analysis results with text, tables, key_value_pairs, etc.

        Raises:
            OCRError: If document analysis fails
        """
        logger.info(f"Starting OCR analysis for document: {document_path}")

        try:
            result = self.ocr_service.analyze_document(document_path, features)

            # Log metrics
            metrics = self.calculate_metrics(result)
            logger.info(
                f"OCR analysis completed. Pages: {metrics.get('page_count', 0)}, "
                f"Words: {metrics.get('word_count', 0)}, "
                f"Tables: {metrics.get('table_count', 0)}, "
                f"Avg Confidence: {metrics.get('average_confidence', 0):.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"OCR analysis failed for {document_path}: {e}")
            raise

    def extract_text(self, document_path: Path) -> str:
        """
        Extract plain text from a document.

        Args:
            document_path: Path to the document file

        Returns:
            Extracted plain text

        Raises:
            OCRError: If text extraction fails
        """
        logger.info(f"Extracting text from document: {document_path}")

        try:
            analysis_result = self.analyze_document(document_path, features=[])
            return self.ocr_service.extract_text(analysis_result)

        except Exception as e:
            logger.error(f"Text extraction failed for {document_path}: {e}")
            raise

    def extract_tables(self, document_path: Path) -> List[Dict[str, Any]]:
        """
        Extract tables from a document.

        Args:
            document_path: Path to the document file

        Returns:
            List of extracted tables

        Raises:
            OCRError: If table extraction fails
        """
        logger.info(f"Extracting tables from document: {document_path}")

        try:
            analysis_result = self.analyze_document(document_path, features=['tables'])
            return self.ocr_service.extract_tables(analysis_result)

        except Exception as e:
            logger.error(f"Table extraction failed for {document_path}: {e}")
            raise

    def extract_key_value_pairs(self, document_path: Path) -> List[Dict[str, Any]]:
        """
        Extract key-value pairs from a document.

        Args:
            document_path: Path to the document file

        Returns:
            List of extracted key-value pairs

        Raises:
            OCRError: If key-value pair extraction fails
        """
        logger.info(f"Extracting key-value pairs from document: {document_path}")

        try:
            analysis_result = self.analyze_document(document_path, features=['key_value_pairs'])
            return self.ocr_service.extract_key_value_pairs(analysis_result)

        except Exception as e:
            logger.error(f"Key-value pair extraction failed for {document_path}: {e}")
            raise

    def calculate_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate metrics from analysis results.

        Args:
            analysis_result: Result from analyze_document

        Returns:
            Dictionary with metrics
        """
        return self.ocr_service.calculate_metrics(analysis_result)

    def get_supported_features(self) -> List[str]:
        """Get list of supported features for the current OCR service."""
        return self.ocr_service.get_supported_features()

    def process_document_comprehensive(self, document_path: Path) -> Dict[str, Any]:
        """
        Process a document with all available features.

        Args:
            document_path: Path to the document file

        Returns:
            Complete analysis result with all features enabled

        Raises:
            OCRError: If document processing fails
        """
        logger.info(f"Processing document comprehensively: {document_path}")

        # Enable all supported features
        features = self.get_supported_features()

        try:
            result = self.analyze_document(document_path, features)

            # Add calculated metrics
            result['metrics'] = self.calculate_metrics(result)

            return result

        except Exception as e:
            logger.error(f"Comprehensive document processing failed for {document_path}: {e}")
            raise

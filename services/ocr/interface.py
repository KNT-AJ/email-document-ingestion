"""Abstract interface for OCR services."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path


class OCRServiceInterface(ABC):
    """Abstract base class for OCR service implementations."""

    @abstractmethod
    def analyze_document(self, document_path: Path, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a document using OCR and return structured results.

        Args:
            document_path: Path to the document file
            features: List of features to enable (e.g., ['tables', 'key_value_pairs'])

        Returns:
            Dictionary containing:
            - text: Extracted plain text
            - tables: List of tables with cells
            - key_value_pairs: List of extracted key-value pairs
            - pages: Page information and metadata
            - raw_response: The raw API response for storage

        Raises:
            OCRError: If document analysis fails
        """
        pass

    @abstractmethod
    def extract_text(self, analysis_result: Dict[str, Any]) -> str:
        """
        Extract plain text from analysis results.

        Args:
            analysis_result: Result from analyze_document

        Returns:
            Concatenated plain text from all pages
        """
        pass

    @abstractmethod
    def extract_tables(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tables from analysis results.

        Args:
            analysis_result: Result from analyze_document

        Returns:
            List of tables with row_count, column_count, and cells
        """
        pass

    @abstractmethod
    def extract_key_value_pairs(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract key-value pairs from analysis results.

        Args:
            analysis_result: Result from analyze_document

        Returns:
            List of key-value pairs with keys, values, and confidence scores
        """
        pass

    @abstractmethod
    def calculate_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate metrics from analysis results.

        Args:
            analysis_result: Result from analyze_document

        Returns:
            Dictionary with metrics like:
            - page_count: Number of pages
            - word_count: Total word count
            - average_confidence: Average confidence score
            - table_count: Number of tables detected
        """
        pass

    @abstractmethod
    def get_supported_features(self) -> List[str]:
        """
        Get list of supported features for this OCR service.

        Returns:
            List of feature names (e.g., ['tables', 'key_value_pairs', 'languages'])
        """
        pass


class OCRError(Exception):
    """Base exception for OCR service errors."""

    def __init__(self, message: str, service_name: str = None, original_error: Exception = None):
        self.service_name = service_name
        self.original_error = original_error
        super().__init__(message)


class OCRConfigurationError(OCRError):
    """Raised when OCR service is not properly configured."""
    pass


class OCRProcessingError(OCRError):
    """Raised when document processing fails."""
    pass


class OCRTimeoutError(OCRError):
    """Raised when OCR processing times out."""
    pass

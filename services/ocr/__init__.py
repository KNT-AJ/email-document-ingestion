"""OCR services for document processing."""

from .interface import (
    OCRServiceInterface, 
    OCRError, 
    OCRConfigurationError, 
    OCRProcessingError, 
    OCRTimeoutError
)
from .pytesseract_service import PytesseractOCRService
from .paddleocr_service import PaddleOCRService
from .opensource_factory import OpenSourceOCRFactory, OpenSourceOCREngine

try:
    from .azure_document_intelligence import AzureDocumentIntelligenceService
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

__all__ = [
    "OCRServiceInterface",
    "OCRError",
    "OCRConfigurationError", 
    "OCRProcessingError",
    "OCRTimeoutError",
    "PytesseractOCRService",
    "PaddleOCRService", 
    "OpenSourceOCRFactory",
    "OpenSourceOCREngine"
]

if AZURE_AVAILABLE:
    __all__.append("AzureDocumentIntelligenceService")

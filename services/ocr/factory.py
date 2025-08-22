"""Factory for creating OCR service implementations."""

from typing import Optional
import logging

from .interface import OCRServiceInterface, OCRConfigurationError
from ..blob_storage.service import BlobStorageService


logger = logging.getLogger(__name__)


# Import OCR implementations
try:
    from .azure_document_intelligence import AzureDocumentIntelligenceService
except ImportError as e:
    logger.warning(f"Azure Document Intelligence not available: {e}")

try:
    from .textract_service import TextractOCRService
except ImportError as e:
    logger.warning(f"AWS Textract not available: {e}")

try:
    from .pytesseract_service import PyTesseractOCRService
except ImportError as e:
    logger.warning(f"PyTesseract not available: {e}")

try:
    from .paddleocr_service import PaddleOCRService
except ImportError as e:
    logger.warning(f"PaddleOCR not available: {e}")

try:
    from ...services.google_document_ai_service import GoogleDocumentAIService
except ImportError as e:
    logger.warning(f"Google Document AI not available: {e}")

try:
    from .mistral_document_ai_service import MistralDocumentAIService
except ImportError as e:
    logger.warning(f"Mistral Document AI not available: {e}")


class OCRServiceFactory:
    """Factory for creating OCR service implementations."""

    @staticmethod
    def create_service(service_type: str = "textract", blob_storage: Optional[BlobStorageService] = None) -> OCRServiceInterface:
        """
        Create an OCR service implementation based on type.

        Args:
            service_type: Type of OCR service to create ('textract', 'azure', 'tesseract', 'paddle', 'google')
            blob_storage: Optional blob storage service for storing raw responses

        Returns:
            Configured OCR service implementation

        Raises:
            OCRConfigurationError: If service type is unsupported or configuration fails
        """
        logger.info(f"Creating {service_type} OCR service implementation")

        service_type_lower = service_type.lower()

        if service_type_lower == "textract":
            try:
                return TextractOCRService(blob_storage=blob_storage)
            except Exception as e:
                raise OCRConfigurationError(
                    f"Failed to create AWS Textract service: {str(e)}",
                    service_name="AWS Textract",
                    original_error=e
                )

        elif service_type_lower == "azure":
            try:
                return AzureDocumentIntelligenceService()
            except Exception as e:
                raise OCRConfigurationError(
                    f"Failed to create Azure Document Intelligence service: {str(e)}",
                    service_name="Azure Document Intelligence",
                    original_error=e
                )

        elif service_type_lower in ("tesseract", "pytesseract"):
            try:
                return PyTesseractOCRService()
            except Exception as e:
                raise OCRConfigurationError(
                    f"Failed to create PyTesseract service: {str(e)}",
                    service_name="PyTesseract",
                    original_error=e
                )

        elif service_type_lower in ("paddle", "paddleocr"):
            try:
                return PaddleOCRService()
            except Exception as e:
                raise OCRConfigurationError(
                    f"Failed to create PaddleOCR service: {str(e)}",
                    service_name="PaddleOCR",
                    original_error=e
                )

        elif service_type_lower in ("google", "documentai"):
            try:
                return GoogleDocumentAIService()
            except Exception as e:
                raise OCRConfigurationError(
                    f"Failed to create Google Document AI service: {str(e)}",
                    service_name="Google Document AI",
                    original_error=e
                )

        elif service_type_lower in ("mistral", "mistralai"):
            try:
                return MistralDocumentAIService()
            except Exception as e:
                raise OCRConfigurationError(
                    f"Failed to create Mistral Document AI service: {str(e)}",
                    service_name="Mistral Document AI",
                    original_error=e
                )

        else:
            raise OCRConfigurationError(f"Unsupported OCR service type: {service_type}")

    @staticmethod
    def get_available_services() -> list[str]:
        """
        Get list of available OCR service types.

        Returns:
            List of service type strings that can be used with create_service
        """
        available = []
        
        # Test each service availability
        try:
            TextractOCRService
            available.append("textract")
        except NameError:
            pass

        try:
            AzureDocumentIntelligenceService
            available.append("azure")
        except NameError:
            pass

        try:
            PyTesseractOCRService
            available.append("tesseract")
        except NameError:
            pass

        try:
            PaddleOCRService
            available.append("paddle")
        except NameError:
            pass

        try:
            GoogleDocumentAIService
            available.append("google")
        except NameError:
            pass

        try:
            MistralDocumentAIService
            available.append("mistral")
        except NameError:
            pass

        return available


def get_ocr_service(service_type: str = "textract", blob_storage: Optional[BlobStorageService] = None) -> OCRServiceInterface:
    """
    Get a configured OCR service instance.

    This is a convenience function that uses the factory to create OCR service instances.

    Args:
        service_type: Type of OCR service to create
        blob_storage: Optional blob storage service for storing raw responses

    Returns:
        Configured OCR service implementation
    """
    return OCRServiceFactory.create_service(service_type, blob_storage=blob_storage)

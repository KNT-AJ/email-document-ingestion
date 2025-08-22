"""OCR engine adapter for Google Document AI."""

from typing import Dict, Any, Optional
from pathlib import Path

from services.google_document_ai_service import GoogleDocumentAIService, GoogleDocumentAIError
from services.blob_storage.interface import BlobStorageInterface


class GoogleDocumentAIOCREngine:
    """OCR engine adapter for Google Document AI integration with the OCR orchestration system."""

    def __init__(self, storage_service: Optional[BlobStorageInterface] = None):
        """Initialize Google Document AI OCR engine.

        Args:
            storage_service: Optional blob storage service for storing raw responses
        """
        self.service = GoogleDocumentAIService(storage_service=storage_service)

    def process_document(
        self,
        document_path: str,
        mime_type: str = "application/pdf",
        **kwargs
    ) -> Dict[str, Any]:
        """Process a document using Google Document AI.

        Args:
            document_path: Path to the document file
            mime_type: MIME type of the document
            **kwargs: Additional parameters (document_id, etc.)

        Returns:
            Dictionary containing OCR results in standardized format

        Raises:
            Exception: If processing fails
        """
        try:
            document_id = kwargs.get('document_id', f"doc_{hash(document_path)}")

            # Process document using Google Document AI
            result = self.service.process_document(
                document_path=document_path,
                mime_type=mime_type,
                document_id=document_id
            )

            # Return standardized result format
            return {
                'engine_name': 'google_document_ai',
                'document_id': document_id,
                'extracted_text': result['extracted_text'],
                'confidence_score': result['confidence_score'],
                'pages_count': result['pages_count'],
                'word_count': result['word_count'],
                'processing_time_ms': result['latency_ms'],
                'tables': result['tables'],
                'key_value_pairs': result['key_value_pairs'],
                'raw_response_path': result.get('raw_response_path'),
                'success': True,
                'error_message': None
            }

        except GoogleDocumentAIError as e:
            return {
                'engine_name': 'google_document_ai',
                'document_id': kwargs.get('document_id', 'unknown'),
                'extracted_text': '',
                'confidence_score': 0.0,
                'pages_count': 0,
                'word_count': 0,
                'processing_time_ms': 0,
                'tables': [],
                'key_value_pairs': [],
                'raw_response_path': None,
                'success': False,
                'error_message': str(e)
            }

        except Exception as e:
            return {
                'engine_name': 'google_document_ai',
                'document_id': kwargs.get('document_id', 'unknown'),
                'extracted_text': '',
                'confidence_score': 0.0,
                'pages_count': 0,
                'word_count': 0,
                'processing_time_ms': 0,
                'tables': [],
                'key_value_pairs': [],
                'raw_response_path': None,
                'success': False,
                'error_message': f"Unexpected error: {str(e)}"
            }

    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about this OCR engine.

        Returns:
            Dictionary with engine information
        """
        return {
            'name': 'google_document_ai',
            'display_name': 'Google Document AI',
            'description': 'Google Cloud Document AI for advanced document processing',
            'supported_formats': ['application/pdf', 'image/jpeg', 'image/png', 'image/tiff'],
            'features': ['text_extraction', 'table_extraction', 'form_parsing', 'entity_extraction'],
            'requires_credentials': True,
            'setup_instructions': (
                '1. Create a Google Cloud Project\n'
                '2. Enable Document AI API\n'
                '3. Create a Document AI processor\n'
                '4. Set GOOGLE_CREDENTIALS_PATH and GOOGLE_DOCUMENT_AI_ENDPOINT environment variables'
            )
        }

    def health_check(self) -> Dict[str, Any]:
        """Check if the Google Document AI engine is healthy.

        Returns:
            Dictionary with health check results
        """
        return self.service.health_check()

"""Factory for creating OCR engine instances."""

from typing import Dict, Any, Optional, Type
from enum import Enum

from services.blob_storage.interface import BlobStorageInterface
from services.ocr_engines.google_document_ai_adapter import GoogleDocumentAIOCREngine


class OCREngineType(Enum):
    """Supported OCR engine types."""
    GOOGLE_DOCUMENT_AI = "google_document_ai"
    TESSERACT = "tesseract"
    AZURE = "azure"
    MISTRAL = "mistral"


class OCREngineFactory:
    """Factory for creating OCR engine instances."""

    # Registry of engine classes
    _engine_registry = {
        OCREngineType.GOOGLE_DOCUMENT_AI: GoogleDocumentAIOCREngine,
        # Add other engines here as they are implemented
        # OCREngineType.TESSERACT: TesseractOCREngine,
        # OCREngineType.AZURE: AzureOCREngine,
        # OCREngineType.MISTRAL: MistralOCREngine,
    }

    @classmethod
    def create_engine(
        cls,
        engine_type: OCREngineType,
        storage_service: Optional[BlobStorageInterface] = None,
        **kwargs
    ) -> Any:
        """Create an OCR engine instance.

        Args:
            engine_type: Type of OCR engine to create
            storage_service: Optional blob storage service
            **kwargs: Additional parameters for engine initialization

        Returns:
            OCR engine instance

        Raises:
            ValueError: If engine type is not supported
        """
        if engine_type not in cls._engine_registry:
            raise ValueError(f"Unsupported OCR engine type: {engine_type}")

        engine_class = cls._engine_registry[engine_type]
        return engine_class(storage_service=storage_service, **kwargs)

    @classmethod
    def get_available_engines(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all available OCR engines.

        Returns:
            Dictionary mapping engine names to their info
        """
        engines = {}
        for engine_type in self._engine_registry.keys():
            try:
                # Create a temporary instance to get info
                engine = self.create_engine(engine_type)
                engines[engine_type.value] = engine.get_engine_info()
            except Exception as e:
                # If engine can't be created, provide basic info
                engines[engine_type.value] = {
                    'name': engine_type.value,
                    'display_name': engine_type.value.replace('_', ' ').title(),
                    'status': 'unavailable',
                    'error': str(e)
                }

        return engines

    @classmethod
    def register_engine(cls, engine_type: OCREngineType, engine_class: Type):
        """Register a new OCR engine type.

        Args:
            engine_type: Engine type enum value
            engine_class: OCR engine class
        """
        cls._engine_registry[engine_type] = engine_class

    @classmethod
    def is_engine_available(cls, engine_type: OCREngineType) -> bool:
        """Check if an OCR engine is available and properly configured.

        Args:
            engine_type: Engine type to check

        Returns:
            True if engine is available, False otherwise
        """
        try:
            engine = cls.create_engine(engine_type)
            health = engine.health_check()
            return health.get('status') == 'healthy'
        except Exception:
            return False

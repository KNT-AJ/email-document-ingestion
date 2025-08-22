"""Factory for open-source OCR services."""

from enum import Enum
from typing import Dict, Any, Optional, Type
from pathlib import Path

from .interface import OCRServiceInterface, OCRConfigurationError
from .pytesseract_service import PytesseractOCRService
from .paddleocr_service import PaddleOCRService
from services.blob_storage.interface import BlobStorageInterface
from utils.logging import get_logger

logger = get_logger(__name__)


class OpenSourceOCREngine(Enum):
    """Enumeration of available open-source OCR engines."""
    PYTESSERACT = "pytesseract"
    PADDLEOCR = "paddleocr"


class OpenSourceOCRFactory:
    """Factory class for creating open-source OCR service instances."""
    
    _service_classes: Dict[OpenSourceOCREngine, Type[OCRServiceInterface]] = {
        OpenSourceOCREngine.PYTESSERACT: PytesseractOCRService,
        OpenSourceOCREngine.PADDLEOCR: PaddleOCRService
    }
    
    @classmethod
    def create_service(
        self,
        engine: OpenSourceOCREngine,
        storage_service: Optional[BlobStorageInterface] = None,
        **kwargs
    ) -> OCRServiceInterface:
        """
        Create an OCR service instance.
        
        Args:
            engine: The OCR engine to use
            storage_service: Optional blob storage service
            **kwargs: Engine-specific configuration options
            
        Returns:
            OCR service instance
            
        Raises:
            OCRConfigurationError: If engine is not supported or configuration is invalid
        """
        if engine not in self._service_classes:
            available_engines = list(self._service_classes.keys())
            raise OCRConfigurationError(
                f"Unsupported OCR engine: {engine}. Available engines: {available_engines}",
                service_name=str(engine)
            )
        
        service_class = self._service_classes[engine]
        
        try:
            logger.info(f"Creating {engine.value} OCR service", engine=engine.value, kwargs=kwargs)
            
            # Create service instance with storage service and additional config
            service = service_class(storage_service=storage_service, **kwargs)
            
            # Perform health check
            health = service.health_check()
            if health.get('status') != 'healthy':
                raise OCRConfigurationError(
                    f"OCR service health check failed: {health.get('error', 'Unknown error')}",
                    service_name=engine.value
                )
            
            logger.info(f"{engine.value} OCR service created successfully")
            return service
            
        except Exception as e:
            logger.error(f"Failed to create {engine.value} OCR service", error=str(e))
            raise OCRConfigurationError(
                f"Failed to create {engine.value} OCR service: {str(e)}",
                service_name=engine.value,
                original_error=e
            )
    
    @classmethod
    def create_pytesseract_service(
        cls,
        storage_service: Optional[BlobStorageInterface] = None,
        tesseract_cmd: Optional[str] = None,
        language: str = "eng",
        config: Optional[str] = None
    ) -> PytesseractOCRService:
        """
        Create a Pytesseract OCR service with specific configuration.
        
        Args:
            storage_service: Optional blob storage service
            tesseract_cmd: Path to tesseract executable
            language: Language for OCR
            config: Additional tesseract configuration options
            
        Returns:
            Pytesseract OCR service instance
        """
        return cls.create_service(
            OpenSourceOCREngine.PYTESSERACT,
            storage_service=storage_service,
            tesseract_cmd=tesseract_cmd,
            language=language,
            config=config
        )
    
    @classmethod
    def create_paddleocr_service(
        cls,
        storage_service: Optional[BlobStorageInterface] = None,
        lang: str = 'en',
        use_angle_cls: bool = True,
        use_gpu: bool = False,
        show_log: bool = False
    ) -> PaddleOCRService:
        """
        Create a PaddleOCR service with specific configuration.
        
        Args:
            storage_service: Optional blob storage service
            lang: Language for OCR
            use_angle_cls: Whether to use angle classification
            use_gpu: Whether to use GPU acceleration
            show_log: Whether to show PaddleOCR logs
            
        Returns:
            PaddleOCR service instance
        """
        return cls.create_service(
            OpenSourceOCREngine.PADDLEOCR,
            storage_service=storage_service,
            lang=lang,
            use_angle_cls=use_angle_cls,
            use_gpu=use_gpu,
            show_log=show_log
        )
    
    @classmethod
    def get_available_engines(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get information about available OCR engines.
        
        Returns:
            Dictionary with engine information
        """
        engines_info = {}
        
        for engine in OpenSourceOCREngine:
            try:
                # Try to create a temporary service to get capabilities
                temp_service = cls.create_service(engine)
                health = temp_service.health_check()
                features = temp_service.get_supported_features()
                
                engines_info[engine.value] = {
                    'name': engine.value,
                    'status': health.get('status', 'unknown'),
                    'features': features,
                    'health_info': health
                }
                
            except Exception as e:
                engines_info[engine.value] = {
                    'name': engine.value,
                    'status': 'unavailable',
                    'error': str(e),
                    'features': []
                }
        
        return engines_info
    
    @classmethod
    def get_best_engine_for_language(cls, language: str) -> OpenSourceOCREngine:
        """
        Get the best OCR engine for a specific language.
        
        Args:
            language: Language code (e.g., 'en', 'ch', 'fr')
            
        Returns:
            Recommended OCR engine
        """
        # Language preference mapping
        language_preferences = {
            'ch': OpenSourceOCREngine.PADDLEOCR,  # Chinese works better with PaddleOCR
            'chinese': OpenSourceOCREngine.PADDLEOCR,
            'ja': OpenSourceOCREngine.PADDLEOCR,  # Japanese
            'japanese': OpenSourceOCREngine.PADDLEOCR,
            'ko': OpenSourceOCREngine.PADDLEOCR,  # Korean
            'korean': OpenSourceOCREngine.PADDLEOCR,
            'ar': OpenSourceOCREngine.PADDLEOCR,  # Arabic
            'arabic': OpenSourceOCREngine.PADDLEOCR,
        }
        
        # Default to PYTESSERACT for most European languages and English
        return language_preferences.get(language.lower(), OpenSourceOCREngine.PYTESSERACT)
    
    @classmethod
    def auto_select_engine(
        cls,
        document_path: Optional[Path] = None,
        language: Optional[str] = None,
        prefer_gpu: bool = False
    ) -> OpenSourceOCREngine:
        """
        Automatically select the best OCR engine based on document and preferences.
        
        Args:
            document_path: Path to document (for analysis)
            language: Preferred language
            prefer_gpu: Whether to prefer GPU-accelerated engines
            
        Returns:
            Selected OCR engine
        """
        # If language is specified, use language-based selection
        if language:
            return cls.get_best_engine_for_language(language)
        
        # If GPU is preferred and available, prefer PaddleOCR
        if prefer_gpu:
            try:
                import paddleocr
                return OpenSourceOCREngine.PADDLEOCR
            except ImportError:
                logger.warning("PaddleOCR not available for GPU preference")
        
        # Default fallback to Pytesseract (more widely compatible)
        return OpenSourceOCREngine.PYTESSERACT

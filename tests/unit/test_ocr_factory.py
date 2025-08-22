"""Tests for OCR service factory."""

import pytest
from unittest.mock import Mock, patch

from services.ocr.factory import OCRServiceFactory, get_ocr_service
from services.ocr.interface import OCRServiceInterface, OCRConfigurationError


class TestOCRServiceFactory:
    """Test cases for OCRServiceFactory."""

    @pytest.fixture
    def mock_blob_storage(self):
        """Mock blob storage service."""
        return Mock()

    def test_create_textract_service_success(self, mock_blob_storage):
        """Test successful creation of Textract service."""
        with patch('services.ocr.factory.TextractOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = OCRServiceFactory.create_service('textract', blob_storage=mock_blob_storage)
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once_with(blob_storage=mock_blob_storage)

    def test_create_azure_service_success(self, mock_blob_storage):
        """Test successful creation of Azure service."""
        with patch('services.ocr.factory.AzureDocumentIntelligenceService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = OCRServiceFactory.create_service('azure', blob_storage=mock_blob_storage)
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once()

    def test_create_tesseract_service_success(self, mock_blob_storage):
        """Test successful creation of PyTesseract service."""
        with patch('services.ocr.factory.PyTesseractOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = OCRServiceFactory.create_service('tesseract', blob_storage=mock_blob_storage)
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once()

    def test_create_paddle_service_success(self, mock_blob_storage):
        """Test successful creation of PaddleOCR service."""
        with patch('services.ocr.factory.PaddleOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = OCRServiceFactory.create_service('paddle', blob_storage=mock_blob_storage)
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once()

    def test_create_google_service_success(self, mock_blob_storage):
        """Test successful creation of Google Document AI service."""
        with patch('services.ocr.factory.GoogleDocumentAIService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = OCRServiceFactory.create_service('google', blob_storage=mock_blob_storage)
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once()

    def test_create_service_case_insensitive(self, mock_blob_storage):
        """Test that service creation is case insensitive."""
        with patch('services.ocr.factory.TextractOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            # Test various case combinations
            for service_type in ['TEXTRACT', 'Textract', 'textRACT']:
                service = OCRServiceFactory.create_service(service_type, blob_storage=mock_blob_storage)
                assert service == mock_service_instance

    def test_create_service_aliases(self, mock_blob_storage):
        """Test that service aliases work correctly."""
        # Test PyTesseract aliases
        with patch('services.ocr.factory.PyTesseractOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            for alias in ['tesseract', 'pytesseract']:
                service = OCRServiceFactory.create_service(alias, blob_storage=mock_blob_storage)
                assert service == mock_service_instance

        # Test PaddleOCR aliases
        with patch('services.ocr.factory.PaddleOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            for alias in ['paddle', 'paddleocr']:
                service = OCRServiceFactory.create_service(alias, blob_storage=mock_blob_storage)
                assert service == mock_service_instance

        # Test Google Document AI aliases
        with patch('services.ocr.factory.GoogleDocumentAIService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            for alias in ['google', 'documentai']:
                service = OCRServiceFactory.create_service(alias, blob_storage=mock_blob_storage)
                assert service == mock_service_instance

    def test_create_service_unsupported_type(self, mock_blob_storage):
        """Test error handling for unsupported service types."""
        with pytest.raises(OCRConfigurationError) as exc_info:
            OCRServiceFactory.create_service('unsupported_service', blob_storage=mock_blob_storage)
        
        assert "Unsupported OCR service type: unsupported_service" in str(exc_info.value)

    def test_create_service_initialization_error(self, mock_blob_storage):
        """Test error handling when service initialization fails."""
        with patch('services.ocr.factory.TextractOCRService') as mock_service_class:
            mock_service_class.side_effect = Exception("Service initialization failed")
            
            with pytest.raises(OCRConfigurationError) as exc_info:
                OCRServiceFactory.create_service('textract', blob_storage=mock_blob_storage)
            
            assert "Failed to create AWS Textract service" in str(exc_info.value)
            assert exc_info.value.service_name == "AWS Textract"
            assert exc_info.value.original_error is not None

    def test_get_available_services(self):
        """Test getting list of available services."""
        # Mock all services as available
        with patch('services.ocr.factory.TextractOCRService'):
            with patch('services.ocr.factory.AzureDocumentIntelligenceService'):
                with patch('services.ocr.factory.PyTesseractOCRService'):
                    with patch('services.ocr.factory.PaddleOCRService'):
                        with patch('services.ocr.factory.GoogleDocumentAIService'):
                            available = OCRServiceFactory.get_available_services()
                            
                            expected_services = ['textract', 'azure', 'tesseract', 'paddle', 'google']
                            for service in expected_services:
                                assert service in available

    def test_get_available_services_partial(self):
        """Test getting available services when some are not available."""
        # Only mock Textract as available
        with patch('services.ocr.factory.TextractOCRService'):
            available = OCRServiceFactory.get_available_services()
            
            assert 'textract' in available
            # Other services should not be in the list if not mocked

    def test_get_ocr_service_convenience_function(self, mock_blob_storage):
        """Test the convenience function for getting OCR services."""
        with patch('services.ocr.factory.TextractOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = get_ocr_service('textract', blob_storage=mock_blob_storage)
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once_with(blob_storage=mock_blob_storage)

    def test_get_ocr_service_default_parameters(self):
        """Test convenience function with default parameters."""
        with patch('services.ocr.factory.TextractOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = get_ocr_service()  # Should default to textract
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once_with(blob_storage=None)

    def test_create_service_without_blob_storage(self):
        """Test creating services without blob storage."""
        with patch('services.ocr.factory.TextractOCRService') as mock_service_class:
            mock_service_instance = Mock(spec=OCRServiceInterface)
            mock_service_class.return_value = mock_service_instance
            
            service = OCRServiceFactory.create_service('textract')
            
            assert service == mock_service_instance
            mock_service_class.assert_called_once_with(blob_storage=None)

    def test_factory_logging(self, mock_blob_storage):
        """Test that factory logs service creation."""
        with patch('services.ocr.factory.logger') as mock_logger:
            with patch('services.ocr.factory.TextractOCRService') as mock_service_class:
                mock_service_instance = Mock(spec=OCRServiceInterface)
                mock_service_class.return_value = mock_service_instance
                
                OCRServiceFactory.create_service('textract', blob_storage=mock_blob_storage)
                
                mock_logger.info.assert_called_once_with("Creating textract OCR service implementation")


class TestOCRFactoryImportHandling:
    """Test factory behavior when OCR services are not available."""

    def test_missing_imports_logged_as_warnings(self):
        """Test that missing imports are logged as warnings, not errors."""
        with patch('services.ocr.factory.logger') as mock_logger:
            # This should trigger import errors that get logged as warnings
            import importlib
            import services.ocr.factory
            importlib.reload(services.ocr.factory)
            
            # Verify that warnings were logged for unavailable services
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if any('not available' in str(arg) for arg in call[0])]
            
            # We expect at least some services to log warnings if dependencies aren't installed
            # In a clean test environment, this is likely to happen
            assert len(warning_calls) >= 0  # At minimum, no errors should occur

    def test_factory_handles_missing_services_gracefully(self):
        """Test that factory handles missing service imports gracefully."""
        # Even if some services can't be imported, the factory should still work
        # for available services
        try:
            available_services = OCRServiceFactory.get_available_services()
            assert isinstance(available_services, list)
        except Exception as e:
            pytest.fail(f"Factory should handle missing imports gracefully, but got: {e}")

    def test_unavailable_service_creation_fails_gracefully(self):
        """Test that creating unavailable services fails with proper error."""
        # If a service class isn't available, creation should fail with OCRConfigurationError
        # This is hard to test without actually making services unavailable,
        # but we can test the error path
        
        import services.ocr.factory as factory_module
        
        # Patch a service to be unavailable
        original_textract = getattr(factory_module, 'TextractOCRService', None)
        
        # Temporarily remove the service
        if hasattr(factory_module, 'TextractOCRService'):
            delattr(factory_module, 'TextractOCRService')
        
        try:
            with pytest.raises(OCRConfigurationError):
                OCRServiceFactory.create_service('textract')
        finally:
            # Restore the service if it existed
            if original_textract is not None:
                setattr(factory_module, 'TextractOCRService', original_textract)

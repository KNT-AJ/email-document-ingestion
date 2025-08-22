"""Tests for Google Document AI service."""

import pytest
import tempfile
import json
import os
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from services.google_document_ai_service import (
    GoogleDocumentAIService,
    GoogleDocumentAIError,
    retry_on_google_api_error
)
from services.blob_storage.interface import BlobStorageInterface


class TestGoogleDocumentAIService:
    """Test cases for GoogleDocumentAIService."""

    @pytest.fixture
    def mock_storage_service(self):
        """Mock blob storage service."""
        return Mock(spec=BlobStorageInterface)

    @pytest.fixture
    def sample_document_response(self):
        """Sample Document AI response."""
        return {
            'text': 'Sample extracted text from document',
            'pages': [
                {
                    'page_number': 1,
                    'width': 612.0,
                    'height': 792.0,
                    'confidence': 0.95,
                    'blocks_count': 5,
                    'tables_count': 1,
                    'paragraphs_count': 3
                }
            ],
            'entities': [
                {
                    'type': 'invoice_number',
                    'mention_text': 'INV-001',
                    'confidence': 0.98
                }
            ]
        }

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_service_initialization_success(self, mock_storage_service):
        """Test successful service initialization."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file') as mock_client:
            mock_client_instance = Mock()
            mock_client.return_value = mock_client_instance

            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            assert service.storage_service == mock_storage_service
            assert service._client == mock_client_instance
            mock_client.assert_called_once_with('/path/to/credentials.json')

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': ''
    })
    def test_service_initialization_missing_config(self, mock_storage_service):
        """Test service initialization with missing configuration."""
        with pytest.raises(GoogleDocumentAIError, match="GOOGLE_CREDENTIALS_PATH not configured"):
            GoogleDocumentAIService(storage_service=mock_storage_service)

    def test_retry_decorator_success(self):
        """Test retry decorator with successful function call."""
        call_count = 0

        @retry_on_google_api_error(max_retries=2, initial_delay=0.1)
        def successful_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return "success"

        result = successful_function()
        assert result == "success"
        assert call_count == 2

    def test_retry_decorator_exceeds_max_retries(self):
        """Test retry decorator when max retries are exceeded."""
        call_count = 0

        @retry_on_google_api_error(max_retries=2, initial_delay=0.1)
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(GoogleDocumentAIError, match="Google API call failed after 3 attempts"):
            failing_function()

        assert call_count == 3

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_process_document_success(self, mock_storage_service, sample_document_response):
        """Test successful document processing."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file') as mock_client:
            # Mock client and response
            mock_client_instance = Mock()
            mock_client.return_value = mock_client_instance

            # Create mock document response
            mock_document = Mock()
            mock_document.text = 'Sample extracted text'
            mock_document.pages = [Mock()]
            mock_document.pages[0].blocks = [Mock()]
            mock_document.pages[0].blocks[0].text_anchor = Mock()
            mock_document.pages[0].blocks[0].text_anchor.text_segments = [Mock()]
            mock_document.pages[0].blocks[0].text_anchor.text_segments[0].text = 'Sample text'
            mock_document.pages[0].blocks[0].layout = Mock()
            mock_document.pages[0].blocks[0].layout.bounding_poly = Mock()
            mock_document.pages[0].blocks[0].layout.bounding_poly.vertices = [
                Mock(x=0, y=0), Mock(x=100, y=0), Mock(x=100, y=100), Mock(x=0, y=100)
            ]
            mock_document.pages[0].tables = []
            mock_document.pages[0].paragraphs = []
            mock_document.entities = []
            mock_document.pages[0].confidence = 0.95

            mock_response = Mock()
            mock_response.document = mock_document
            mock_client_instance.process_document.return_value = mock_response

            # Mock storage service
            mock_storage_service.upload_string.return_value = None

            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            # Create temporary test file
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.pdf') as f:
                f.write(b'test document content')
                temp_path = f.name

            try:
                result = service.process_document(
                    document_path=temp_path,
                    mime_type='application/pdf',
                    document_id='test_doc_123'
                )

                # Verify result structure
                assert 'extracted_text' in result
                assert 'tables' in result
                assert 'key_value_pairs' in result
                assert 'confidence_score' in result
                assert 'pages_count' in result
                assert 'word_count' in result
                assert 'latency_ms' in result
                assert 'engine' in result
                assert 'raw_response' in result
                assert 'raw_response_path' in result

                assert result['engine'] == 'google_document_ai'
                assert isinstance(result['confidence_score'], float)
                assert isinstance(result['pages_count'], int)
                assert isinstance(result['word_count'], int)
                assert isinstance(result['latency_ms'], int)

            finally:
                os.unlink(temp_path)

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_process_document_file_not_found(self, mock_storage_service):
        """Test document processing with non-existent file."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file'):
            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            with pytest.raises(GoogleDocumentAIError, match="Processing failed"):
                service.process_document(
                    document_path='/non/existent/file.pdf',
                    document_id='test_doc_123'
                )

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_store_raw_response(self, mock_storage_service):
        """Test storing raw response in blob storage."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file'):
            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            test_data = {'test': 'data'}
            document_id = 'test_doc_123'

            with patch('time.time', return_value=1234567890):
                blob_path = service._store_raw_response(document_id, test_data)

                expected_path = f"ocr-runs/google-document-ai/{document_id}/raw_response.json"
                assert blob_path == expected_path

                # Verify storage service was called correctly
                mock_storage_service.upload_string.assert_called_once()
                call_args = mock_storage_service.upload_string.call_args
                assert call_args[0][1] == expected_path  # blob_path
                assert call_args[0][2] == "application/json"  # content_type

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_store_raw_response_no_storage(self):
        """Test storing raw response without storage service."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file'):
            service = GoogleDocumentAIService(storage_service=None)

            with pytest.raises(GoogleDocumentAIError, match="Storage service not available"):
                service._store_raw_response('test_doc', {'test': 'data'})

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_calculate_confidence_score(self, mock_storage_service):
        """Test confidence score calculation."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file'):
            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            # Create mock document with pages
            mock_document = Mock()
            mock_document.pages = [
                Mock(confidence=0.9),
                Mock(confidence=0.8),
                Mock(confidence=0.95)
            ]

            confidence = service._calculate_confidence_score(mock_document)
            expected_average = (0.9 + 0.8 + 0.95) / 3
            assert abs(confidence - expected_average) < 0.001

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_calculate_confidence_score_no_pages(self, mock_storage_service):
        """Test confidence score calculation with no pages."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file'):
            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            mock_document = Mock()
            mock_document.pages = []

            confidence = service._calculate_confidence_score(mock_document)
            assert confidence == 0.0

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_extract_text_no_text(self, mock_storage_service):
        """Test text extraction when document has no text."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file'):
            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            mock_document = Mock()
            mock_document.text = ""

            extracted_text = service._extract_text(mock_document)
            assert extracted_text == ""

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_extract_key_value_pairs(self, mock_storage_service):
        """Test key-value pairs extraction."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file'):
            service = GoogleDocumentAIService(storage_service=mock_storage_service)

            # Create mock entities
            mock_entity1 = Mock()
            mock_entity1.type_ = 'invoice_number'
            mock_entity1.mention_text = 'INV-001'
            mock_entity1.confidence = 0.98

            mock_entity2 = Mock()
            mock_entity2.type_ = 'total_amount'
            mock_entity2.mention_text = '$100.00'
            mock_entity2.confidence = 0.95

            mock_document = Mock()
            mock_document.entities = [mock_entity1, mock_entity2]

            kv_pairs = service._extract_key_value_pairs(mock_document)

            assert len(kv_pairs) == 2
            assert kv_pairs[0]['key'] == 'invoice_number'
            assert kv_pairs[0]['value'] == 'INV-001'
            assert kv_pairs[0]['confidence'] == 0.98

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_health_check_success(self, mock_storage_service):
        """Test successful health check."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file') as mock_client:
            mock_client_instance = Mock()
            mock_client.return_value = mock_client_instance

            # Mock processor response
            mock_processor = Mock()
            mock_processor.name = 'test-processor'
            mock_processor.state = Mock()
            mock_processor.state.name = 'ENABLED'
            mock_client_instance.get_processor.return_value = mock_processor

            service = GoogleDocumentAIService(storage_service=mock_storage_service)
            health = service.health_check()

            assert health['status'] == 'healthy'
            assert health['processor_name'] == 'test-processor'
            assert health['processor_state'] == 'ENABLED'

    @patch.dict(os.environ, {
        'GOOGLE_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GOOGLE_DOCUMENT_AI_ENDPOINT': 'projects/test-project/locations/us/processors/test-processor'
    })
    def test_health_check_client_not_initialized(self, mock_storage_service):
        """Test health check when client is not initialized."""
        with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.from_service_account_file') as mock_client:
            mock_client.side_effect = Exception("Initialization failed")

            service = GoogleDocumentAIService(storage_service=mock_storage_service)
            service._client = None  # Force client to be None

            health = service.health_check()

            assert health['status'] == 'unhealthy'
            assert 'Client not initialized' in health['error']


class TestGoogleDocumentAIError:
    """Test cases for GoogleDocumentAIError exception."""

    def test_exception_creation(self):
        """Test exception creation and message handling."""
        error = GoogleDocumentAIError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_exception_inheritance(self):
        """Test that GoogleDocumentAIError inherits from Exception."""
        error = GoogleDocumentAIError("Test")
        assert isinstance(error, Exception)

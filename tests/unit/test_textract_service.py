"""Tests for AWS Textract OCR service."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError, NoCredentialsError

from services.ocr.textract_service import TextractOCRService, create_textract_service
from services.ocr.interface import OCRError, OCRConfigurationError, OCRProcessingError


class TestTextractOCRService:
    """Test cases for TextractOCRService."""

    @pytest.fixture
    def mock_blob_storage(self):
        """Mock blob storage service."""
        mock = Mock()
        mock.store.return_value = "stored_key_12345"
        return mock

    @pytest.fixture
    def mock_document_path(self, tmp_path):
        """Create a mock document file."""
        document = tmp_path / "test_document.pdf"
        document.write_bytes(b"Mock PDF content")
        return document

    @pytest.fixture
    def mock_textract_document(self):
        """Mock Textract document response."""
        mock_doc = Mock()
        mock_doc.text = "Sample extracted text"
        mock_doc.response = {"DocumentMetadata": {"Pages": 1}}
        
        # Mock tables
        mock_table = Mock()
        mock_table.rows = [Mock(), Mock()]
        mock_table.rows[0].cells = [Mock(), Mock()]
        mock_table.rows[0].cells[0].text = "Cell 1,1"
        mock_table.rows[0].cells[0].confidence = 0.95
        mock_table.rows[0].cells[1].text = "Cell 1,2"
        mock_table.rows[0].cells[1].confidence = 0.93
        mock_table.rows[1].cells = [Mock(), Mock()]
        mock_table.rows[1].cells[0].text = "Cell 2,1"
        mock_table.rows[1].cells[0].confidence = 0.89
        mock_table.rows[1].cells[1].text = "Cell 2,2"
        mock_table.rows[1].cells[1].confidence = 0.91
        mock_table.get_text.return_value = "| Cell 1,1 | Cell 1,2 |\n| Cell 2,1 | Cell 2,2 |"
        mock_doc.tables = [mock_table]
        
        # Mock key-value pairs
        mock_kv = Mock()
        mock_kv.key.text = "Name"
        mock_kv.value.text = "John Doe"
        mock_kv.key.confidence = 0.98
        mock_kv.value.confidence = 0.96
        mock_doc.key_values = [mock_kv]
        
        # Mock pages
        mock_page = Mock()
        mock_page.width = 612
        mock_page.height = 792
        mock_page.words = ["word1", "word2", "word3"]
        mock_page.lines = ["line1", "line2"]
        mock_doc.pages = [mock_page]
        
        return mock_doc

    def test_initialization_success(self, mock_blob_storage):
        """Test successful service initialization."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            assert service.blob_storage == mock_blob_storage
            assert service.SUPPORTED_FORMATS == {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}

    def test_initialization_no_credentials(self, mock_blob_storage):
        """Test initialization failure with no AWS credentials."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.side_effect = NoCredentialsError()
            
            with pytest.raises(OCRConfigurationError) as exc_info:
                TextractOCRService(blob_storage=mock_blob_storage)
            
            assert "AWS credentials not found" in str(exc_info.value)
            assert exc_info.value.service_name == "textract"

    def test_textractor_property(self, mock_blob_storage):
        """Test textractor property lazy initialization."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            with patch('services.ocr.textract_service.Textractor') as mock_textractor_class:
                mock_textractor_instance = Mock()
                mock_textractor_class.return_value = mock_textractor_instance
                
                service = TextractOCRService(blob_storage=mock_blob_storage)
                
                # First access should create the instance
                textractor = service.textractor
                assert textractor == mock_textractor_instance
                mock_textractor_class.assert_called_once()
                
                # Second access should return same instance
                textractor2 = service.textractor
                assert textractor2 == mock_textractor_instance
                # Should not call constructor again
                assert mock_textractor_class.call_count == 1

    def test_convert_features(self, mock_blob_storage):
        """Test feature string to enum conversion."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            # Test with known features
            features = service._convert_features(['tables', 'forms', 'layout'])
            from textractor.data.constants import TextractFeatures
            assert TextractFeatures.TABLES in features
            assert TextractFeatures.FORMS in features
            assert TextractFeatures.LAYOUT in features
            
            # Test with unknown feature (should log warning)
            features = service._convert_features(['unknown_feature'])
            # Should fall back to default
            assert TextractFeatures.TABLES in features
            assert TextractFeatures.FORMS in features
            
            # Test with empty list (should use defaults)
            features = service._convert_features([])
            assert TextractFeatures.TABLES in features
            assert TextractFeatures.FORMS in features

    def test_analyze_document_sync_success(self, mock_blob_storage, mock_document_path, mock_textract_document):
        """Test successful synchronous document analysis."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            with patch.object(service, '_textractor') as mock_textractor:
                mock_textractor.analyze_document.return_value = mock_textract_document
                
                result = service.analyze_document(mock_document_path, ['tables', 'forms'])
                
                # Verify textract was called correctly
                mock_textractor.analyze_document.assert_called_once()
                call_args = mock_textractor.analyze_document.call_args
                assert str(mock_document_path) in call_args[1]['file_source']
                
                # Verify result structure
                assert result['text'] == "Sample extracted text"
                assert len(result['tables']) == 1
                assert result['tables'][0]['row_count'] == 2
                assert result['tables'][0]['column_count'] == 2
                assert len(result['key_value_pairs']) == 1
                assert result['key_value_pairs'][0]['key'] == "Name"
                assert result['key_value_pairs'][0]['value'] == "John Doe"
                assert len(result['pages']) == 1
                assert result['pages'][0]['page_number'] == 1
                assert 'raw_response_key' in result

    def test_analyze_document_async_success(self, mock_blob_storage, mock_document_path, mock_textract_document):
        """Test successful asynchronous document analysis."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            # Create a large file to trigger async processing
            large_content = b"x" * (6 * 1024 * 1024)  # 6MB
            mock_document_path.write_bytes(large_content)
            
            with patch('services.ocr.textract_service.settings') as mock_settings:
                mock_settings.TEXTRACT_S3_BUCKET = "test-bucket"
                mock_settings.TEXTRACT_S3_PREFIX = "textract/"
                
                service = TextractOCRService(blob_storage=mock_blob_storage)
                
                with patch.object(service, '_textractor') as mock_textractor:
                    mock_textractor.start_document_analysis.return_value = mock_textract_document
                    
                    result = service.analyze_document(mock_document_path, ['tables'])
                    
                    # Verify async method was called
                    mock_textractor.start_document_analysis.assert_called_once()
                    call_args = mock_textractor.start_document_analysis.call_args
                    assert call_args[1]['s3_upload_path'] == "s3://test-bucket/textract/"

    def test_analyze_document_unsupported_format(self, mock_blob_storage, tmp_path):
        """Test analysis with unsupported file format."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            unsupported_file = tmp_path / "test.txt"
            unsupported_file.write_text("Some text")
            
            with pytest.raises(OCRProcessingError) as exc_info:
                service.analyze_document(unsupported_file)
            
            assert "Unsupported file format" in str(exc_info.value)
            assert exc_info.value.service_name == "textract"

    def test_analyze_document_async_no_bucket(self, mock_blob_storage, mock_document_path):
        """Test async processing failure when no S3 bucket configured."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            # Create a large file to trigger async processing
            large_content = b"x" * (6 * 1024 * 1024)  # 6MB
            mock_document_path.write_bytes(large_content)
            
            with patch('services.ocr.textract_service.settings') as mock_settings:
                mock_settings.TEXTRACT_S3_BUCKET = None
                
                service = TextractOCRService(blob_storage=mock_blob_storage)
                
                with pytest.raises(OCRConfigurationError) as exc_info:
                    service.analyze_document(mock_document_path)
                
                assert "TEXTRACT_S3_BUCKET must be configured" in str(exc_info.value)

    def test_analyze_document_client_error(self, mock_blob_storage, mock_document_path):
        """Test handling of AWS client errors."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            with patch.object(service, '_textractor') as mock_textractor:
                mock_textractor.analyze_document.side_effect = ClientError(
                    error_response={'Error': {'Code': 'InvalidParameterException', 'Message': 'Invalid input'}},
                    operation_name='AnalyzeDocument'
                )
                
                with pytest.raises(OCRProcessingError) as exc_info:
                    service.analyze_document(mock_document_path)
                
                assert "Textract processing failed" in str(exc_info.value)

    def test_extract_text(self, mock_blob_storage):
        """Test text extraction from analysis result."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            analysis_result = {'text': 'Extracted text content'}
            text = service.extract_text(analysis_result)
            assert text == 'Extracted text content'

    def test_extract_tables(self, mock_blob_storage):
        """Test table extraction from analysis result."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            analysis_result = {
                'tables': [
                    {'table_id': 0, 'row_count': 2, 'column_count': 3, 'cells': []}
                ]
            }
            tables = service.extract_tables(analysis_result)
            assert len(tables) == 1
            assert tables[0]['table_id'] == 0

    def test_extract_key_value_pairs(self, mock_blob_storage):
        """Test key-value pair extraction from analysis result."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            analysis_result = {
                'key_value_pairs': [
                    {'key': 'Name', 'value': 'John Doe', 'key_confidence': 0.98, 'value_confidence': 0.96}
                ]
            }
            kvs = service.extract_key_value_pairs(analysis_result)
            assert len(kvs) == 1
            assert kvs[0]['key'] == 'Name'
            assert kvs[0]['value'] == 'John Doe'

    def test_calculate_metrics(self, mock_blob_storage):
        """Test metrics calculation from analysis result."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            analysis_result = {
                'pages': [
                    {'page_number': 1, 'word_count': 150, 'line_count': 20},
                    {'page_number': 2, 'word_count': 200, 'line_count': 25}
                ],
                'tables': [{'table_id': 0}, {'table_id': 1}],
                'key_value_pairs': [
                    {'key': 'Name', 'value': 'John', 'key_confidence': 0.95, 'value_confidence': 0.90},
                    {'key': 'Age', 'value': '30', 'key_confidence': 0.98, 'value_confidence': 0.92}
                ]
            }
            
            metrics = service.calculate_metrics(analysis_result)
            
            assert metrics['page_count'] == 2
            assert metrics['word_count'] == 350
            assert metrics['line_count'] == 45
            assert metrics['table_count'] == 2
            assert metrics['key_value_pair_count'] == 2
            assert metrics['average_confidence'] == pytest.approx(0.9375, rel=1e-3)

    def test_get_supported_features(self, mock_blob_storage):
        """Test getting supported features."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=mock_blob_storage)
            
            features = service.get_supported_features()
            expected_features = ['tables', 'forms', 'layout', 'queries', 'signatures']
            assert all(feature in features for feature in expected_features)

    def test_store_raw_response_no_blob_storage(self, mock_document_path, mock_textract_document):
        """Test document analysis without blob storage."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = TextractOCRService(blob_storage=None)
            
            with patch.object(service, '_textractor') as mock_textractor:
                mock_textractor.analyze_document.return_value = mock_textract_document
                
                result = service.analyze_document(mock_document_path, ['tables'])
                
                # Should not have raw_response_key when no blob storage
                assert 'raw_response_key' not in result

    def test_create_textract_service_function(self, mock_blob_storage):
        """Test factory function."""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = Mock()
            
            service = create_textract_service(blob_storage=mock_blob_storage)
            assert isinstance(service, TextractOCRService)
            assert service.blob_storage == mock_blob_storage


class TestTextractServiceIntegration:
    """Integration tests that require AWS credentials."""

    @pytest.mark.integration
    def test_real_textract_initialization(self):
        """Test initialization with real AWS environment (requires credentials)."""
        try:
            service = TextractOCRService()
            # If we get here, credentials are available
            assert service is not None
            assert isinstance(service.get_supported_features(), list)
        except OCRConfigurationError:
            pytest.skip("AWS credentials not available for integration test")

    @pytest.mark.integration 
    @pytest.mark.slow
    def test_real_document_processing(self, tmp_path):
        """Test processing a real document (requires AWS credentials and may incur costs)."""
        try:
            service = TextractOCRService()
            
            # Create a simple test image
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.new('RGB', (400, 200), color='white')
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "Test Document", fill='black')
            draw.text((10, 50), "Name: John Doe", fill='black')
            draw.text((10, 90), "Date: 2024-01-01", fill='black')
            
            test_image_path = tmp_path / "test_form.png"
            img.save(test_image_path)
            
            result = service.analyze_document(test_image_path, ['forms'])
            
            assert 'text' in result
            assert 'tables' in result
            assert 'key_value_pairs' in result
            assert 'pages' in result
            assert len(result['pages']) >= 1
            
        except OCRConfigurationError:
            pytest.skip("AWS credentials not available for integration test")

#!/usr/bin/env python3
"""
Simple test script for the Document Extraction Service
"""

import base64
import sys
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from services.document_extraction_service import DocumentExtractionService

def test_document_extraction_service():
    """Test the document extraction service with sample data."""

    print("Testing Document Extraction Service...")

    # Create service instance
    service = DocumentExtractionService()

    # Test SHA256 hash computation
    test_data = b"This is test data"
    expected_hash = hashlib.sha256(test_data).hexdigest()
    actual_hash = service._compute_sha256_hash(test_data)

    assert actual_hash == expected_hash, f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
    print("✅ SHA256 hash computation test passed")

    # Test file type detection
    assert service._is_text_file("test.txt", "text/plain") == True
    assert service._is_text_file("test.csv", "text/csv") == True
    assert service._is_text_file("test.jpg", "image/jpeg") == False
    assert service._is_text_file("test.pdf", "application/pdf") == False
    print("✅ File type detection test passed")

    # Test file skipping
    assert service._should_skip_file("test.tmp", "application/octet-stream") == True
    assert service._should_skip_file("test.txt", "text/plain") == False
    assert service._should_skip_file("Thumbs.db", "application/octet-stream") == True
    print("✅ File skipping logic test passed")

    # Test encoding detection
    utf8_text = "Hello, 世界!".encode('utf-8')
    encoding = service._detect_encoding(utf8_text)
    assert encoding == 'utf-8', f"Expected utf-8, got {encoding}"
    print("✅ Encoding detection test passed")

    # Test text extraction
    sample_text = b"This is a test file content."
    extracted = service._extract_text_content("test.txt", sample_text, "text/plain")
    assert extracted == "This is a test file content.", f"Text extraction failed: {extracted}"
    print("✅ Text extraction test passed")

    # Test metadata extraction
    metadata = service._extract_file_metadata("test.txt", sample_text, "text/plain")
    assert metadata['file_type'] == 'text'
    assert metadata['likely_contains_text'] == True
    assert metadata['file_size_bytes'] == len(sample_text)
    print("✅ Metadata extraction test passed")

    print("✅ All Document Extraction Service tests passed!")
    return True

def test_with_mock_storage():
    """Test the service with mocked storage to avoid database/blob storage dependencies."""

    print("\nTesting with mocked storage...")

    # Create service with mocked dependencies
    service = DocumentExtractionService()

    # Mock the database and blob storage
    with patch.object(service, 'db_service') as mock_db, \
         patch.object(service, 'blob_storage') as mock_storage, \
         patch.object(service, '_find_existing_document_by_hash', return_value=None):

        # Mock successful storage upload
        mock_storage.upload_blob.return_value = "documents/aa/bb/test_hash/test.txt"

        # Mock database session
        mock_session = Mock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # Mock document creation
        mock_document = Mock()
        mock_document.id = 1
        mock_document.filename = "test.txt"
        mock_session.add.return_value = None
        mock_session.commit.return_value = None

        with patch.object(service, '_create_document_record', return_value=mock_document) as mock_create:
            # Test attachment processing
            test_email = Mock()
            test_email.id = 1

            attachment_data = {
                'filename': 'test.txt',
                'mimeType': 'text/plain',
                'size': 26,
                'attachmentId': 'attach_1',
                'data': base64.b64encode(b"This is test content").decode('utf-8')
            }

            result = service._process_attachment(test_email, attachment_data)

            # Verify the result
            assert result is not None
            assert mock_storage.upload_blob.called
            assert mock_create.called

            # Check that the right parameters were passed
            call_args = mock_create.call_args[1]
            assert call_args['filename'] == 'test.txt'
            assert call_args['content_type'] == 'text/plain'
            assert call_args['size_bytes'] == 26

            print("✅ Mock storage test passed")

    return True

if __name__ == "__main__":
    try:
        success1 = test_document_extraction_service()
        success2 = test_with_mock_storage()

        if success1 and success2:
            print("\n🎉 All tests passed! Task 10 implementation is working correctly.")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed.")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

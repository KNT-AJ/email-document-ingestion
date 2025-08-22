"""Tests for Email Persistence Service."""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from services.email_persistence_service import EmailPersistenceService, get_email_persistence_service
from models.email import Email


class TestEmailPersistenceService(unittest.TestCase):
    """Test cases for EmailPersistenceService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = EmailPersistenceService()
        
        # Mock database service and session
        self.mock_db_service = Mock()
        self.mock_session = Mock()
        self.mock_db_service.get_session.return_value.__enter__.return_value = self.mock_session
        self.mock_db_service.get_session.return_value.__exit__.return_value = None
        self.service.db_service = self.mock_db_service
        
        # Mock email utils
        self.mock_email_utils = Mock()
        self.service.email_utils = self.mock_email_utils

    def test_persist_email_success(self):
        """Test successful email persistence."""
        # Mock no existing email (not duplicate)
        self.mock_email_utils.get_email_by_gmail_id.return_value = None
        
        # Test data
        email_data = {
            'id': 'test123',
            'thread_id': 'thread456',
            'headers': {
                'from': 'sender@example.com',
                'to': 'recipient@example.com',
                'subject': 'Test Subject',
                'date': 'Mon, 01 Jan 2024 12:00:00 +0000'
            },
            'body': {
                'text': 'Test body text',
                'html': '<p>Test body html</p>'
            },
            'internal_date': '1704110400000',  # 2024-01-01 12:00:00 UTC
            'label_ids': ['INBOX'],
            'size_estimate': 1024,
            'attachments': []
        }
        
        # Mock successful database operations
        mock_email = Mock(spec=Email)
        mock_email.id = 1
        self.mock_session.add.return_value = None
        self.mock_session.commit.return_value = None
        self.mock_session.refresh.return_value = None
        
        # Mock the _create_email_record method to return our mock email
        with patch.object(self.service, '_create_email_record', return_value=mock_email):
            result = self.service.persist_email(email_data, 'user123')
        
        # Verify results
        self.assertEqual(result, mock_email)
        self.mock_session.add.assert_called_once_with(mock_email)
        self.mock_session.commit.assert_called_once()
        self.mock_session.refresh.assert_called_once_with(mock_email)

    def test_persist_email_duplicate(self):
        """Test handling of duplicate emails."""
        # Mock existing email (duplicate)
        existing_email = Mock(spec=Email)
        existing_email.id = 1
        self.mock_email_utils.get_email_by_gmail_id.return_value = existing_email
        
        email_data = {'id': 'test123'}
        
        result = self.service.persist_email(email_data, 'user123')
        
        # Should return existing email and not attempt to save
        self.assertEqual(result, existing_email)
        self.mock_session.add.assert_not_called()

    def test_persist_email_missing_id(self):
        """Test error handling for missing Gmail message ID."""
        email_data = {}  # Missing 'id'
        
        with self.assertRaises(ValueError) as context:
            self.service.persist_email(email_data, 'user123')
        
        self.assertIn("Gmail message ID is required", str(context.exception))

    def test_create_email_record(self):
        """Test creating email record from Gmail data."""
        email_data = {
            'id': 'gmail123',
            'thread_id': 'thread456',
            'headers': {
                'from': 'Test User <sender@example.com>',
                'to': 'recipient1@example.com, recipient2@example.com',
                'cc': 'cc@example.com',
                'subject': 'Test Subject',
                'date': 'Mon, 01 Jan 2024 12:00:00 +0000'
            },
            'body': {
                'text': 'Test body text',
                'html': '<p>Test body html</p>'
            },
            'internal_date': '1704110400000',
            'label_ids': ['INBOX', 'UNREAD'],
            'size_estimate': 2048,
            'attachments': [{'filename': 'test.pdf'}]
        }
        
        email_record = self.service._create_email_record(email_data)
        
        # Verify email record properties
        self.assertEqual(email_record.gmail_message_id, 'gmail123')
        self.assertEqual(email_record.gmail_thread_id, 'thread456')
        self.assertEqual(email_record.subject, 'Test Subject')
        self.assertEqual(email_record.sender, 'sender@example.com')
        self.assertEqual(email_record.recipients, ['recipient1@example.com', 'recipient2@example.com'])
        self.assertEqual(email_record.cc_recipients, ['cc@example.com'])
        self.assertEqual(email_record.body_text, 'Test body text')
        self.assertEqual(email_record.body_html, '<p>Test body html</p>')
        self.assertEqual(email_record.size_bytes, 2048)
        self.assertTrue(email_record.has_attachments)
        self.assertEqual(email_record.attachment_count, 1)
        self.assertFalse(email_record.is_read)  # UNREAD in labels
        self.assertFalse(email_record.is_starred)  # STARRED not in labels

    def test_extract_email_address(self):
        """Test email address extraction from headers."""
        # Test various email header formats
        test_cases = [
            ('user@example.com', 'user@example.com'),
            ('Test User <user@example.com>', 'user@example.com'),
            ('"Test User" <user@example.com>', 'user@example.com'),
            ('user@example.com (Test User)', 'user@example.com'),
            ('', ''),
            ('Invalid header', ''),
        ]
        
        for header, expected in test_cases:
            with self.subTest(header=header):
                result = self.service._extract_email_address(header)
                self.assertEqual(result, expected)

    def test_parse_recipients(self):
        """Test parsing multiple recipients."""
        recipients_header = 'user1@example.com, Test User <user2@example.com>, user3@example.com'
        expected = ['user1@example.com', 'user2@example.com', 'user3@example.com']
        
        result = self.service._parse_recipients(recipients_header)
        self.assertEqual(result, expected)

    def test_sanitize_text(self):
        """Test text sanitization."""
        test_cases = [
            ('Normal text', 'Normal text'),
            ('Text with\x00null byte', 'Text withnull byte'),
            ('Text with\tvalid tab', 'Text with\tvalid tab'),
            ('Text with\x01control char', 'Text withcontrol char'),
            ('', ''),
            (None, ''),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=repr(input_text)):
                result = self.service._sanitize_text(input_text)
                self.assertEqual(result, expected)

    def test_get_emails_by_criteria(self):
        """Test querying emails by various criteria."""
        # Mock query chain
        mock_query = Mock()
        self.mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [Mock(spec=Email)]
        
        criteria = {
            'sender': 'test@example.com',
            'subject': 'Important',
            'has_attachments': True,
            'processing_status': 'pending'
        }
        
        result = self.service.get_emails_by_criteria(criteria, limit=10, offset=0)
        
        # Verify query was built correctly
        self.mock_session.query.assert_called_once_with(Email)
        self.assertEqual(len(result), 1)

    def test_search_emails_fulltext(self):
        """Test full-text search functionality."""
        # Mock query chain
        mock_query = Mock()
        self.mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock(spec=Email)]
        
        result = self.service.search_emails_fulltext('search term', limit=5)
        
        # Verify query was executed
        self.mock_session.query.assert_called_once_with(Email)
        self.assertEqual(len(result), 1)

    def test_update_processing_status(self):
        """Test updating email processing status."""
        # Mock email exists
        mock_email = Mock(spec=Email)
        mock_email.id = 1
        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_email
        
        result = self.service.update_processing_status(1, 'completed', None)
        
        # Verify update
        self.assertTrue(result)
        self.assertEqual(mock_email.processing_status, 'completed')
        self.assertIsNotNone(mock_email.processed_at)
        self.mock_session.commit.assert_called_once()

    def test_get_email_persistence_service_singleton(self):
        """Test that the global service function returns singleton."""
        service1 = get_email_persistence_service()
        service2 = get_email_persistence_service()
        
        self.assertIs(service1, service2)
        self.assertIsInstance(service1, EmailPersistenceService)


if __name__ == '__main__':
    unittest.main()

"""
Unit tests for GmailMessageService

Tests cover message fetching, parsing, HTML conversion, MIME handling,
pagination, and error scenarios.
"""

import base64
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
import pytest
from googleapiclient.errors import HttpError

from services.gmail_message_service import GmailMessageService
from services.gmail_service import GmailService


class TestGmailMessageService(unittest.TestCase):
    """Test cases for GmailMessageService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_gmail_service = Mock(spec=GmailService)
        self.service = GmailMessageService(self.mock_gmail_service)

    def test_init_default_service(self):
        """Test initialization with default Gmail service."""
        service = GmailMessageService()
        self.assertIsInstance(service.gmail_service, GmailService)

    def test_init_custom_service(self):
        """Test initialization with custom Gmail service."""
        service = GmailMessageService(self.mock_gmail_service)
        self.assertEqual(service.gmail_service, self.mock_gmail_service)

    @patch('services.gmail_message_service.logger')
    def test_fetch_message_by_id_success(self, mock_logger):
        """Test successful message fetching by ID."""
        # Mock data
        message_id = '12345'
        user_id = 'test_user'
        raw_message = {
            'id': message_id,
            'threadId': 'thread_123',
            'labelIds': ['INBOX'],
            'snippet': 'Test message snippet',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'From', 'value': 'sender@example.com'},
                    {'name': 'To', 'value': 'recipient@example.com'}
                ],
                'mimeType': 'text/plain',
                'body': {'data': base64.urlsafe_b64encode(b'Test message body').decode()}
            }
        }

        # Mock Gmail client
        mock_client = Mock()
        mock_client.users().messages().get.return_value.execute.return_value = raw_message
        self.mock_gmail_service.get_gmail_client.return_value = mock_client

        # Execute test
        result = self.service.fetch_message_by_id(user_id, message_id)

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], message_id)
        self.assertEqual(result['headers']['subject'], 'Test Subject')
        self.assertEqual(result['body']['text'], 'Test message body')
        mock_logger.info.assert_called_once()

    def test_fetch_message_by_id_no_client(self):
        """Test message fetching when Gmail client is not available."""
        self.mock_gmail_service.get_gmail_client.return_value = None

        result = self.service.fetch_message_by_id('test_user', '12345')

        self.assertIsNone(result)

    def test_fetch_message_by_id_api_error(self):
        """Test message fetching with Gmail API error."""
        mock_client = Mock()
        mock_client.users().messages().get.side_effect = HttpError(
            Mock(status=404), b'Not Found'
        )
        self.mock_gmail_service.get_gmail_client.return_value = mock_client

        result = self.service.fetch_message_by_id('test_user', '12345')

        self.assertIsNone(result)

    def test_fetch_messages_by_query_success(self):
        """Test successful message search with query."""
        # Mock search results
        search_results = {
            'messages': [
                {'id': 'msg1'},
                {'id': 'msg2'}
            ]
        }

        # Mock message data
        mock_messages = [
            {'id': 'msg1', 'payload': {'headers': []}},
            {'id': 'msg2', 'payload': {'headers': []}}
        ]

        mock_client = Mock()
        mock_client.users().messages().list.return_value.execute.return_value = search_results
        self.mock_gmail_service.get_gmail_client.return_value = mock_client

        with patch.object(self.service, 'fetch_message_by_id', side_effect=mock_messages):
            result = self.service.fetch_messages_by_query('test_user', 'test query', max_results=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], 'msg1')

    def test_fetch_messages_by_query_pagination(self):
        """Test message search with pagination."""
        # Mock first page
        first_page = {
            'messages': [{'id': 'msg1'}],
            'nextPageToken': 'token123'
        }

        # Mock second page
        second_page = {
            'messages': [{'id': 'msg2'}]
        }

        mock_client = Mock()
        mock_client.users().messages().list.return_value.execute.side_effect = [
            first_page, second_page
        ]
        self.mock_gmail_service.get_gmail_client.return_value = mock_client

        mock_messages = [
            {'id': 'msg1', 'payload': {'headers': []}},
            {'id': 'msg2', 'payload': {'headers': []}}
        ]

        with patch.object(self.service, 'fetch_message_by_id', side_effect=mock_messages):
            result = self.service.fetch_messages_by_query('test_user', '', max_results=2)

        self.assertEqual(len(result), 2)

    def test_parse_message_headers(self):
        """Test message header parsing."""
        headers = [
            {'name': 'Subject', 'value': 'Test Subject'},
            {'name': 'From', 'value': 'sender@example.com'},
            {'name': 'Received', 'value': 'by mail.example.com'},
            {'name': 'Received', 'value': 'from sender.example.com'}
        ]

        result = self.service._parse_message_headers(headers)

        self.assertEqual(result['subject'], 'Test Subject')
        self.assertEqual(result['from'], 'sender@example.com')
        self.assertEqual(len(result['received']), 2)

    def test_decode_body_data_success(self):
        """Test successful base64 body data decoding."""
        test_data = base64.urlsafe_b64encode(b'Test message content').decode()

        result = self.service._decode_body_data(test_data)

        self.assertEqual(result, 'Test message content')

    def test_decode_body_data_empty(self):
        """Test decoding empty body data."""
        result = self.service._decode_body_data('')

        self.assertEqual(result, '')

    def test_decode_body_data_padding(self):
        """Test decoding with missing padding."""
        # Create data without padding
        test_data = base64.urlsafe_b64encode(b'Test').decode().rstrip('=')

        result = self.service._decode_body_data(test_data)

        self.assertEqual(result, 'Test')

    def test_html_to_text_conversion(self):
        """Test HTML to plain text conversion."""
        html_content = '''
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>Hello World</h1>
            <p>This is a <strong>test</strong> message.</p>
            <script>alert('test');</script>
            <style>body { color: red; }</style>
        </body>
        </html>
        '''

        result = self.service._html_to_text(html_content)

        # Should contain text but not HTML tags or script/style content
        self.assertIn('Hello World', result)
        self.assertIn('This is a test message.', result)
        self.assertNotIn('<h1>', result)
        self.assertNotIn('alert', result)
        self.assertNotIn('color: red', result)

    def test_html_to_text_empty(self):
        """Test HTML to text conversion with empty input."""
        result = self.service._html_to_text('')

        self.assertEqual(result, '')

    def test_extract_attachment(self):
        """Test attachment extraction from message part."""
        part = {
            'filename': 'test.pdf',
            'mimeType': 'application/pdf',
            'size': 1024,
            'headers': [
                {'name': 'Content-Disposition', 'value': 'attachment; filename="test.pdf"'}
            ]
        }

        body = {
            'attachmentId': 'attach_123'
        }

        result = self.service._extract_attachment(part, body)

        self.assertIsNotNone(result)
        self.assertEqual(result['filename'], 'test.pdf')
        self.assertEqual(result['mime_type'], 'application/pdf')
        self.assertEqual(result['attachment_id'], 'attach_123')
        self.assertIn('content-disposition', result['headers'])

    def test_download_attachment_success(self):
        """Test successful attachment download."""
        attachment_data = b'Test attachment content'
        encoded_data = base64.urlsafe_b64encode(attachment_data).decode()

        mock_client = Mock()
        mock_attachment = {
            'data': encoded_data
        }
        mock_client.users().messages().attachments().get.return_value.execute.return_value = mock_attachment
        self.mock_gmail_service.get_gmail_client.return_value = mock_client

        result = self.service.download_attachment('test_user', 'msg123', 'attach123')

        self.assertEqual(result, attachment_data)

    def test_download_attachment_no_client(self):
        """Test attachment download when Gmail client is not available."""
        self.mock_gmail_service.get_gmail_client.return_value = None

        result = self.service.download_attachment('test_user', 'msg123', 'attach123')

        self.assertIsNone(result)

    def test_get_message_raw_content(self):
        """Test getting raw message content."""
        raw_content = 'From: sender@example.com\nSubject: Test\n\nTest body'
        encoded_content = base64.urlsafe_b64encode(raw_content.encode()).decode()

        mock_message = {
            'id': 'msg123',
            'raw': encoded_content,
            'payload': {'headers': []}
        }

        with patch.object(self.service, 'fetch_message_by_id', return_value=mock_message):
            result = self.service.get_message_raw_content('test_user', 'msg123')

        self.assertEqual(result, raw_content)

    def test_search_messages_with_filters(self):
        """Test structured message search with filters."""
        filters = {
            'from': 'sender@example.com',
            'subject': 'Test Subject',
            'after': '2023-01-01',
            'has_attachment': True
        }

        mock_messages = [
            {'id': 'msg1', 'payload': {'headers': []}}
        ]

        with patch.object(self.service, 'fetch_messages_by_query', return_value=mock_messages):
            result = self.service.search_messages_with_filters('test_user', filters)

        self.assertEqual(len(result), 1)

        # Verify the query was constructed correctly
        expected_query = 'from:sender@example.com subject:"Test Subject" after:2023-01-01 has:attachment'
        self.service.fetch_messages_by_query.assert_called_with(
            'test_user', expected_query, 50
        )

    def test_get_message_thread_success(self):
        """Test successful thread retrieval."""
        thread_data = {
            'messages': [
                {'id': 'msg1'},
                {'id': 'msg2'}
            ]
        }

        mock_messages = [
            {'id': 'msg1', 'payload': {'headers': []}},
            {'id': 'msg2', 'payload': {'headers': []}}
        ]

        mock_client = Mock()
        mock_client.users().threads().get.return_value.execute.return_value = thread_data
        self.mock_gmail_service.get_gmail_client.return_value = mock_client

        with patch.object(self.service, 'fetch_message_by_id', side_effect=mock_messages):
            result = self.service.get_message_thread('test_user', 'thread123')

        self.assertEqual(len(result), 2)

    def test_get_message_summary_success(self):
        """Test successful message summary retrieval."""
        mock_message = {
            'id': 'msg123',
            'thread_id': 'thread123',
            'label_ids': ['INBOX'],
            'snippet': 'Test snippet',
            'size_estimate': 2048,
            'internal_date': '1672531200000',
            'headers': {
                'from': 'sender@example.com',
                'to': 'recipient@example.com',
                'subject': 'Test Subject',
                'date': 'Mon, 01 Jan 2023 00:00:00 +0000',
                'message-id': '<test@example.com>'
            },
            'attachments': [
                {'filename': 'test.pdf'}
            ]
        }

        with patch.object(self.service, 'fetch_message_by_id', return_value=mock_message):
            result = self.service.get_message_summary('test_user', 'msg123')

        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'msg123')
        self.assertEqual(result['attachment_count'], 1)
        self.assertEqual(result['headers']['from'], 'sender@example.com')

    def test_batch_fetch_message_summaries(self):
        """Test batch fetching of message summaries."""
        message_ids = ['msg1', 'msg2', 'msg3']

        mock_summaries = [
            {'id': 'msg1', 'attachment_count': 0},
            {'id': 'msg2', 'attachment_count': 1},
            None  # Simulate one failed fetch
        ]

        with patch.object(self.service, 'get_message_summary', side_effect=mock_summaries):
            result = self.service.batch_fetch_message_summaries('test_user', message_ids)

        self.assertEqual(len(result), 2)  # Only successful summaries returned
        self.assertEqual(result[0]['id'], 'msg1')
        self.assertEqual(result[1]['id'], 'msg2')

    def test_process_message_part_text_plain(self):
        """Test processing plain text message part."""
        message = {'body': {'text': '', 'html': ''}, 'attachments': []}

        part = {
            'mimeType': 'text/plain',
            'body': {'data': base64.urlsafe_b64encode(b'Hello World').decode()}
        }

        self.service._process_message_part(part, message)

        self.assertEqual(message['body']['text'], 'Hello World')
        self.assertEqual(len(message['attachments']), 0)

    def test_process_message_part_text_html(self):
        """Test processing HTML message part."""
        message = {'body': {'text': '', 'html': ''}, 'attachments': []}

        html_content = '<p>Hello <strong>World</strong></p>'
        part = {
            'mimeType': 'text/html',
            'body': {'data': base64.urlsafe_b64encode(html_content.encode()).decode()}
        }

        self.service._process_message_part(part, message)

        self.assertIn('Hello World', message['body']['text'])
        self.assertEqual(message['body']['html'], html_content)

    def test_process_message_part_attachment(self):
        """Test processing attachment message part."""
        message = {'body': {'text': '', 'html': ''}, 'attachments': []}

        part = {
            'filename': 'document.pdf',
            'mimeType': 'application/pdf',
            'size': 2048,
            'body': {'attachmentId': 'attach123'}
        }

        self.service._process_message_part(part, message)

        self.assertEqual(len(message['attachments']), 1)
        self.assertEqual(message['attachments'][0]['filename'], 'document.pdf')

    def test_process_message_part_multipart(self):
        """Test processing multipart message part."""
        message = {'body': {'text': '', 'html': ''}, 'attachments': []}

        part = {
            'mimeType': 'multipart/mixed',
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {'data': base64.urlsafe_b64encode(b'Hello').decode()}
                },
                {
                    'filename': 'test.pdf',
                    'mimeType': 'application/pdf',
                    'body': {'attachmentId': 'attach123'}
                }
            ]
        }

        self.service._process_message_part(part, message)

        self.assertEqual(message['body']['text'], 'Hello')
        self.assertEqual(len(message['attachments']), 1)


class TestGmailMessageServiceIntegration(unittest.TestCase):
    """Integration tests for GmailMessageService."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.service = GmailMessageService()

    @patch('services.gmail_message_service.GmailService')
    def test_get_gmail_message_service_default(self, mock_gmail_service_class):
        """Test getting default message service instance."""
        from services.gmail_message_service import get_gmail_message_service

        # Reset global instance
        import services.gmail_message_service
        services.gmail_message_service._message_service = None

        mock_gmail_service = Mock()
        mock_gmail_service_class.return_value = mock_gmail_service

        service = get_gmail_message_service()

        self.assertIsInstance(service, GmailMessageService)
        mock_gmail_service_class.assert_called_once()

    @patch('services.gmail_message_service.GmailService')
    def test_get_gmail_message_service_custom(self, mock_gmail_service_class):
        """Test getting message service with custom Gmail service."""
        from services.gmail_message_service import get_gmail_message_service

        # Reset global instance
        import services.gmail_message_service
        services.gmail_message_service._message_service = None

        custom_gmail_service = Mock()
        service = get_gmail_message_service(custom_gmail_service)

        self.assertIsInstance(service, GmailMessageService)
        self.assertEqual(service.gmail_service, custom_gmail_service)
        mock_gmail_service_class.assert_not_called()


if __name__ == '__main__':
    unittest.main()

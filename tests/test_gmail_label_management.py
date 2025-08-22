"""
Tests for Gmail label management functionality.

This module tests the label management features implemented in Task 6,
including listing labels, creating labels, assigning labels to messages,
and utility functions for label name/ID conversion.
"""

import pytest
import unittest.mock as mock
from typing import Dict, Any, List, Optional

from services.gmail_service import GmailService
from googleapiclient.errors import HttpError


class TestGmailLabelManagement:
    """Test cases for Gmail label management functionality."""

    @pytest.fixture
    def gmail_service(self) -> GmailService:
        """Create a GmailService instance for testing."""
        return GmailService()

    @pytest.fixture
    def mock_gmail_client(self):
        """Mock Gmail API client for testing."""
        return mock.Mock()

    def test_list_labels_success(self, gmail_service: GmailService, mock_gmail_client):
        """Test successful label listing."""
        # Mock response
        mock_labels_response = {
            'labels': [
                {'id': 'Label_1', 'name': 'Important', 'type': 'user'},
                {'id': 'Label_2', 'name': 'Work', 'type': 'user'},
                {'id': 'INBOX', 'name': 'INBOX', 'type': 'system'}
            ]
        }
        mock_gmail_client.users().labels().list.return_value.execute.return_value = mock_labels_response

        with mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):
            result = gmail_service.list_labels('test_user')

            assert result is not None
            assert len(result) == 3
            assert result[0]['name'] == 'Important'
            assert result[1]['name'] == 'Work'
            assert result[2]['name'] == 'INBOX'

            mock_gmail_client.users().labels().list.assert_called_once_with(userId='me')

    def test_list_labels_no_client(self, gmail_service: GmailService):
        """Test label listing when Gmail client is not available."""
        with mock.patch.object(gmail_service, 'get_gmail_client', return_value=None):
            result = gmail_service.list_labels('test_user')

            assert result is None

    def test_list_labels_api_error(self, gmail_service: GmailService, mock_gmail_client):
        """Test label listing with API error."""
        mock_gmail_client.users().labels().list.side_effect = HttpError(
            resp=mock.Mock(status=500), content=b'Internal Server Error'
        )

        with mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):
            result = gmail_service.list_labels('test_user')

            assert result is None

    def test_get_label_by_name_found(self, gmail_service: GmailService):
        """Test getting a label by name when it exists."""
        mock_labels = [
            {'id': 'Label_1', 'name': 'Important', 'type': 'user'},
            {'id': 'Label_2', 'name': 'Work', 'type': 'user'}
        ]

        with mock.patch.object(gmail_service, 'list_labels', return_value=mock_labels):
            result = gmail_service.get_label_by_name('test_user', 'Work')

            assert result is not None
            assert result['id'] == 'Label_2'
            assert result['name'] == 'Work'

    def test_get_label_by_name_not_found(self, gmail_service: GmailService):
        """Test getting a label by name when it doesn't exist."""
        mock_labels = [
            {'id': 'Label_1', 'name': 'Important', 'type': 'user'}
        ]

        with mock.patch.object(gmail_service, 'list_labels', return_value=mock_labels):
            result = gmail_service.get_label_by_name('test_user', 'NonExistent')

            assert result is None

    def test_get_label_by_name_no_labels(self, gmail_service: GmailService):
        """Test getting a label by name when no labels are available."""
        with mock.patch.object(gmail_service, 'list_labels', return_value=None):
            result = gmail_service.get_label_by_name('test_user', 'Important')

            assert result is None

    def test_get_label_by_id_success(self, gmail_service: GmailService, mock_gmail_client):
        """Test getting a label by ID successfully."""
        mock_label_response = {
            'id': 'Label_1',
            'name': 'Important',
            'type': 'user',
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        mock_gmail_client.users().labels().get.return_value.execute.return_value = mock_label_response

        with mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):
            result = gmail_service.get_label_by_id('test_user', 'Label_1')

            assert result is not None
            assert result['id'] == 'Label_1'
            assert result['name'] == 'Important'

            mock_gmail_client.users().labels().get.assert_called_once_with(userId='me', id='Label_1')

    def test_get_label_by_id_not_found(self, gmail_service: GmailService, mock_gmail_client):
        """Test getting a label by ID when it doesn't exist."""
        mock_response = mock.Mock(status=404)
        mock_gmail_client.users().labels().get.side_effect = HttpError(
            resp=mock_response, content=b'Label not found'
        )

        with mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):
            result = gmail_service.get_label_by_id('test_user', 'NonExistent')

            assert result is None

    def test_get_label_by_id_no_client(self, gmail_service: GmailService):
        """Test getting a label by ID when Gmail client is not available."""
        with mock.patch.object(gmail_service, 'get_gmail_client', return_value=None):
            result = gmail_service.get_label_by_id('test_user', 'Label_1')

            assert result is None

    def test_ensure_label_exists_already_exists(self, gmail_service: GmailService):
        """Test ensuring a label exists when it already exists."""
        mock_label = {'id': 'Label_1', 'name': 'Important', 'type': 'user'}

        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=mock_label):
            result = gmail_service.ensure_label_exists('test_user', 'Important')

            assert result is not None
            assert result['id'] == 'Label_1'
            assert result['name'] == 'Important'

    def test_ensure_label_exists_create_new(self, gmail_service: GmailService, mock_gmail_client):
        """Test ensuring a label exists by creating a new one."""
        mock_created_label = {
            'id': 'Label_3',
            'name': 'NewLabel',
            'type': 'user',
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }

        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=None), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            mock_gmail_client.users().labels().create.return_value.execute.return_value = mock_created_label

            result = gmail_service.ensure_label_exists('test_user', 'NewLabel')

            assert result is not None
            assert result['id'] == 'Label_3'
            assert result['name'] == 'NewLabel'

            # Verify the create call was made with correct parameters
            mock_gmail_client.users().labels().create.assert_called_once_with(
                userId='me',
                body={
                    'name': 'NewLabel',
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show'
                }
            )

    def test_ensure_label_exists_create_with_color(self, gmail_service: GmailService, mock_gmail_client):
        """Test ensuring a label exists with custom color settings."""
        mock_created_label = {
            'id': 'Label_4',
            'name': 'ColoredLabel',
            'type': 'user',
            'color': {'backgroundColor': '#ff0000', 'textColor': '#ffffff'}
        }

        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=None), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            mock_gmail_client.users().labels().create.return_value.execute.return_value = mock_created_label

            color_settings = {'color': {'backgroundColor': '#ff0000', 'textColor': '#ffffff'}}
            result = gmail_service.ensure_label_exists('test_user', 'ColoredLabel', color_settings)

            assert result is not None
            assert result['color']['backgroundColor'] == '#ff0000'

            # Verify the create call included color settings
            call_args = mock_gmail_client.users().labels().create.call_args
            body = call_args[1]['body']
            assert 'color' in body
            assert body['color']['backgroundColor'] == '#ff0000'

    def test_ensure_label_exists_no_client(self, gmail_service: GmailService):
        """Test ensuring a label exists when Gmail client is not available."""
        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=None), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=None):

            result = gmail_service.ensure_label_exists('test_user', 'NewLabel')

            assert result is None

    def test_assign_label_to_message_by_name(self, gmail_service: GmailService, mock_gmail_client):
        """Test assigning a label to a message using label name."""
        mock_label = {'id': 'Label_1', 'name': 'Important'}

        with mock.patch.object(gmail_service, '_resolve_label_to_id', return_value='Label_1'), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            result = gmail_service.assign_label_to_message('test_user', 'msg_123', 'Important')

            assert result is True

            # Verify the modify call was made correctly
            mock_gmail_client.users().messages().modify.assert_called_once_with(
                userId='me',
                id='msg_123',
                body={'addLabelIds': ['Label_1']}
            )

    def test_assign_label_to_message_by_id(self, gmail_service: GmailService, mock_gmail_client):
        """Test assigning a label to a message using label ID."""
        with mock.patch.object(gmail_service, '_resolve_label_to_id', return_value='Label_1'), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            result = gmail_service.assign_label_to_message('test_user', 'msg_123', 'Label_1')

            assert result is True

    def test_assign_label_to_message_no_label(self, gmail_service: GmailService):
        """Test assigning a label when the label cannot be resolved."""
        with mock.patch.object(gmail_service, '_resolve_label_to_id', return_value=None):
            result = gmail_service.assign_label_to_message('test_user', 'msg_123', 'NonExistent')

            assert result is False

    def test_assign_label_to_message_no_client(self, gmail_service: GmailService):
        """Test assigning a label when Gmail client is not available."""
        with mock.patch.object(gmail_service, '_resolve_label_to_id', return_value='Label_1'), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=None):

            result = gmail_service.assign_label_to_message('test_user', 'msg_123', 'Important')

            assert result is False

    def test_remove_label_from_message(self, gmail_service: GmailService, mock_gmail_client):
        """Test removing a label from a message."""
        with mock.patch.object(gmail_service, '_resolve_label_to_id', return_value='Label_1'), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            result = gmail_service.remove_label_from_message('test_user', 'msg_123', 'Important')

            assert result is True

            # Verify the modify call was made correctly
            mock_gmail_client.users().messages().modify.assert_called_once_with(
                userId='me',
                id='msg_123',
                body={'removeLabelIds': ['Label_1']}
            )

    def test_assign_labels_to_messages_success(self, gmail_service: GmailService, mock_gmail_client):
        """Test assigning multiple labels to multiple messages successfully."""
        with mock.patch.object(gmail_service, '_resolve_label_to_id', side_effect=['Label_1', 'Label_2']), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            result = gmail_service.assign_labels_to_messages(
                'test_user',
                ['msg_123', 'msg_456'],
                ['Important', 'Work']
            )

            assert result['successful'] == 2
            assert result['failed'] == 0
            assert len(result['errors']) == 0

            # Verify two modify calls were made
            assert mock_gmail_client.users().messages().modify.call_count == 2

    def test_assign_labels_to_messages_partial_failure(self, gmail_service: GmailService, mock_gmail_client):
        """Test assigning multiple labels when some operations fail."""
        # Mock label resolution to return None for NonExistent and Label_1 for Important
        def resolve_side_effect(user_id, label_name):
            if label_name == 'Important':
                return 'Label_1'
            elif label_name == 'NonExistent':
                return None
            else:
                return 'Label_2'

        # Mock modify call to fail for msg_123 but succeed for msg_456
        def modify_side_effect(**kwargs):
            if kwargs.get('id') == 'msg_123':
                raise HttpError(resp=mock.Mock(status=400), content=b'Bad Request')
            else:
                return mock.Mock()

        mock_gmail_client.users().messages().modify.side_effect = modify_side_effect

        with mock.patch.object(gmail_service, '_resolve_label_to_id', side_effect=resolve_side_effect), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            result = gmail_service.assign_labels_to_messages(
                'test_user',
                ['msg_123', 'msg_456'],
                ['Important', 'NonExistent']
            )

            assert result['successful'] == 1  # Only msg_456 succeeded
            assert result['failed'] == 2     # msg_123 failed + NonExistent label failed
            assert len(result['errors']) == 2

    def test_resolve_label_to_id_by_name(self, gmail_service: GmailService):
        """Test resolving a label name to ID."""
        mock_label = {'id': 'Label_1', 'name': 'Important'}

        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=mock_label):
            result = gmail_service._resolve_label_to_id('test_user', 'Important')

            assert result == 'Label_1'

    def test_resolve_label_to_id_by_id(self, gmail_service: GmailService):
        """Test resolving a label ID to ID."""
        mock_label = {'id': 'Label_1', 'name': 'Important'}

        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=None), \
             mock.patch.object(gmail_service, 'get_label_by_id', return_value=mock_label):

            result = gmail_service._resolve_label_to_id('test_user', 'Label_1')

            assert result == 'Label_1'

    def test_resolve_label_to_id_not_found(self, gmail_service: GmailService):
        """Test resolving a label when it doesn't exist."""
        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=None), \
             mock.patch.object(gmail_service, 'get_label_by_id', return_value=None):

            result = gmail_service._resolve_label_to_id('test_user', 'NonExistent')

            assert result is None

    def test_ensure_label_exists_api_error(self, gmail_service: GmailService, mock_gmail_client):
        """Test ensuring a label exists when API error occurs."""
        with mock.patch.object(gmail_service, 'get_label_by_name', return_value=None), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            mock_gmail_client.users().labels().create.side_effect = HttpError(
                resp=mock.Mock(status=400), content=b'Invalid label name'
            )

            result = gmail_service.ensure_label_exists('test_user', 'Invalid/Label')

            assert result is None

    def test_assign_label_to_message_api_error(self, gmail_service: GmailService, mock_gmail_client):
        """Test assigning a label when API error occurs."""
        with mock.patch.object(gmail_service, '_resolve_label_to_id', return_value='Label_1'), \
             mock.patch.object(gmail_service, 'get_gmail_client', return_value=mock_gmail_client):

            mock_gmail_client.users().messages().modify.side_effect = HttpError(
                resp=mock.Mock(status=403), content=b'Permission denied'
            )

            result = gmail_service.assign_label_to_message('test_user', 'msg_123', 'Important')

            assert result is False


if __name__ == '__main__':
    pytest.main([__file__])

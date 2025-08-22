"""
Gmail Message Service

Service for fetching and parsing Gmail messages, including headers, body content,
and attachments. Handles various MIME types, encodings, and pagination.
"""

import base64
import email
import email.policy
import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from typing import List, Dict, Any, Optional, Tuple, Union
from bs4 import BeautifulSoup
from googleapiclient.errors import HttpError

from .gmail_service import GmailService

logger = logging.getLogger(__name__)


class GmailMessageService:
    """
    Service for fetching and parsing Gmail messages.

    Provides functionality to:
    - Fetch messages by ID or query
    - Parse message headers and body content
    - Extract and decode attachments
    - Handle various MIME types and encodings
    - Implement pagination for large result sets
    """

    def __init__(self, gmail_service: Optional[GmailService] = None):
        """
        Initialize the message service.

        Args:
            gmail_service: Gmail service instance (creates default if None)
        """
        self.gmail_service = gmail_service or GmailService()

    def fetch_message_by_id(self, user_id: str, message_id: str, format_type: str = 'full') -> Optional[Dict[str, Any]]:
        """
        Fetch a single Gmail message by its ID.

        Args:
            user_id: User identifier
            message_id: Gmail message ID
            format_type: Message format ('full', 'metadata', 'minimal', 'raw')

        Returns:
            Parsed message dictionary or None if error
        """
        try:
            gmail_client = self.gmail_service.get_gmail_client(user_id)
            if not gmail_client:
                return None

            # Fetch the message
            message = gmail_client.users().messages().get(
                userId='me',
                id=message_id,
                format=format_type
            ).execute()

            # Parse the message content
            parsed_message = self._parse_message_content(message)

            logger.info(f"Successfully fetched message {message_id} for user {user_id}")
            return parsed_message

        except HttpError as e:
            logger.error(f"Gmail API error fetching message {message_id} for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching message {message_id} for user {user_id}: {e}")
            return None

    def fetch_messages_by_query(
        self,
        user_id: str,
        query: str = '',
        max_results: int = 50,
        include_spam_trash: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch Gmail messages matching a search query with pagination.

        Args:
            user_id: User identifier
            query: Gmail search query string
            max_results: Maximum number of messages to fetch
            include_spam_trash: Include messages from spam and trash

        Returns:
            List of parsed message dictionaries
        """
        messages = []
        next_page_token = None

        try:
            gmail_client = self.gmail_service.get_gmail_client(user_id)
            if not gmail_client:
                return messages

            while len(messages) < max_results:
                # Calculate how many messages to fetch in this batch
                batch_size = min(500, max_results - len(messages))  # Gmail API max is 500

                # Build request parameters
                request_params = {
                    'userId': 'me',
                    'maxResults': batch_size,
                    'q': query
                }

                if include_spam_trash:
                    request_params['includeSpamTrash'] = True

                if next_page_token:
                    request_params['pageToken'] = next_page_token

                # Execute search
                results = gmail_client.users().messages().list(**request_params).execute()

                message_list = results.get('messages', [])
                if not message_list:
                    break

                # Fetch full message details for each message
                for msg_data in message_list:
                    message = self.fetch_message_by_id(user_id, msg_data['id'])
                    if message:
                        messages.append(message)

                    # Break if we've reached the desired count
                    if len(messages) >= max_results:
                        break

                # Check for next page
                next_page_token = results.get('nextPageToken')
                if not next_page_token:
                    break

            logger.info(f"Fetched {len(messages)} messages matching query '{query}' for user {user_id}")
            return messages

        except HttpError as e:
            logger.error(f"Gmail API error searching messages for user {user_id}: {e}")
            return messages
        except Exception as e:
            logger.error(f"Unexpected error searching messages for user {user_id}: {e}")
            return messages

    def fetch_messages_by_ids(
        self,
        user_id: str,
        message_ids: List[str],
        format_type: str = 'full'
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple Gmail messages by their IDs.

        Args:
            user_id: User identifier
            message_ids: List of Gmail message IDs
            format_type: Message format type

        Returns:
            List of parsed message dictionaries
        """
        messages = []

        try:
            for message_id in message_ids:
                message = self.fetch_message_by_id(user_id, message_id, format_type)
                if message:
                    messages.append(message)

            logger.info(f"Successfully fetched {len(messages)}/{len(message_ids)} messages for user {user_id}")
            return messages

        except Exception as e:
            logger.error(f"Error fetching messages by IDs for user {user_id}: {e}")
            return messages

    def _parse_message_content(self, raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw Gmail message data into structured format.

        Args:
            raw_message: Raw message data from Gmail API

        Returns:
            Parsed message dictionary
        """
        try:
            message = {
                'id': raw_message.get('id'),
                'thread_id': raw_message.get('threadId'),
                'label_ids': raw_message.get('labelIds', []),
                'snippet': raw_message.get('snippet', ''),
                'size_estimate': raw_message.get('sizeEstimate', 0),
                'history_id': raw_message.get('historyId'),
                'internal_date': raw_message.get('internalDate'),
                'headers': {},
                'body': {
                    'text': '',
                    'html': ''
                },
                'attachments': []
            }

            # Parse message payload
            payload = raw_message.get('payload')
            if payload:
                # Extract headers
                message['headers'] = self._parse_message_headers(payload.get('headers', []))

                # Extract body and attachments
                self._extract_body_and_attachments(payload, message)

            return message

        except Exception as e:
            logger.error(f"Error parsing message content: {e}")
            return {
                'id': raw_message.get('id'),
                'error': str(e)
            }

    def _parse_message_headers(self, headers: List[Dict[str, str]]) -> Dict[str, str]:
        """
        Parse message headers into a dictionary.

        Args:
            headers: List of header dictionaries

        Returns:
            Dictionary of header key-value pairs
        """
        parsed_headers = {}

        for header in headers:
            name = header.get('name', '').lower()
            value = header.get('value', '')

            # Handle common headers with multiple values
            if name in ['received', 'delivered-to']:
                if name not in parsed_headers:
                    parsed_headers[name] = []
                parsed_headers[name].append(value)
            else:
                parsed_headers[name] = value

        return parsed_headers

    def _extract_body_and_attachments(self, payload: Dict[str, Any], message: Dict[str, Any]):
        """
        Extract body content and attachments from message payload.

        Args:
            payload: Message payload from Gmail API
            message: Message dictionary to update
        """
        try:
            mime_type = payload.get('mimeType', '')

            if mime_type.startswith('multipart/'):
                # Handle multipart messages
                parts = payload.get('parts', [])
                for part in parts:
                    self._process_message_part(part, message)
            else:
                # Handle simple messages
                self._process_message_part(payload, message)

        except Exception as e:
            logger.error(f"Error extracting body and attachments: {e}")

    def _process_message_part(self, part: Dict[str, Any], message: Dict[str, Any]):
        """
        Process a single message part to extract body or attachments.

        Args:
            part: Message part data
            message: Message dictionary to update
        """
        try:
            mime_type = part.get('mimeType', '')
            filename = part.get('filename', '')
            body = part.get('body', {})

            if filename or mime_type.startswith('application/') or mime_type.startswith('image/') or mime_type.startswith('audio/') or mime_type.startswith('video/'):
                # This is an attachment
                attachment = self._extract_attachment(part, body)
                if attachment:
                    message['attachments'].append(attachment)
            elif mime_type == 'text/plain':
                # Plain text body
                text_content = self._decode_body_data(body.get('data', ''))
                message['body']['text'] += text_content
            elif mime_type == 'text/html':
                # HTML body
                html_content = self._decode_body_data(body.get('data', ''))
                message['body']['html'] += html_content

                # Also extract plain text from HTML
                if not message['body']['text']:
                    message['body']['text'] = self._html_to_text(html_content)
            elif mime_type.startswith('multipart/'):
                # Recursively process nested parts
                nested_parts = part.get('parts', [])
                for nested_part in nested_parts:
                    self._process_message_part(nested_part, message)

        except Exception as e:
            logger.error(f"Error processing message part: {e}")

    def _extract_attachment(self, part: Dict[str, Any], body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract attachment information from a message part.

        Args:
            part: Message part data
            body: Body data containing attachment

        Returns:
            Attachment dictionary or None
        """
        try:
            attachment = {
                'filename': part.get('filename', 'unnamed_attachment'),
                'mime_type': part.get('mimeType', ''),
                'size': part.get('size', 0),
                'attachment_id': body.get('attachmentId'),
                'headers': {}
            }

            # Extract attachment headers if available
            if 'headers' in part:
                attachment['headers'] = self._parse_message_headers(part['headers'])

            return attachment

        except Exception as e:
            logger.error(f"Error extracting attachment: {e}")
            return None

    def _decode_body_data(self, data: str) -> str:
        """
        Decode base64-encoded body data.

        Args:
            data: Base64-encoded data string

        Returns:
            Decoded string
        """
        try:
            if not data:
                return ''

            # Add padding if necessary
            missing_padding = len(data) % 4
            if missing_padding:
                data += '=' * (4 - missing_padding)

            # Decode base64
            decoded_bytes = base64.urlsafe_b64decode(data)
            return decoded_bytes.decode('utf-8', errors='replace')

        except Exception as e:
            logger.error(f"Error decoding body data: {e}")
            return ''

    def _html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to plain text.

        Args:
            html_content: HTML string

        Returns:
            Plain text string
        """
        try:
            if not html_content:
                return ''

            # Use BeautifulSoup to parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            logger.error(f"Error converting HTML to text: {e}")
            return html_content

    def download_attachment(self, user_id: str, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Download attachment content from a message.

        Args:
            user_id: User identifier
            message_id: Gmail message ID
            attachment_id: Attachment ID

        Returns:
            Attachment content as bytes or None if error
        """
        try:
            gmail_client = self.gmail_service.get_gmail_client(user_id)
            if not gmail_client:
                return None

            # Download attachment
            attachment = gmail_client.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()

            # Decode attachment data
            data = attachment.get('data', '')
            if data:
                return base64.urlsafe_b64decode(data)

            return None

        except HttpError as e:
            logger.error(f"Gmail API error downloading attachment {attachment_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading attachment {attachment_id}: {e}")
            return None

    def get_message_raw_content(self, user_id: str, message_id: str) -> Optional[str]:
        """
        Get the raw RFC 2822 message content.

        Args:
            user_id: User identifier
            message_id: Gmail message ID

        Returns:
            Raw message content as string or None if error
        """
        try:
            message = self.fetch_message_by_id(user_id, message_id, format_type='raw')
            if not message or 'raw' not in message:
                return None

            raw_data = message['raw']
            return self._decode_body_data(raw_data)

        except Exception as e:
            logger.error(f"Error getting raw message content for {message_id}: {e}")
            return None

    def search_messages_with_filters(
        self,
        user_id: str,
        filters: Dict[str, Any],
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search messages using structured filters.

        Args:
            user_id: User identifier
            filters: Dictionary of search filters
            max_results: Maximum number of messages to return

        Returns:
            List of matching messages
        """
        try:
            # Build Gmail query string from filters
            query_parts = []

            # From filter
            if 'from' in filters:
                query_parts.append(f"from:{filters['from']}")

            # To filter
            if 'to' in filters:
                query_parts.append(f"to:{filters['to']}")

            # Subject filter
            if 'subject' in filters:
                query_parts.append(f"subject:\"{filters['subject']}\"")

            # Date filters
            if 'after' in filters:
                query_parts.append(f"after:{filters['after']}")
            if 'before' in filters:
                query_parts.append(f"before:{filters['before']}")

            # Has attachment filter
            if filters.get('has_attachment'):
                query_parts.append("has:attachment")

            # Label filter
            if 'label' in filters:
                query_parts.append(f"label:{filters['label']}")

            # Size filters
            if 'larger' in filters:
                query_parts.append(f"larger:{filters['larger']}")
            if 'smaller' in filters:
                query_parts.append(f"smaller:{filters['smaller']}")

            # Free text search
            if 'query' in filters:
                query_parts.append(filters['query'])

            # Combine all query parts
            query = ' '.join(query_parts)

            return self.fetch_messages_by_query(user_id, query, max_results)

        except Exception as e:
            logger.error(f"Error searching messages with filters for user {user_id}: {e}")
            return []

    def get_message_thread(self, user_id: str, thread_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages in a thread.

        Args:
            user_id: User identifier
            thread_id: Gmail thread ID

        Returns:
            List of messages in the thread
        """
        try:
            gmail_client = self.gmail_service.get_gmail_client(user_id)
            if not gmail_client:
                return []

            # Get thread details
            thread = gmail_client.users().threads().get(userId='me', id=thread_id).execute()

            messages = []
            for msg_data in thread.get('messages', []):
                message = self.fetch_message_by_id(user_id, msg_data['id'])
                if message:
                    messages.append(message)

            logger.info(f"Retrieved {len(messages)} messages from thread {thread_id} for user {user_id}")
            return messages

        except HttpError as e:
            logger.error(f"Gmail API error getting thread {thread_id} for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting thread {thread_id} for user {user_id}: {e}")
            return []

    def get_message_summary(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of message metadata without full content.

        Args:
            user_id: User identifier
            message_id: Gmail message ID

        Returns:
            Message summary dictionary or None if error
        """
        try:
            message = self.fetch_message_by_id(user_id, message_id, format_type='metadata')

            if not message:
                return None

            # Extract key metadata
            summary = {
                'id': message.get('id'),
                'thread_id': message.get('thread_id'),
                'label_ids': message.get('label_ids', []),
                'snippet': message.get('snippet', ''),
                'size_estimate': message.get('size_estimate', 0),
                'internal_date': message.get('internal_date'),
                'headers': {
                    'from': message.get('headers', {}).get('from', ''),
                    'to': message.get('headers', {}).get('to', ''),
                    'subject': message.get('headers', {}).get('subject', ''),
                    'date': message.get('headers', {}).get('date', ''),
                    'message_id': message.get('headers', {}).get('message-id', '')
                },
                'attachment_count': len(message.get('attachments', []))
            }

            return summary

        except Exception as e:
            logger.error(f"Error getting message summary for {message_id}: {e}")
            return None

    def batch_fetch_message_summaries(
        self,
        user_id: str,
        message_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch summaries for multiple messages efficiently.

        Args:
            user_id: User identifier
            message_ids: List of message IDs

        Returns:
            List of message summaries
        """
        summaries = []

        try:
            for message_id in message_ids:
                summary = self.get_message_summary(user_id, message_id)
                if summary:
                    summaries.append(summary)

            logger.info(f"Fetched {len(summaries)} message summaries for user {user_id}")
            return summaries

        except Exception as e:
            logger.error(f"Error batch fetching message summaries for user {user_id}: {e}")
            return summaries


# Global service instance
_message_service = None

def get_gmail_message_service(gmail_service: Optional[GmailService] = None) -> GmailMessageService:
    """Get the global Gmail message service instance."""
    global _message_service
    if _message_service is None:
        _message_service = GmailMessageService(gmail_service)
    return _message_service

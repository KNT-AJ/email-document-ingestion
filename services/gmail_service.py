"""
Gmail API Service

Complete Gmail API authentication and access service that integrates OAuth2 flow,
token management, and API client creation. This is the main service that applications
should use to interact with Gmail API.
"""

import logging
import os
from typing import Optional, Tuple, Dict, Any
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from .gmail_auth import GmailAuthService
from .token_manager import TokenManager
from .token_storage import get_token_storage

logger = logging.getLogger(__name__)


class GmailService:
    """
    Complete Gmail API service with authentication, token management, and API access.

    This service provides a unified interface for:
    - OAuth2 authentication flow
    - Token storage and refresh
    - Gmail API client creation
    - Error handling and logging
    """

    def __init__(
        self,
        client_secrets_file: Optional[str] = None,
        scopes: Optional[list] = None,
        redirect_uri: Optional[str] = None,
        token_storage=None
    ):
        """
        Initialize the Gmail service.

        Args:
            client_secrets_file: Path to client_secret.json (default: from env)
            scopes: OAuth2 scopes (default: Gmail readonly)
            redirect_uri: OAuth2 redirect URI (default: from env)
            token_storage: Token storage implementation (default: from config)
        """
        # Configuration
        self.client_secrets_file = client_secrets_file or os.environ.get(
            'GOOGLE_CLIENT_SECRETS_FILE', 'client_secret.json'
        )
        self.scopes = scopes or [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.labels',
            'https://www.googleapis.com/auth/pubsub'
        ]
        self.redirect_uri = redirect_uri or os.environ.get(
            'GOOGLE_REDIRECT_URI', 'http://localhost:8000/auth/callback'
        )

        # Initialize components
        self.auth_service = GmailAuthService(
            self.client_secrets_file,
            self.scopes,
            self.redirect_uri
        )

        self.token_storage = token_storage or get_token_storage()
        self.token_manager = TokenManager(self.token_storage)

    def get_authorization_url(self, user_id: str) -> Tuple[str, str]:
        """
        Generate authorization URL for user authentication.

        Args:
            user_id: User identifier for tracking authentication

        Returns:
            Tuple of (authorization_url, state_token)
        """
        try:
            # Check if user already has valid credentials
            existing_creds = self.token_manager.get_valid_credentials(user_id)
            if existing_creds:
                logger.info(f"User {user_id} already has valid credentials")
                return "", ""  # No need for authorization

            auth_url, state = self.auth_service.get_authorization_url()
            logger.info(f"Generated authorization URL for user: {user_id}")
            return auth_url, state

        except Exception as e:
            logger.error(f"Error generating authorization URL for user {user_id}: {e}")
            raise

    def handle_oauth_callback(self, callback_url: str, state: str, user_id: str) -> bool:
        """
        Handle OAuth2 callback and store credentials.

        Args:
            callback_url: Full callback URL from OAuth2 provider
            state: State token for CSRF protection
            user_id: User identifier

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Exchange authorization code for tokens
            credentials = self.auth_service.exchange_code(callback_url, state)

            if not credentials:
                logger.error(f"Failed to exchange authorization code for user: {user_id}")
                return False

            # Save credentials
            success = self.token_storage.save_credentials(user_id, credentials)

            if success:
                logger.info(f"Successfully authenticated and stored credentials for user: {user_id}")
                return True
            else:
                logger.error(f"Failed to save credentials for user: {user_id}")
                return False

        except Exception as e:
            logger.error(f"Error handling OAuth callback for user {user_id}: {e}")
            return False

    def get_gmail_client(self, user_id: str) -> Optional[Any]:
        """
        Get an authenticated Gmail API client for a user.

        Args:
            user_id: User identifier

        Returns:
            Gmail API client if authentication successful, None otherwise
        """
        try:
            # Get valid credentials
            credentials = self.token_manager.get_valid_credentials(user_id, self.scopes)

            if not credentials:
                logger.warning(f"No valid credentials available for user: {user_id}")
                return None

            # Build Gmail API client
            gmail_client = build('gmail', 'v1', credentials=credentials)

            logger.debug(f"Created Gmail API client for user: {user_id}")
            return gmail_client

        except HttpError as e:
            logger.error(f"Gmail API error for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating Gmail client for user {user_id}: {e}")
            return None

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get Gmail user profile information.

        Args:
            user_id: User identifier

        Returns:
            User profile dictionary or None if error
        """
        try:
            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return None

            profile = gmail_client.users().getProfile(userId='me').execute()
            logger.info(f"Retrieved profile for user: {user_id}")
            return profile

        except HttpError as e:
            logger.error(f"Error getting profile for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting profile for user {user_id}: {e}")
            return None

    def list_labels(self, user_id: str) -> Optional[list]:
        """
        List Gmail labels for a user.

        Args:
            user_id: User identifier

        Returns:
            List of labels or None if error
        """
        try:
            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return None

            results = gmail_client.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

            logger.info(f"Retrieved {len(labels)} labels for user: {user_id}")
            return labels

        except HttpError as e:
            logger.error(f"Error listing labels for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error listing labels for user {user_id}: {e}")
            return None

    def get_label_by_name(self, user_id: str, label_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a label by its name.

        Args:
            user_id: User identifier
            label_name: Name of the label to find

        Returns:
            Label dictionary or None if not found
        """
        labels = self.list_labels(user_id)
        if not labels:
            return None

        # Gmail label names are case-sensitive
        for label in labels:
            if label.get('name') == label_name:
                return label

        logger.debug(f"Label '{label_name}' not found for user: {user_id}")
        return None

    def get_label_by_id(self, user_id: str, label_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a label by its ID.

        Args:
            user_id: User identifier
            label_id: ID of the label to find

        Returns:
            Label dictionary or None if not found
        """
        try:
            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return None

            result = gmail_client.users().labels().get(userId='me', id=label_id).execute()
            return result

        except HttpError as e:
            if e.resp.status == 404:
                logger.debug(f"Label ID '{label_id}' not found for user: {user_id}")
            else:
                logger.error(f"Error getting label {label_id} for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting label {label_id} for user {user_id}: {e}")
            return None

    def ensure_label_exists(self, user_id: str, label_name: str, label_color: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """
        Ensure a label exists, creating it if necessary.

        Args:
            user_id: User identifier
            label_name: Name of the label to ensure exists
            label_color: Optional color settings for the label

        Returns:
            Label dictionary or None if error
        """
        try:
            # First, check if the label already exists
            existing_label = self.get_label_by_name(user_id, label_name)
            if existing_label:
                logger.debug(f"Label '{label_name}' already exists for user: {user_id}")
                return existing_label

            # Label doesn't exist, create it
            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return None

            label_body = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }

            # Add color settings if provided
            if label_color:
                label_body.update(label_color)

            result = gmail_client.users().labels().create(userId='me', body=label_body).execute()

            logger.info(f"Created label '{label_name}' for user: {user_id}")
            return result

        except HttpError as e:
            logger.error(f"Error ensuring label '{label_name}' exists for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error ensuring label '{label_name}' exists for user {user_id}: {e}")
            return None

    def assign_label_to_message(self, user_id: str, message_id: str, label_name_or_id: str) -> bool:
        """
        Assign a label to a Gmail message.

        Args:
            user_id: User identifier
            message_id: Gmail message ID
            label_name_or_id: Label name or ID to assign

        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine if we have a name or ID
            label_id = self._resolve_label_to_id(user_id, label_name_or_id)
            if not label_id:
                return False

            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return False

            # Modify the message to add the label
            modify_body = {
                'addLabelIds': [label_id]
            }

            gmail_client.users().messages().modify(
                userId='me',
                id=message_id,
                body=modify_body
            ).execute()

            logger.info(f"Assigned label '{label_name_or_id}' to message {message_id} for user: {user_id}")
            return True

        except HttpError as e:
            logger.error(f"Error assigning label '{label_name_or_id}' to message {message_id} for user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error assigning label '{label_name_or_id}' to message {message_id} for user {user_id}: {e}")
            return False

    def remove_label_from_message(self, user_id: str, message_id: str, label_name_or_id: str) -> bool:
        """
        Remove a label from a Gmail message.

        Args:
            user_id: User identifier
            message_id: Gmail message ID
            label_name_or_id: Label name or ID to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine if we have a name or ID
            label_id = self._resolve_label_to_id(user_id, label_name_or_id)
            if not label_id:
                return False

            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return False

            # Modify the message to remove the label
            modify_body = {
                'removeLabelIds': [label_id]
            }

            gmail_client.users().messages().modify(
                userId='me',
                id=message_id,
                body=modify_body
            ).execute()

            logger.info(f"Removed label '{label_name_or_id}' from message {message_id} for user: {user_id}")
            return True

        except HttpError as e:
            logger.error(f"Error removing label '{label_name_or_id}' from message {message_id} for user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error removing label '{label_name_or_id}' from message {message_id} for user {user_id}: {e}")
            return False

    def assign_labels_to_messages(self, user_id: str, message_ids: list, label_names_or_ids: list) -> Dict[str, Any]:
        """
        Assign multiple labels to multiple messages.

        Args:
            user_id: User identifier
            message_ids: List of Gmail message IDs
            label_names_or_ids: List of label names or IDs to assign

        Returns:
            Dictionary with success/failure counts and details
        """
        results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        # Resolve all label names/IDs to IDs first
        label_ids = []
        for label_name_or_id in label_names_or_ids:
            label_id = self._resolve_label_to_id(user_id, label_name_or_id)
            if label_id:
                label_ids.append(label_id)
            else:
                results['errors'].append(f"Could not resolve label: {label_name_or_id}")
                results['failed'] += 1

        if not label_ids:
            return results

        # Process each message
        for message_id in message_ids:
            try:
                gmail_client = self.get_gmail_client(user_id)
                if not gmail_client:
                    results['errors'].append(f"No Gmail client for message: {message_id}")
                    results['failed'] += 1
                    continue

                modify_body = {
                    'addLabelIds': label_ids
                }

                gmail_client.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body=modify_body
                ).execute()

                results['successful'] += 1
                logger.debug(f"Assigned {len(label_ids)} labels to message {message_id} for user: {user_id}")

            except Exception as e:
                results['errors'].append(f"Error processing message {message_id}: {str(e)}")
                results['failed'] += 1
                logger.error(f"Error assigning labels to message {message_id} for user {user_id}: {e}")

        logger.info(f"Label assignment complete for user {user_id}: {results['successful']} successful, {results['failed']} failed")
        return results

    def _resolve_label_to_id(self, user_id: str, label_name_or_id: str) -> Optional[str]:
        """
        Resolve a label name to its ID, or return the ID if already provided.

        Args:
            user_id: User identifier
            label_name_or_id: Label name or ID

        Returns:
            Label ID or None if not found
        """
        try:
            # First, try to get by name
            label = self.get_label_by_name(user_id, label_name_or_id)
            if label:
                return label['id']

            # If not found by name, assume it's already an ID and verify it exists
            label = self.get_label_by_id(user_id, label_name_or_id)
            if label:
                return label['id']

            logger.warning(f"Could not resolve label '{label_name_or_id}' for user: {user_id}")
            return None

        except Exception as e:
            logger.error(f"Error resolving label '{label_name_or_id}' for user {user_id}: {e}")
            return None

    def get_token_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a user's authentication token.

        Args:
            user_id: User identifier

        Returns:
            Token information dictionary or None if no token
        """
        return self.token_manager.get_token_info(user_id)

    def revoke_access(self, user_id: str) -> bool:
        """
        Revoke OAuth access for a user.

        Args:
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        return self.token_manager.revoke_and_delete_token(user_id)

    def is_authenticated(self, user_id: str) -> bool:
        """
        Check if a user is authenticated with valid credentials.

        Args:
            user_id: User identifier

        Returns:
            True if authenticated, False otherwise
        """
        credentials = self.token_manager.get_valid_credentials(user_id, self.scopes)
        return credentials is not None

    def cleanup_expired_tokens(self, max_age_days: int = 30) -> int:
        """
        Clean up expired tokens across all users.

        Args:
            max_age_days: Maximum age of expired tokens to keep

        Returns:
            Number of tokens cleaned up
        """
        return self.token_manager.cleanup_expired_tokens(max_age_days)

    def list_authenticated_users(self) -> list:
        """
        List all users with stored authentication tokens.

        Returns:
            List of user information dictionaries
        """
        return self.token_manager.list_user_tokens()

    def setup_watch(self, user_id: str, topic_name: str, label_ids: Optional[list] = None,
                   watch_duration_days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Set up Gmail watch for push notifications on specified labels.

        Args:
            user_id: User identifier
            topic_name: Full Pub/Sub topic name (e.g., 'projects/my-project/topics/my-topic')
            label_ids: List of label IDs to watch (default: all inbox messages)
            watch_duration_days: How long to watch in days (max 7)

        Returns:
            Watch response dictionary or None if error
        """
        try:
            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return None

            # Prepare watch request body
            watch_request = {
                'topicName': topic_name,
                'labelIds': label_ids or ['INBOX'],
                'labelFilterAction': 'include'
            }

            # Set expiration time (max 7 days from now)
            import datetime
            expiration_ms = int((datetime.datetime.now() +
                               datetime.timedelta(days=watch_duration_days)).timestamp() * 1000)
            watch_request['expireTime'] = f"{expiration_ms * 1000}"  # Convert to microseconds

            # Execute watch request
            result = gmail_client.users().watch(
                userId='me',
                body=watch_request
            ).execute()

            logger.info(f"Successfully set up Gmail watch for user {user_id}: "
                       f"historyId={result.get('historyId')}, expiration={result.get('expiration')}")
            return result

        except HttpError as e:
            logger.error(f"HTTP error setting up watch for user {user_id}: {e}")
            if e.resp.status == 403:
                logger.error("Missing pubsub scope or insufficient permissions. "
                           "Ensure gmail-api-push@system.gserviceaccount.com has publisher role.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error setting up watch for user {user_id}: {e}")
            return None

    def stop_watch(self, user_id: str) -> bool:
        """
        Stop Gmail watch for a user.

        Args:
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return False

            # Execute stop request
            result = gmail_client.users().stop(userId='me').execute()

            logger.info(f"Successfully stopped Gmail watch for user {user_id}")
            return True

        except HttpError as e:
            logger.error(f"HTTP error stopping watch for user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error stopping watch for user {user_id}: {e}")
            return False

    def get_watch_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current watch status for a user.

        Args:
            user_id: User identifier

        Returns:
            Watch status dictionary or None if no active watch
        """
        try:
            gmail_client = self.get_gmail_client(user_id)
            if not gmail_client:
                return None

            # Get user profile which includes watch information
            profile = gmail_client.users().getProfile(userId='me').execute()

            # Extract watch-related information
            watch_info = {}
            if 'historyId' in profile:
                watch_info['historyId'] = profile['historyId']
            if 'emailAddress' in profile:
                watch_info['emailAddress'] = profile['emailAddress']

            return watch_info if watch_info else None

        except HttpError as e:
            logger.error(f"HTTP error getting watch status for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting watch status for user {user_id}: {e}")
            return None

    def renew_watch(self, user_id: str, topic_name: str, label_ids: Optional[list] = None,
                   watch_duration_days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Renew Gmail watch by stopping existing watch and setting up a new one.

        Args:
            user_id: User identifier
            topic_name: Full Pub/Sub topic name
            label_ids: List of label IDs to watch
            watch_duration_days: How long to watch in days

        Returns:
            New watch response dictionary or None if error
        """
        try:
            # First, try to stop existing watch
            self.stop_watch(user_id)

            # Small delay to ensure stop is processed
            import time
            time.sleep(1)

            # Set up new watch
            return self.setup_watch(user_id, topic_name, label_ids, watch_duration_days)

        except Exception as e:
            logger.error(f"Error renewing watch for user {user_id}: {e}")
            return None

    def setup_watch_with_retry(self, user_id: str, topic_name: str, label_ids: Optional[list] = None,
                              watch_duration_days: int = 7, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Set up Gmail watch with automatic retry logic for transient failures.

        Args:
            user_id: User identifier
            topic_name: Full Pub/Sub topic name
            label_ids: List of label IDs to watch
            watch_duration_days: How long to watch in days
            max_retries: Maximum number of retry attempts

        Returns:
            Watch response dictionary or None if all retries failed
        """
        import time

        for attempt in range(max_retries + 1):
            try:
                result = self.setup_watch(user_id, topic_name, label_ids, watch_duration_days)
                if result:
                    return result

                if attempt < max_retries:
                    # Exponential backoff: wait 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Watch setup failed for user {user_id}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)

            except Exception as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Watch setup error for user {user_id}: {e}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Watch setup failed after {max_retries + 1} attempts for user {user_id}: {e}")

        return None


# Global service instance
_gmail_service = None

def get_gmail_service() -> GmailService:
    """Get the global Gmail service instance."""
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = GmailService()
    return _gmail_service


def create_gmail_service(
    client_secrets_file: Optional[str] = None,
    scopes: Optional[list] = None,
    redirect_uri: Optional[str] = None
) -> GmailService:
    """
    Create a new Gmail service instance with custom configuration.

    Args:
        client_secrets_file: Path to client_secret.json
        scopes: OAuth2 scopes
        redirect_uri: OAuth2 redirect URI

    Returns:
        Configured GmailService instance
    """
    return GmailService(
        client_secrets_file=client_secrets_file,
        scopes=scopes,
        redirect_uri=redirect_uri
    )

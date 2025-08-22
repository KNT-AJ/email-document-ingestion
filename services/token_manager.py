"""
Token Manager Service

This module handles OAuth token refresh, validation, and lifecycle management.
It automatically refreshes expired tokens and validates token scopes.
"""

import logging
import time
from typing import Optional, List
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from .token_storage import TokenStorageInterface, get_token_storage

logger = logging.getLogger(__name__)


class TokenManager:
    """
    Manages OAuth token lifecycle including refresh and validation.

    Handles automatic token refresh, scope validation, and provides
    convenient methods for token operations.
    """

    def __init__(self, token_storage: Optional[TokenStorageInterface] = None):
        """
        Initialize the token manager.

        Args:
            token_storage: Token storage implementation (uses default if None)
        """
        self.token_storage = token_storage or get_token_storage()

    def get_valid_credentials(self, user_id: str, required_scopes: Optional[List[str]] = None) -> Optional[Credentials]:
        """
        Get valid credentials for a user, refreshing if necessary.

        Args:
            user_id: User identifier
            required_scopes: List of required OAuth scopes

        Returns:
            Valid credentials if available, None otherwise
        """
        try:
            # Retrieve stored credentials
            credentials = self.token_storage.get_credentials(user_id)

            if not credentials:
                logger.debug(f"No stored credentials found for user: {user_id}")
                return None

            # Check if credentials are valid
            if not credentials.valid:
                logger.info(f"Credentials expired or invalid for user: {user_id}")

                # Try to refresh if possible
                if credentials.expired and credentials.refresh_token:
                    if self._refresh_credentials(user_id, credentials):
                        # Reload refreshed credentials
                        credentials = self.token_storage.get_credentials(user_id)
                        if not credentials:
                            return None
                    else:
                        logger.warning(f"Failed to refresh credentials for user: {user_id}")
                        return None
                else:
                    logger.warning(f"Cannot refresh credentials for user: {user_id} (no refresh token)")
                    return None

            # Validate scopes if required
            if required_scopes:
                if not self.validate_token_scopes(credentials, required_scopes):
                    logger.warning(f"Insufficient scopes for user: {user_id}")
                    return None

            logger.debug(f"Valid credentials retrieved for user: {user_id}")
            return credentials

        except Exception as e:
            logger.error(f"Error getting valid credentials for user {user_id}: {e}")
            return None

    def _refresh_credentials(self, user_id: str, credentials: Credentials) -> bool:
        """
        Attempt to refresh expired credentials.

        Args:
            user_id: User identifier
            credentials: Credentials to refresh

        Returns:
            True if refresh successful, False otherwise
        """
        try:
            logger.info(f"Attempting to refresh credentials for user: {user_id}")

            # Create a request object for refresh
            request = Request()

            # Refresh the credentials
            credentials.refresh(request)

            # Save the refreshed credentials
            success = self.token_storage.save_credentials(user_id, credentials)

            if success:
                logger.info(f"Successfully refreshed credentials for user: {user_id}")
                return True
            else:
                logger.error(f"Failed to save refreshed credentials for user: {user_id}")
                return False

        except RefreshError as e:
            logger.error(f"Refresh error for user {user_id}: {e}")
            # Token might be revoked or refresh token invalid
            self.token_storage.delete_credentials(user_id)
            return False
        except Exception as e:
            logger.error(f"Unexpected error refreshing credentials for user {user_id}: {e}")
            return False

    def validate_token_scopes(self, credentials: Credentials, required_scopes: List[str]) -> bool:
        """
        Validate that credentials have all required scopes.

        Args:
            credentials: OAuth2 credentials
            required_scopes: List of required scopes

        Returns:
            True if all required scopes are present, False otherwise
        """
        if not credentials.scopes:
            logger.warning("Credentials have no scopes")
            return False

        missing_scopes = []
        for scope in required_scopes:
            if scope not in credentials.scopes:
                missing_scopes.append(scope)

        if missing_scopes:
            logger.warning(f"Missing required scopes: {missing_scopes}")
            return False

        return True

    def is_token_expiring_soon(self, credentials: Credentials, buffer_minutes: int = 5) -> bool:
        """
        Check if token will expire soon.

        Args:
            credentials: OAuth2 credentials
            buffer_minutes: Buffer time in minutes before expiration

        Returns:
            True if token expires within buffer time, False otherwise
        """
        if not credentials.expiry:
            return False

        # Add buffer time to current time
        buffer_time = datetime.utcnow() + timedelta(minutes=buffer_minutes)
        return credentials.expiry <= buffer_time

    def get_token_info(self, user_id: str) -> Optional[dict]:
        """
        Get information about a user's token.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with token information, or None if no token
        """
        try:
            credentials = self.token_storage.get_credentials(user_id)

            if not credentials:
                return None

            return {
                'user_id': user_id,
                'has_token': True,
                'is_valid': credentials.valid,
                'is_expired': credentials.expired if credentials.expiry else False,
                'expiry': credentials.expiry.isoformat() if credentials.expiry else None,
                'scopes': credentials.scopes,
                'has_refresh_token': bool(credentials.refresh_token),
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id
            }

        except Exception as e:
            logger.error(f"Error getting token info for user {user_id}: {e}")
            return None

    def list_user_tokens(self) -> List[dict]:
        """
        Get information about all stored tokens.

        Returns:
            List of token information dictionaries
        """
        try:
            users = self.token_storage.list_users()
            tokens_info = []

            for user_id in users:
                token_info = self.get_token_info(user_id)
                if token_info:
                    tokens_info.append(token_info)

            return tokens_info

        except Exception as e:
            logger.error(f"Error listing user tokens: {e}")
            return []

    def revoke_and_delete_token(self, user_id: str) -> bool:
        """
        Revoke OAuth token and delete stored credentials.

        Args:
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            credentials = self.token_storage.get_credentials(user_id)

            if credentials and credentials.token:
                # Revoke the token via Google OAuth2 revoke endpoint
                import requests

                revoke_url = "https://oauth2.googleapis.com/revoke"
                response = requests.post(
                    revoke_url,
                    params={'token': credentials.token},
                    headers={'content-type': 'application/x-www-form-urlencoded'}
                )

                if response.status_code == 200:
                    logger.info(f"Successfully revoked token for user: {user_id}")
                else:
                    logger.warning(f"Failed to revoke token for user {user_id}: {response.status_code}")

            # Delete stored credentials regardless of revoke success
            success = self.token_storage.delete_credentials(user_id)

            if success:
                logger.info(f"Successfully deleted stored credentials for user: {user_id}")
            else:
                logger.error(f"Failed to delete stored credentials for user: {user_id}")

            return success

        except Exception as e:
            logger.error(f"Error revoking and deleting token for user {user_id}: {e}")
            return False

    def cleanup_expired_tokens(self, max_age_days: int = 30) -> int:
        """
        Clean up expired tokens older than specified days.

        Args:
            max_age_days: Maximum age of expired tokens to keep

        Returns:
            Number of tokens cleaned up
        """
        try:
            users = self.token_storage.list_users()
            cleaned_count = 0

            for user_id in users:
                credentials = self.token_storage.get_credentials(user_id)
                if not credentials:
                    continue

                # Check if token is expired and old
                if credentials.expiry:
                    days_expired = (datetime.utcnow() - credentials.expiry).days
                    if credentials.expired and days_expired > max_age_days:
                        logger.info(f"Cleaning up expired token for user {user_id} ({days_expired} days old)")
                        self.token_storage.delete_credentials(user_id)
                        cleaned_count += 1

            logger.info(f"Cleaned up {cleaned_count} expired tokens")
            return cleaned_count

        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
            return 0

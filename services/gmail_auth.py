"""
Gmail API Authentication Service

This module handles OAuth2 authentication flow for Gmail API using Google's official
Python client libraries. It provides secure authentication with state parameter
handling to prevent CSRF attacks.
"""

from typing import Tuple, Optional
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import secrets
import logging
import os
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class GmailAuthService:
    """
    OAuth2 authentication service for Gmail API.

    Handles the complete OAuth2 flow including authorization URL generation,
    authorization code exchange, and token management.
    """

    def __init__(self, client_secrets_file: str, scopes: list, redirect_uri: str):
        """
        Initialize the authentication service.

        Args:
            client_secrets_file: Path to the client_secret.json file
            scopes: List of OAuth2 scopes required
            redirect_uri: OAuth2 redirect URI for callback
        """
        self.client_secrets_file = client_secrets_file
        self.scopes = scopes
        self.redirect_uri = redirect_uri

        if not os.path.exists(client_secrets_file):
            logger.warning(f"Client secrets file not found: {client_secrets_file}")
            logger.info("This is expected in development - create client_secret.json manually")

    def get_authorization_url(self) -> Tuple[str, str]:
        """
        Generate the authorization URL for user consent.

        Returns:
            Tuple of (authorization_url, state_token)
        """
        try:
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri
            )

            # Generate a secure state token to prevent CSRF attacks
            state = secrets.token_urlsafe(16)

            authorization_url, _ = flow.authorization_url(
                access_type='offline',  # Request refresh token
                include_granted_scopes='true',
                state=state
            )

            logger.info(f"Generated authorization URL: {authorization_url}")
            return authorization_url, state

        except FileNotFoundError:
            logger.error(f"Client secrets file not found: {self.client_secrets_file}")
            raise
        except Exception as e:
            logger.error(f"Error generating authorization URL: {e}")
            raise

    def exchange_code(self, authorization_response: str, expected_state: str) -> Optional[Credentials]:
        """
        Exchange authorization code for access tokens.

        Args:
            authorization_response: Full callback URL with authorization code
            expected_state: Expected state token for CSRF protection

        Returns:
            Credentials object if successful, None if state mismatch or error
        """
        try:
            # Parse the authorization response URL
            parsed_url = urlparse(authorization_response)
            query_params = parse_qs(parsed_url.query)

            # Verify state parameter to prevent CSRF attacks
            received_state = query_params.get('state', [None])[0]
            if received_state != expected_state:
                logger.error("State parameter mismatch - possible CSRF attack")
                return None

            # Check for authorization code
            code = query_params.get('code', [None])[0]
            if not code:
                logger.error("No authorization code found in callback URL")
                return None

            # Exchange code for tokens
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=self.scopes,
                state=expected_state,
                redirect_uri=self.redirect_uri
            )

            flow.fetch_token(authorization_response=authorization_response)
            credentials = flow.credentials

            logger.info("Successfully exchanged authorization code for tokens")
            return credentials

        except Exception as e:
            logger.error(f"Error exchanging authorization code: {e}")
            return None

    def validate_redirect_uri(self, callback_url: str, expected_state: str) -> bool:
        """
        Validate that the callback URL contains the expected state parameter.

        Args:
            callback_url: The full callback URL
            expected_state: Expected state token

        Returns:
            True if valid, False otherwise
        """
        try:
            parsed_url = urlparse(callback_url)
            query_params = parse_qs(parsed_url.query)

            received_state = query_params.get('state', [None])[0]
            return received_state == expected_state

        except Exception as e:
            logger.error(f"Error validating redirect URI: {e}")
            return False

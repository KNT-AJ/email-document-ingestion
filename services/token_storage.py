"""
Secure Token Storage Service

This module provides secure storage and retrieval of OAuth tokens with encryption.
Supports multiple storage backends including file-based and database-based storage.
"""

import json
import os
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from datetime import datetime
from cryptography.fernet import Fernet, InvalidToken
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class TokenStorageInterface(ABC):
    """Abstract interface for token storage implementations."""

    @abstractmethod
    def save_credentials(self, user_id: str, credentials: Credentials) -> bool:
        """Save credentials for a user."""
        pass

    @abstractmethod
    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """Retrieve credentials for a user."""
        pass

    @abstractmethod
    def delete_credentials(self, user_id: str) -> bool:
        """Delete credentials for a user."""
        pass

    @abstractmethod
    def list_users(self) -> list:
        """List all users with stored credentials."""
        pass


class FileBasedTokenStorage(TokenStorageInterface):
    """
    File-based token storage with encryption.

    Stores tokens in encrypted JSON files on disk.
    Suitable for development and single-server deployments.
    """

    def __init__(self, storage_dir: str = ".tokens", encryption_key: Optional[bytes] = None):
        """
        Initialize file-based storage.

        Args:
            storage_dir: Directory to store token files
            encryption_key: Encryption key (if None, uses environment variable or generates one)
        """
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        # Get encryption key
        if encryption_key:
            self.encryption_key = encryption_key
        elif 'TOKEN_ENCRYPTION_KEY' in os.environ:
            self.encryption_key = os.environ['TOKEN_ENCRYPTION_KEY'].encode()
        else:
            logger.warning("No encryption key provided - generating one (not secure for production)")
            self.encryption_key = Fernet.generate_key()

        self.cipher_suite = Fernet(self.encryption_key)

    def credentials_to_dict(self, credentials: Credentials) -> Dict[str, Any]:
        """Convert Credentials object to dictionary."""
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None
        }

    def dict_to_credentials(self, credentials_dict: Dict[str, Any]) -> Credentials:
        """Convert dictionary to Credentials object."""
        # Handle expiry datetime
        expiry = None
        if credentials_dict.get('expiry'):
            try:
                expiry = datetime.fromisoformat(credentials_dict['expiry'])
            except ValueError:
                logger.warning("Invalid expiry format in stored credentials")

        return Credentials(
            token=credentials_dict['token'],
            refresh_token=credentials_dict['refresh_token'],
            token_uri=credentials_dict['token_uri'],
            client_id=credentials_dict['client_id'],
            client_secret=credentials_dict['client_secret'],
            scopes=credentials_dict['scopes'],
            expiry=expiry
        )

    def _get_token_file(self, user_id: str) -> str:
        """Get the file path for a user's token file."""
        # Sanitize user_id to prevent path traversal
        safe_user_id = "".join(c for c in user_id if c.isalnum() or c in ('-', '_')).rstrip()
        return os.path.join(self.storage_dir, f"{safe_user_id}.json")

    def save_credentials(self, user_id: str, credentials: Credentials) -> bool:
        """Save credentials to encrypted file."""
        try:
            creds_dict = self.credentials_to_dict(credentials)
            json_data = json.dumps(creds_dict)
            encrypted_data = self.cipher_suite.encrypt(json_data.encode())

            token_file = self._get_token_file(user_id)
            with open(token_file, 'wb') as f:
                f.write(encrypted_data)

            logger.info(f"Credentials saved for user: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving credentials for user {user_id}: {e}")
            return False

    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """Retrieve and decrypt credentials from file."""
        try:
            token_file = self._get_token_file(user_id)

            if not os.path.exists(token_file):
                logger.debug(f"No token file found for user: {user_id}")
                return None

            with open(token_file, 'rb') as f:
                encrypted_data = f.read()

            decrypted_data = self.cipher_suite.decrypt(encrypted_data).decode()
            creds_dict = json.loads(decrypted_data)

            credentials = self.dict_to_credentials(creds_dict)
            logger.debug(f"Credentials loaded for user: {user_id}")
            return credentials

        except (InvalidToken, json.JSONDecodeError) as e:
            logger.error(f"Error decrypting/parsing credentials for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading credentials for user {user_id}: {e}")
            return None

    def delete_credentials(self, user_id: str) -> bool:
        """Delete credentials file."""
        try:
            token_file = self._get_token_file(user_id)

            if os.path.exists(token_file):
                os.remove(token_file)
                logger.info(f"Credentials deleted for user: {user_id}")
                return True
            else:
                logger.debug(f"No token file to delete for user: {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error deleting credentials for user {user_id}: {e}")
            return False

    def list_users(self) -> list:
        """List all users with stored token files."""
        try:
            users = []
            if os.path.exists(self.storage_dir):
                for filename in os.listdir(self.storage_dir):
                    if filename.endswith('.json'):
                        user_id = filename[:-5]  # Remove .json extension
                        users.append(user_id)
            return users

        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []


class DatabaseTokenStorage(TokenStorageInterface):
    """
    Database-based token storage with encryption.

    Stores tokens in a database table with encryption.
    Suitable for production deployments and multi-server setups.
    """

    def __init__(self, db_session_provider, encryption_key: Optional[bytes] = None):
        """
        Initialize database storage.

        Args:
            db_session_provider: Function that returns a database session
            encryption_key: Encryption key for tokens
        """
        self.get_session = db_session_provider

        # Get encryption key
        if encryption_key:
            self.encryption_key = encryption_key
        elif 'TOKEN_ENCRYPTION_KEY' in os.environ:
            self.encryption_key = os.environ['TOKEN_ENCRYPTION_KEY'].encode()
        else:
            logger.warning("No encryption key provided - generating one (not secure for production)")
            self.encryption_key = Fernet.generate_key()

        self.cipher_suite = Fernet(self.encryption_key)

    def save_credentials(self, user_id: str, credentials: Credentials) -> bool:
        """Save credentials to database."""
        try:
            # This is a placeholder implementation
            # In a real implementation, you would:
            # 1. Define a database model for storing encrypted tokens
            # 2. Use the session to save/update the record
            logger.warning("DatabaseTokenStorage is not fully implemented - use FileBasedTokenStorage")
            return False

        except Exception as e:
            logger.error(f"Error saving credentials to database for user {user_id}: {e}")
            return False

    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """Retrieve credentials from database."""
        logger.warning("DatabaseTokenStorage is not fully implemented - use FileBasedTokenStorage")
        return None

    def delete_credentials(self, user_id: str) -> bool:
        """Delete credentials from database."""
        logger.warning("DatabaseTokenStorage is not fully implemented - use FileBasedTokenStorage")
        return False

    def list_users(self) -> list:
        """List all users with stored credentials."""
        logger.warning("DatabaseTokenStorage is not fully implemented - use FileBasedTokenStorage")
        return []


def create_token_storage(storage_type: str = "file", **kwargs) -> TokenStorageInterface:
    """
    Factory function to create token storage instance.

    Args:
        storage_type: 'file' or 'database'
        **kwargs: Additional arguments for storage initialization

    Returns:
        TokenStorageInterface implementation
    """
    if storage_type == "file":
        return FileBasedTokenStorage(**kwargs)
    elif storage_type == "database":
        return DatabaseTokenStorage(**kwargs)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


# Default token storage instance
_default_storage = None

def get_token_storage() -> TokenStorageInterface:
    """Get the default token storage instance."""
    global _default_storage
    if _default_storage is None:
        _default_storage = create_token_storage(
            storage_type=os.environ.get('TOKEN_STORAGE_TYPE', 'file'),
            storage_dir=os.environ.get('TOKEN_STORAGE_DIR', '.tokens')
        )
    return _default_storage

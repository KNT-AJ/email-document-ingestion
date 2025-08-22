"""
Test Gmail Authentication Service

Basic tests to verify the Gmail authentication service components
can be imported and initialized correctly.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch

# Test imports
def test_imports():
    """Test that all Gmail auth modules can be imported."""
    try:
        from services.gmail_auth import GmailAuthService
        from services.token_storage import FileBasedTokenStorage, get_token_storage
        from services.token_manager import TokenManager
        from services.gmail_service import GmailService, get_gmail_service
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import Gmail auth modules: {e}")

def test_gmail_auth_service_initialization():
    """Test GmailAuthService initialization."""
    from services.gmail_auth import GmailAuthService

    # Test with non-existent client secrets file (expected in development)
    auth_service = GmailAuthService(
        client_secrets_file="non_existent.json",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        redirect_uri="http://localhost:8000/callback"
    )

    assert auth_service.client_secrets_file == "non_existent.json"
    assert len(auth_service.scopes) == 1
    assert auth_service.redirect_uri == "http://localhost:8000/callback"

def test_file_based_token_storage():
    """Test FileBasedTokenStorage initialization and basic operations."""
    from services.token_storage import FileBasedTokenStorage
    from google.oauth2.credentials import Credentials

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileBasedTokenStorage(
            storage_dir=temp_dir,
            encryption_key=b'test_key_12345678901234567890123456789012'  # 32 bytes
        )

        # Test basic operations with mock credentials
        mock_creds = Credentials(
            token="test_token",
            refresh_token="test_refresh_token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"]
        )

        # Test save and retrieve
        success = storage.save_credentials("test_user", mock_creds)
        assert success is True

        retrieved_creds = storage.get_credentials("test_user")
        assert retrieved_creds is not None
        assert retrieved_creds.token == "test_token"
        assert retrieved_creds.client_id == "test_client_id"

        # Test list users
        users = storage.list_users()
        assert "test_user" in users

        # Test delete
        success = storage.delete_credentials("test_user")
        assert success is True

        # Verify deleted
        retrieved_creds = storage.get_credentials("test_user")
        assert retrieved_creds is None

def test_token_manager():
    """Test TokenManager initialization."""
    from services.token_manager import TokenManager
    from services.token_storage import FileBasedTokenStorage

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileBasedTokenStorage(
            storage_dir=temp_dir,
            encryption_key=b'test_key_12345678901234567890123456789012'
        )

        manager = TokenManager(token_storage=storage)
        assert manager.token_storage is storage

def test_gmail_service():
    """Test GmailService initialization."""
    from services.gmail_service import GmailService

    # Test with default configuration
    service = GmailService()

    # Test that components are initialized
    assert service.auth_service is not None
    assert service.token_manager is not None
    assert service.token_storage is not None

    # Test with custom configuration
    custom_service = GmailService(
        client_secrets_file="custom_secrets.json",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        redirect_uri="http://localhost:5000/callback"
    )

    assert custom_service.client_secrets_file == "custom_secrets.json"
    assert custom_service.redirect_uri == "http://localhost:5000/callback"

@patch.dict(os.environ, {
    'GOOGLE_CLIENT_SECRETS_FILE': 'test_secrets.json',
    'GOOGLE_REDIRECT_URI': 'http://localhost:3000/callback'
})
def test_gmail_service_with_env_vars():
    """Test GmailService with environment variables."""
    from services.gmail_service import GmailService

    service = GmailService()

    assert service.client_secrets_file == 'test_secrets.json'
    assert service.redirect_uri == 'http://localhost:3000/callback'

def test_token_validation():
    """Test token validation functions."""
    from services.token_manager import TokenManager
    from services.token_storage import FileBasedTokenStorage
    from google.oauth2.credentials import Credentials
    import datetime

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileBasedTokenStorage(
            storage_dir=temp_dir,
            encryption_key=b'test_key_12345678901234567890123456789012'
        )

        manager = TokenManager(token_storage=storage)

        # Test with mock credentials
        mock_creds = Credentials(
            token="test_token",
            refresh_token="test_refresh_token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"]
        )

        # Test scope validation
        valid_scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        assert manager.validate_token_scopes(mock_creds, valid_scopes) is True

        invalid_scopes = ["https://www.googleapis.com/auth/gmail.send"]
        assert manager.validate_token_scopes(mock_creds, invalid_scopes) is False

        # Test expiry checking
        mock_creds.expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        assert manager.is_token_expiring_soon(mock_creds, buffer_minutes=5) is False

        mock_creds.expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=2)
        assert manager.is_token_expiring_soon(mock_creds, buffer_minutes=5) is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

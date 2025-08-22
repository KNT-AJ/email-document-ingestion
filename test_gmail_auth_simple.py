#!/usr/bin/env python3
"""
Simple test script for Gmail Authentication Service

This script tests that all Gmail authentication components can be imported
and initialized without errors.
"""

import sys
import os
import tempfile

# Add the project root to Python path
sys.path.insert(0, '/Users/ajdavis/GitHub/data_ingest')

def test_imports():
    """Test that all Gmail auth modules can be imported."""
    print("Testing imports...")

    try:
        from services.gmail_auth import GmailAuthService
        print("✅ GmailAuthService imported successfully")

        from services.token_storage import FileBasedTokenStorage, get_token_storage
        print("✅ Token storage imported successfully")

        from services.token_manager import TokenManager
        print("✅ TokenManager imported successfully")

        from services.gmail_service import GmailService, get_gmail_service
        print("✅ GmailService imported successfully")

        return True

    except ImportError as e:
        print(f"❌ Failed to import Gmail auth modules: {e}")
        return False

def test_initialization():
    """Test basic initialization of services."""
    print("\nTesting initialization...")

    try:
        from services.gmail_auth import GmailAuthService

        # Test with non-existent client secrets file (expected in development)
        auth_service = GmailAuthService(
            client_secrets_file="non_existent.json",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            redirect_uri="http://localhost:8000/callback"
        )
        print("✅ GmailAuthService initialized successfully")

        # Test token storage
        from services.token_storage import FileBasedTokenStorage
        from cryptography.fernet import Fernet

        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate a proper Fernet key
            encryption_key = Fernet.generate_key()
            storage = FileBasedTokenStorage(
                storage_dir=temp_dir,
                encryption_key=encryption_key
            )
            print("✅ FileBasedTokenStorage initialized successfully")

        # Test token manager
        from services.token_manager import TokenManager
        manager = TokenManager(token_storage=storage)
        print("✅ TokenManager initialized successfully")

        # Test Gmail service
        from services.gmail_service import GmailService
        service = GmailService()
        print("✅ GmailService initialized successfully")

        return True

    except Exception as e:
        print(f"❌ Initialization test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🔐 Gmail Authentication Service Test")
    print("=" * 50)

    success = True

    # Test imports
    if not test_imports():
        success = False

    # Test initialization
    if not test_initialization():
        success = False

    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Gmail authentication service is ready.")
        print("\nNext steps:")
        print("1. Set up Google Cloud Project and OAuth credentials")
        print("2. Copy client_secret.example.json to client_secret.json")
        print("3. Configure environment variables (see env.example)")
        print("4. Run examples/gmail_auth_example.py for a demo")
    else:
        print("❌ Some tests failed. Please check the error messages above.")

    return 0 if success else 1

if __name__ == "__main__":
    exit(main())

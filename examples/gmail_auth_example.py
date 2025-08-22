#!/usr/bin/env python3
"""
Gmail Authentication Example

This example demonstrates how to use the Gmail authentication service
to authenticate users and access their Gmail data.
"""

import os
import logging
from services.gmail_service import GmailService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Gmail service
gmail_service = GmailService()

def authenticate_user(user_id: str):
    """Authenticate a user with Gmail OAuth2 flow."""
    print(f"\n=== Authenticating User: {user_id} ===")

    # Check if user is already authenticated
    if gmail_service.is_authenticated(user_id):
        print(f"✅ User {user_id} is already authenticated!")
        return True

    # Get authorization URL
    try:
        auth_url, state = gmail_service.get_authorization_url(user_id)

        if not auth_url:
            print(f"❌ Failed to generate authorization URL for {user_id}")
            return False

        print(f"🔗 Please visit this URL to authorize the application:")
        print(f"{auth_url}")
        print(f"\n📝 After authorization, you'll be redirected to your callback URL.")
        print(f"   Copy the full callback URL and paste it here:")

        callback_url = input("\nPaste the callback URL: ").strip()

        # Handle the OAuth callback
        success = gmail_service.handle_oauth_callback(callback_url, state, user_id)

        if success:
            print(f"✅ Successfully authenticated user {user_id}!")
            return True
        else:
            print(f"❌ Authentication failed for user {user_id}")
            return False

    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        return False

def show_user_info(user_id: str):
    """Show information about an authenticated user."""
    print(f"\n=== User Information: {user_id} ===")

    # Get token information
    token_info = gmail_service.get_token_info(user_id)
    if token_info:
        print(f"📧 Email: {token_info.get('client_id', 'N/A')}")
        print(f"✅ Has valid token: {token_info.get('is_valid', False)}")
        print(f"🔄 Has refresh token: {token_info.get('has_refresh_token', False)}")
        print(f"📅 Expires: {token_info.get('expiry', 'N/A')}")
        print(f"🔑 Scopes: {', '.join(token_info.get('scopes', []))}")
    else:
        print("❌ No token information available")

def access_gmail_api(user_id: str):
    """Access Gmail API for an authenticated user."""
    print(f"\n=== Accessing Gmail API: {user_id} ===")

    try:
        # Get Gmail client
        gmail_client = gmail_service.get_gmail_client(user_id)

        if not gmail_client:
            print(f"❌ Could not create Gmail client for {user_id}")
            return

        # Get user profile
        profile = gmail_service.get_user_profile(user_id)
        if profile:
            print(f"📧 Email Address: {profile.get('emailAddress', 'N/A')}")
            print(f"📨 Total Messages: {profile.get('messagesTotal', 'N/A')}")
            print(f"📬 Unread Messages: {profile.get('threadsUnread', 'N/A')}")
        else:
            print("❌ Could not retrieve user profile")

        # List labels
        labels = gmail_service.list_labels(user_id)
        if labels:
            print(f"\n📋 Available Labels ({len(labels)}):")
            for label in labels[:10]:  # Show first 10 labels
                print(f"  - {label.get('name', 'N/A')} ({label.get('id', 'N/A')})")
            if len(labels) > 10:
                print(f"  ... and {len(labels) - 10} more labels")
        else:
            print("❌ Could not retrieve labels")

    except Exception as e:
        print(f"❌ Error accessing Gmail API: {e}")

def main():
    """Main example function."""
    print("🔐 Gmail Authentication Service Example")
    print("=" * 50)

    # Example user ID
    user_id = input("Enter user ID (or press Enter for 'test_user'): ").strip()
    if not user_id:
        user_id = "test_user"

    # Step 1: Authenticate user
    if not authenticate_user(user_id):
        print("💡 Make sure you have:")
        print("   1. Created a Google Cloud Project")
        print("   2. Enabled the Gmail API")
        print("   3. Downloaded client_secret.json")
        print("   4. Set GOOGLE_CLIENT_SECRETS_FILE in .env")
        return

    # Step 2: Show user information
    show_user_info(user_id)

    # Step 3: Access Gmail API
    access_gmail_api(user_id)

    print(f"\n🎉 Example completed for user: {user_id}")

if __name__ == "__main__":
    main()

# Gmail API Authentication Service

This service provides complete OAuth2 authentication for Gmail API, including secure token storage, automatic refresh, and API client management.

## Features

- ✅ Complete OAuth2 flow implementation
- 🔐 Secure token storage with encryption
- 🔄 Automatic token refresh
- 🛡️ CSRF protection with state tokens
- 📊 Token lifecycle management
- 🔍 Scope validation
- 📝 Comprehensive logging
- 🧪 Production-ready error handling

## Components

### 1. GmailAuthService (`gmail_auth.py`)
Handles the OAuth2 authorization flow with Google.

**Key Methods:**
- `get_authorization_url()` - Generate OAuth2 authorization URL
- `exchange_code()` - Exchange authorization code for tokens
- `validate_redirect_uri()` - Validate callback URLs

### 2. TokenStorage (`token_storage.py`)
Secure storage for OAuth tokens with encryption.

**Storage Types:**
- `FileBasedTokenStorage` - Encrypted files (recommended for development)
- `DatabaseTokenStorage` - Database storage (for production)

### 3. TokenManager (`token_manager.py`)
Manages token lifecycle including refresh and validation.

**Key Methods:**
- `get_valid_credentials()` - Get valid credentials with auto-refresh
- `validate_token_scopes()` - Check if token has required scopes
- `revoke_and_delete_token()` - Revoke OAuth access
- `cleanup_expired_tokens()` - Clean up old tokens

### 4. GmailService (`gmail_service.py`)
Main service that integrates all components.

**Key Methods:**
- `get_authorization_url()` - Start OAuth flow
- `handle_oauth_callback()` - Complete OAuth flow
- `get_gmail_client()` - Get authenticated API client
- `get_user_profile()` - Get Gmail user profile
- `list_labels()` - List Gmail labels

## Setup Instructions

### 1. Google Cloud Project Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API" and enable it
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Choose "Web application" as application type
   - Add authorized redirect URIs (e.g., `http://localhost:8000/auth/callback`)
   - Download the `client_secret.json` file

### 2. Environment Configuration

Copy `env.example` to `.env` and configure:

```bash
# Required: Path to your client_secret.json
GOOGLE_CLIENT_SECRETS_FILE=client_secret.json

# Required: Your OAuth2 redirect URI
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Optional: Token storage configuration
TOKEN_STORAGE_TYPE=file
TOKEN_STORAGE_DIR=.tokens
TOKEN_ENCRYPTION_KEY=your-secure-32-byte-key
```

### 3. Generate Encryption Key

For production, generate a secure encryption key:

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Use this in TOKEN_ENCRYPTION_KEY
```

### 4. Install Dependencies

```bash
pip install google-auth google-auth-oauthlib google-api-python-client cryptography
```

## Usage Examples

### Basic Authentication Flow

```python
from services.gmail_service import GmailService

# Initialize service
gmail_service = GmailService()

# Start OAuth flow
user_id = "user123"
auth_url, state = gmail_service.get_authorization_url(user_id)
print(f"Visit: {auth_url}")

# After user authorizes, handle callback
callback_url = "http://localhost:8000/auth/callback?code=..."  # Full URL
success = gmail_service.handle_oauth_callback(callback_url, state, user_id)

if success:
    print("Authentication successful!")
```

### Access Gmail API

```python
# Get authenticated Gmail client
gmail_client = gmail_service.get_gmail_client(user_id)

if gmail_client:
    # Get user profile
    profile = gmail_client.users().getProfile(userId='me').execute()
    print(f"Email: {profile['emailAddress']}")

    # List labels
    labels = gmail_client.users().labels().list(userId='me').execute()
    print(f"Labels: {labels}")
```

### Token Management

```python
# Check if user is authenticated
is_auth = gmail_service.is_authenticated(user_id)

# Get token information
token_info = gmail_service.get_token_info(user_id)

# Revoke access
gmail_service.revoke_access(user_id)

# Clean up expired tokens
cleaned = gmail_service.cleanup_expired_tokens(max_age_days=30)
```

## Security Considerations

### 1. Token Storage Security
- Tokens are encrypted using Fernet (AES-256)
- Use strong encryption keys in production
- Store encryption keys securely (environment variables, secret managers)
- Consider database storage for multi-server deployments

### 2. OAuth2 Security
- CSRF protection using state tokens
- Validate redirect URIs
- Use HTTPS in production
- Implement proper session management

### 3. Scope Management
- Request minimal required scopes
- Validate scopes before API calls
- Regularly audit authorized scopes

## Error Handling

The service includes comprehensive error handling for:

- **Authentication Errors**: Invalid credentials, revoked tokens
- **Network Errors**: Connection timeouts, API rate limits
- **Token Errors**: Expired tokens, invalid refresh tokens
- **Storage Errors**: File system errors, encryption failures

All errors are logged with appropriate context for debugging.

## Production Deployment

For production deployment:

1. **Use Database Storage**: Switch to `DatabaseTokenStorage` for multi-server setups
2. **Enable HTTPS**: Ensure all OAuth redirects use HTTPS
3. **Secure Key Management**: Use proper secret management systems
4. **Monitor Token Usage**: Implement logging and monitoring for token operations
5. **Regular Cleanup**: Set up automated cleanup of expired tokens

## Testing

Run the example script to test the authentication flow:

```bash
python examples/gmail_auth_example.py
```

## API Reference

For detailed API documentation, see the docstrings in each service file.

## Troubleshooting

### Common Issues

1. **"Client secrets file not found"**
   - Ensure `client_secret.json` exists and `GOOGLE_CLIENT_SECRETS_FILE` is set

2. **"Invalid client" errors**
   - Check that OAuth credentials are properly configured in Google Cloud Console

3. **Token refresh failures**
   - Verify the refresh token is valid and not revoked
   - Check network connectivity to Google's OAuth endpoints

4. **Scope validation errors**
   - Ensure the token has all required scopes
   - Re-authenticate if additional scopes are needed

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## Contributing

When extending this service:

1. Maintain security best practices
2. Add comprehensive error handling
3. Include unit tests for new functionality
4. Update documentation for API changes
5. Follow existing code patterns and style

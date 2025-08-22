"""Test script for Gmail push notification webhook."""

import json
import base64
import asyncio
from datetime import datetime, timezone
import httpx
import jwt

# Sample Gmail push notification data
SAMPLE_GMAIL_NOTIFICATION = {
    "emailAddress": "test@example.com",
    "historyId": "1234567890"
}

# Sample Pub/Sub message structure
def create_sample_pubsub_message(gmail_data: dict) -> dict:
    """Create a sample Pub/Sub message with Gmail notification data."""

    # Encode the Gmail data as base64
    data_bytes = json.dumps(gmail_data).encode('utf-8')
    encoded_data = base64.b64encode(data_bytes).decode('utf-8')

    return {
        "message": {
            "data": encoded_data,
            "messageId": "test-message-123",
            "publishTime": datetime.now(timezone.utc).isoformat(),
            "attributes": {
                "source": "gmail"
            }
        },
        "subscription": "projects/test-project/subscriptions/gmail-push"
    }

def create_sample_jwt_token(audience: str = "https://example.com/api/gmail/push") -> str:
    """Create a sample JWT token for testing (without signature verification)."""

    payload = {
        "iss": "https://accounts.google.com",
        "aud": audience,
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,  # 1 hour from now
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "sub": "pubsub@system.gserviceaccount.com"
    }

    # Create unsigned token (for testing only)
    header = {"alg": "none", "typ": "JWT"}
    import base64

    # Encode header
    header_b64 = base64.b64encode(json.dumps(header).encode()).decode().rstrip('=')

    # Encode payload
    payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode().rstrip('=')

    # Create unsigned token
    token = f"{header_b64}.{payload_b64}."

    return token

async def test_gmail_webhook(
    webhook_url: str = "http://localhost:8000/api/gmail/push",
    audience: str = "https://example.com/api/gmail/push"
):
    """Test the Gmail webhook endpoint with sample data."""

    print(f"Testing Gmail webhook at: {webhook_url}")

    # Create sample data
    gmail_data = SAMPLE_GMAIL_NOTIFICATION.copy()
    pubsub_message = create_sample_pubsub_message(gmail_data)
    jwt_token = create_sample_jwt_token(audience)

    # Set up headers
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"Sending test request with JWT token...")
            print(f"JWT Payload: {json.dumps(jwt.decode(jwt_token, options={'verify_signature': False}), indent=2)}")
            print(f"Pub/Sub Message: {json.dumps(pubsub_message, indent=2)}")

            # Send the request
            response = await client.post(
                webhook_url,
                json=pubsub_message,
                headers=headers
            )

            print(f"\nResponse Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")

            if response.status_code == 200:
                response_data = response.json()
                print(f"Response Body: {json.dumps(response_data, indent=2)}")
                print("✅ Webhook test PASSED")
            else:
                print(f"❌ Webhook test FAILED with status {response.status_code}")
                print(f"Response Body: {response.text}")

    except httpx.RequestError as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

async def test_webhook_health(
    health_url: str = "http://localhost:8000/api/gmail/webhook/health"
):
    """Test the webhook health endpoint."""

    print(f"\nTesting webhook health at: {health_url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(health_url)

            print(f"Health Response Status: {response.status_code}")

            if response.status_code == 200:
                health_data = response.json()
                print(f"Health Response: {json.dumps(health_data, indent=2)}")
                print("✅ Health check PASSED")
            else:
                print(f"❌ Health check FAILED with status {response.status_code}")
                print(f"Response Body: {response.text}")

    except httpx.RequestError as e:
        print(f"❌ Health check request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error during health check: {e}")

async def test_invalid_jwt():
    """Test webhook with invalid JWT token."""

    print("\nTesting with invalid JWT token...")

    webhook_url = "http://localhost:8000/api/gmail/push"
    gmail_data = SAMPLE_GMAIL_NOTIFICATION.copy()
    pubsub_message = create_sample_pubsub_message(gmail_data)

    # Invalid JWT token
    headers = {
        "Authorization": "Bearer invalid.jwt.token",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=pubsub_message,
                headers=headers
            )

            print(f"Invalid JWT Response Status: {response.status_code}")

            if response.status_code == 401:
                print("✅ Invalid JWT test PASSED (correctly rejected)")
            else:
                print(f"❌ Invalid JWT test FAILED - expected 401, got {response.status_code}")

    except Exception as e:
        print(f"❌ Error testing invalid JWT: {e}")

async def main():
    """Run all webhook tests."""

    print("🚀 Starting Gmail Webhook Tests")
    print("=" * 50)

    # Test webhook health first
    await test_webhook_health()

    # Test main webhook functionality
    await test_gmail_webhook()

    # Test invalid JWT handling
    await test_invalid_jwt()

    print("\n" + "=" * 50)
    print("🏁 Webhook Tests Complete")

if __name__ == "__main__":
    asyncio.run(main())

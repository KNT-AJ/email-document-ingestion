# Gmail Push Notification Webhook

This document describes the implementation of the Gmail push notification webhook endpoint for the Email & Document Ingestion System.

## Overview

The Gmail push notification webhook allows the system to receive real-time notifications when new emails arrive in monitored Gmail accounts. This enables efficient email processing without the need for continuous polling.

## Implementation Details

### Webhook Endpoint

- **URL**: `/api/gmail/push`
- **Method**: `POST`
- **Authentication**: JWT token in Authorization header
- **Content-Type**: `application/json`

### Request Format

The webhook expects a Google Pub/Sub push message format:

```json
{
  "message": {
    "data": "base64-encoded-gmail-notification",
    "messageId": "pubsub-message-id",
    "publishTime": "2024-01-01T00:00:00Z",
    "attributes": {
      "source": "gmail"
    }
  },
  "subscription": "projects/project-id/subscriptions/subscription-name"
}
```

### Gmail Notification Data

The `data` field contains base64-encoded JSON with Gmail notification details:

```json
{
  "emailAddress": "user@example.com",
  "historyId": "1234567890"
}
```

### JWT Token Validation

The webhook validates JWT tokens from Google Pub/Sub:

- **Issuer**: `https://accounts.google.com`
- **Audience**: Configurable via `PUBSUB_AUDIENCE` environment variable
- **Algorithm**: ES256 (production) or none (testing)
- **Expiration**: Standard JWT expiration validation

### Processing Flow

1. **Authentication**: Validate JWT token from Authorization header
2. **Message Parsing**: Decode and parse Pub/Sub message format
3. **Data Extraction**: Extract Gmail notification data (email, historyId)
4. **User Mapping**: Map email address to user ID
5. **Task Queueing**: Enqueue background task for email synchronization
6. **Response**: Return success response to Pub/Sub

### Environment Variables

Add these to your `.env` file:

```bash
# Gmail Push Notification Settings
PUBSUB_AUDIENCE=https://your-domain.com/api/gmail/push
```

### Testing

Use the provided test script to verify webhook functionality:

```bash
python test_gmail_webhook.py
```

The test script includes:
- Sample Pub/Sub message generation
- JWT token creation (for testing)
- Webhook endpoint testing
- Health check verification
- Invalid token testing

### Health Check

A health check endpoint is available at `/api/gmail/webhook/health`:

```bash
curl http://localhost:8000/api/gmail/webhook/health
```

### Error Handling

The webhook implements comprehensive error handling:

- **401 Unauthorized**: Invalid or missing JWT token
- **400 Bad Request**: Invalid message format or Gmail data
- **500 Internal Server Error**: Unexpected server errors
- **Background Processing**: Failed sync tasks are logged but don't break the webhook response

### Security Considerations

1. **HTTPS Required**: Webhook endpoint must be served over HTTPS
2. **JWT Validation**: Always validate JWT tokens in production
3. **Rate Limiting**: Implement rate limiting to prevent abuse
4. **Input Validation**: Validate all incoming data structures
5. **Logging**: Log all webhook requests for debugging and monitoring

### Production Deployment

For production deployment:

1. Set up proper SSL/TLS certificates
2. Configure Google Cloud Pub/Sub subscription with correct push endpoint
3. Set `PUBSUB_AUDIENCE` to your production domain
4. Implement proper JWT signature verification with Google's public keys
5. Set up monitoring and alerting for webhook failures
6. Configure proper logging and log retention

### Integration with Gmail Watch

This webhook works in conjunction with the Gmail watch setup:

1. Use `GmailWatchConfig` to set up Pub/Sub topics and subscriptions
2. Configure push endpoint to point to this webhook
3. Grant appropriate permissions to Gmail service account
4. Start Gmail watch for specific labels or entire inbox

### Monitoring and Debugging

The webhook provides detailed logging:

- Request authentication details
- Message parsing results
- User mapping information
- Task queueing status
- Error conditions and stack traces

Check application logs for webhook activity and troubleshoot issues using the provided test scripts.

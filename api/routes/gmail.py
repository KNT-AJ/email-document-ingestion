"""Gmail API routes for push notifications and webhooks."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import jwt
import json
import logging
from datetime import datetime, timezone

from config import get_settings
from utils.logging import get_logger
from workers.tasks.email_ingestion import sync_gmail_messages

router = APIRouter()
logger = get_logger("api.gmail")
settings = get_settings()


class GmailPushNotification(BaseModel):
    """Model for Gmail push notification from Pub/Sub."""

    message: Dict[str, Any]
    subscription: str


class GmailNotificationData(BaseModel):
    """Model for Gmail notification data."""

    emailAddress: str
    historyId: str


class PubSubMessage(BaseModel):
    """Model for Pub/Sub message structure."""

    data: str
    messageId: str
    publishTime: str
    attributes: Optional[Dict[str, str]] = None


@router.post("/gmail/push")
async def gmail_push_webhook(
    request: Request,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Webhook endpoint for Gmail push notifications via Google Pub/Sub.

    This endpoint receives push notifications from Gmail when new emails arrive,
    validates the JWT token, extracts the historyId, and triggers email sync.

    The endpoint expects a Pub/Sub push message with JWT authentication.
    """

    try:
        logger.info("Received Gmail push notification", endpoint="/gmail/push")

        # Get the authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            raise HTTPException(status_code=401, detail="Missing or invalid authorization")

        # Extract JWT token
        jwt_token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate JWT token
        try:
            payload = _validate_pubsub_jwt(jwt_token)
            logger.debug("JWT token validated successfully", audience=payload.get("aud"))
        except Exception as e:
            logger.error(f"JWT validation failed: {e}")
            raise HTTPException(status_code=401, detail=f"JWT validation failed: {str(e)}")

        # Parse the request body as Pub/Sub message
        try:
            body = await request.json()
            pubsub_message = PubSubMessage(**body.get("message", {}))

            # Decode the base64 data
            import base64
            decoded_data = base64.b64decode(pubsub_message.data).decode('utf-8')
            gmail_data = json.loads(decoded_data)

            logger.info(
                "Parsed Pub/Sub message",
                message_id=pubsub_message.messageId,
                publish_time=pubsub_message.publishTime,
                history_id=gmail_data.get("historyId")
            )

        except Exception as e:
            logger.error(f"Failed to parse Pub/Sub message: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid message format: {str(e)}")

        # Extract Gmail notification data
        try:
            notification_data = GmailNotificationData(**gmail_data)
            logger.info(
                "Extracted Gmail notification data",
                email=notification_data.emailAddress,
                history_id=notification_data.historyId
            )
        except Exception as e:
            logger.error(f"Failed to extract Gmail data: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid Gmail notification format: {str(e)}")

        # Extract user ID from email address (this is a simple mapping)
        # In a real implementation, you might need a more sophisticated user lookup
        user_id = _extract_user_id_from_email(notification_data.emailAddress)

        if not user_id:
            logger.warning(f"Could not extract user ID from email: {notification_data.emailAddress}")
            raise HTTPException(status_code=400, detail="Invalid email address format")

        # Queue the sync task in background
        try:
            background_tasks.add_task(
                _process_gmail_notification,
                user_id=user_id,
                history_id=notification_data.historyId,
                email_address=notification_data.emailAddress
            )

            logger.info(
                "Queued Gmail sync task",
                user_id=user_id,
                history_id=notification_data.historyId,
                email_address=notification_data.emailAddress
            )

        except Exception as e:
            logger.error(f"Failed to queue sync task: {e}")
            # Don't raise HTTP error here as the webhook should return 200
            # The sync failure will be handled by the background task

        # Return success response to Pub/Sub
        return {
            "status": "success",
            "message": "Notification processed successfully",
            "user_id": user_id,
            "history_id": notification_data.historyId,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Gmail push webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


def _validate_pubsub_jwt(jwt_token: str) -> Dict[str, Any]:
    """
    Validate JWT token from Google Pub/Sub.

    Args:
        jwt_token: The JWT token from Authorization header

    Returns:
        Decoded JWT payload

    Raises:
        Exception: If JWT validation fails
    """
    try:
        # Google Pub/Sub uses ES256 algorithm with Google's public keys
        # In production, you should fetch Google's public keys from:
        # https://www.googleapis.com/robot/v1/metadata/x509/cloud-pubsub@system.gserviceaccount.com

        # For now, we'll do basic validation without signature verification
        # In production, implement proper JWT signature verification

        header = jwt.get_unverified_header(jwt_token)
        payload = jwt.decode(jwt_token, options={"verify_signature": False})

        # Basic validation
        if payload.get("aud") != settings.PUBSUB_AUDIENCE:
            raise Exception(f"Invalid audience: {payload.get('aud')}")

        if payload.get("iss") != "https://accounts.google.com":
            raise Exception(f"Invalid issuer: {payload.get('iss')}")

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise Exception("Token has expired")

        logger.debug("JWT validation passed", audience=payload.get("aud"), issuer=payload.get("iss"))
        return payload

    except Exception as e:
        logger.error(f"JWT validation error: {e}")
        raise


def _extract_user_id_from_email(email: str) -> Optional[str]:
    """
    Extract user ID from email address.

    This is a simple implementation that extracts the username part.
    In a real application, you might need to map email addresses to user IDs
    using a database lookup or a more sophisticated mapping strategy.

    Args:
        email: Email address

    Returns:
        User ID or None if extraction fails
    """
    try:
        # Simple extraction: username@domain.com -> username
        username = email.split('@')[0]
        if username and len(username) > 0:
            return username
        return None
    except Exception as e:
        logger.error(f"Failed to extract user ID from email {email}: {e}")
        return None


async def _process_gmail_notification(
    user_id: str,
    history_id: str,
    email_address: str
) -> None:
    """
    Process a Gmail notification by triggering email sync.

    This function is called as a background task to handle the
    actual email synchronization after the webhook has responded.

    Args:
        user_id: User identifier
        history_id: Gmail history ID from the notification
        email_address: Email address that received the notification
    """
    try:
        logger.info(
            "Processing Gmail notification",
            user_id=user_id,
            history_id=history_id,
            email_address=email_address
        )

        # Queue the email sync task using Celery
        # We'll use the existing sync_gmail_messages task
        sync_task = sync_gmail_messages.delay(
            user_id=user_id,
            query="",  # Empty query to sync all messages
            max_messages=50,  # Limit the number of messages per sync
            process_attachments=True
        )

        logger.info(
            "Email sync task queued",
            user_id=user_id,
            history_id=history_id,
            task_id=sync_task.id
        )

        # In a more sophisticated implementation, you could:
        # 1. Store the history_id for incremental sync
        # 2. Check if this history_id was already processed
        # 3. Use the history_id to fetch only new changes since last sync

    except Exception as e:
        logger.error(
            "Failed to process Gmail notification",
            user_id=user_id,
            history_id=history_id,
            email_address=email_address,
            error=str(e),
            exc_info=True
        )

        # In a production system, you might want to:
        # 1. Store failed notifications for retry
        # 2. Send alerts for repeated failures
        # 3. Implement a retry mechanism


@router.get("/gmail/webhook/health")
async def gmail_webhook_health() -> Dict[str, Any]:
    """
    Health check endpoint for Gmail webhook.

    This endpoint can be used to verify that the Gmail webhook
    is properly configured and accessible.
    """
    return {
        "status": "healthy",
        "service": "gmail_webhook",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            "/gmail/push",
            "/gmail/webhook/health"
        ]
    }


# Export the router
__all__ = ["router"]

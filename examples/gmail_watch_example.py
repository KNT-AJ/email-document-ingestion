"""
Gmail Watch Setup Example

This script demonstrates how to set up Gmail push notifications using the Gmail API watch functionality.
It includes examples of:
- Setting up Pub/Sub topics and subscriptions
- Configuring Gmail watches
- Handling watch renewals and cleanup

Prerequisites:
1. Google Cloud project with Pub/Sub API enabled
2. Gmail API enabled in the project
3. Service account with appropriate permissions
4. Authenticated Gmail user

Environment variables needed:
- GOOGLE_CLOUD_PROJECT: Your Google Cloud project ID
- GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file
- GMAIL_USER_ID: The user ID for Gmail authentication
"""

import os
import logging
from typing import Optional

from services.gmail_service import get_gmail_service
from services.gmail_watch_config import get_gmail_watch_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_gmail_watch(user_id: str, topic_name: str = "gmail-notifications",
                     subscription_name: str = "gmail-push-subscription",
                     push_endpoint: Optional[str] = None) -> bool:
    """
    Complete setup for Gmail watch functionality.

    Args:
        user_id: Gmail user ID
        topic_name: Pub/Sub topic name
        subscription_name: Pub/Sub subscription name
        push_endpoint: HTTPS endpoint for push notifications

    Returns:
        True if setup successful, False otherwise
    """
    try:
        # Initialize services
        gmail_service = get_gmail_service()
        watch_config = get_gmail_watch_config()

        # Get project ID
        project_id = watch_config.project_id
        if not project_id:
            logger.error("Google Cloud project ID not found. Set GOOGLE_CLOUD_PROJECT environment variable.")
            return False

        logger.info(f"Setting up Gmail watch for project: {project_id}")

        # Step 1: Set up Pub/Sub infrastructure
        if push_endpoint:
            logger.info("Setting up Pub/Sub topic and subscription...")
            infrastructure = watch_config.setup_gmail_watch_infrastructure(
                topic_name=topic_name,
                subscription_name=subscription_name,
                push_endpoint=push_endpoint
            )
            logger.info(f"Pub/Sub infrastructure created: {infrastructure}")
        else:
            logger.info("Setting up Pub/Sub topic only (no push subscription)...")
            topic_path = watch_config.create_topic(topic_name)
            watch_config.grant_gmail_publisher_role(topic_name)
            logger.info(f"Topic created with permissions: {topic_path}")

        # Step 2: Set up Gmail watch
        full_topic_name = f"projects/{project_id}/topics/{topic_name}"

        logger.info(f"Setting up Gmail watch for user: {user_id}")
        watch_response = gmail_service.setup_watch_with_retry(
            user_id=user_id,
            topic_name=full_topic_name,
            label_ids=['INBOX'],  # Watch inbox messages
            watch_duration_days=7
        )

        if watch_response:
            logger.info(f"Gmail watch setup successful!")
            logger.info(f"History ID: {watch_response.get('historyId')}")
            logger.info(f"Expiration: {watch_response.get('expiration')}")

            # Step 3: Validate setup
            validation = watch_config.validate_topic_permissions(topic_name)
            logger.info(f"Setup validation: {validation}")

            return True
        else:
            logger.error("Failed to set up Gmail watch")
            return False

    except Exception as e:
        logger.error(f"Error setting up Gmail watch: {e}")
        return False


def stop_gmail_watch(user_id: str) -> bool:
    """
    Stop Gmail watch for a user.

    Args:
        user_id: Gmail user ID

    Returns:
        True if successful, False otherwise
    """
    try:
        gmail_service = get_gmail_service()

        logger.info(f"Stopping Gmail watch for user: {user_id}")
        success = gmail_service.stop_watch(user_id)

        if success:
            logger.info("Gmail watch stopped successfully")
        else:
            logger.error("Failed to stop Gmail watch")

        return success

    except Exception as e:
        logger.error(f"Error stopping Gmail watch: {e}")
        return False


def renew_gmail_watch(user_id: str, topic_name: str = "gmail-notifications") -> bool:
    """
    Renew Gmail watch for a user.

    Args:
        user_id: Gmail user ID
        topic_name: Pub/Sub topic name

    Returns:
        True if successful, False otherwise
    """
    try:
        gmail_service = get_gmail_service()
        watch_config = get_gmail_watch_config()

        project_id = watch_config.project_id
        if not project_id:
            logger.error("Google Cloud project ID not found")
            return False

        full_topic_name = f"projects/{project_id}/topics/{topic_name}"

        logger.info(f"Renewing Gmail watch for user: {user_id}")
        watch_response = gmail_service.renew_watch(
            user_id=user_id,
            topic_name=full_topic_name,
            label_ids=['INBOX'],
            watch_duration_days=7
        )

        if watch_response:
            logger.info("Gmail watch renewed successfully!")
            logger.info(f"New history ID: {watch_response.get('historyId')}")
            return True
        else:
            logger.error("Failed to renew Gmail watch")
            return False

    except Exception as e:
        logger.error(f"Error renewing Gmail watch: {e}")
        return False


def get_watch_status(user_id: str) -> Optional[dict]:
    """
    Get current Gmail watch status for a user.

    Args:
        user_id: Gmail user ID

    Returns:
        Watch status dictionary or None if no active watch
    """
    try:
        gmail_service = get_gmail_service()

        logger.info(f"Getting watch status for user: {user_id}")
        status = gmail_service.get_watch_status(user_id)

        if status:
            logger.info(f"Watch status: {status}")
        else:
            logger.info("No active watch found for user")

        return status

    except Exception as e:
        logger.error(f"Error getting watch status: {e}")
        return None


def main():
    """Main function demonstrating Gmail watch functionality."""
    # Get configuration from environment
    user_id = os.environ.get('GMAIL_USER_ID', 'default_user')
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    push_endpoint = os.environ.get('GMAIL_PUSH_ENDPOINT')  # Optional

    if not project_id:
        logger.error("GOOGLE_CLOUD_PROJECT environment variable is required")
        return

    logger.info("Gmail Watch Example")
    logger.info("=" * 50)

    # Example 1: Set up Gmail watch
    logger.info("\n1. Setting up Gmail watch...")
    success = setup_gmail_watch(
        user_id=user_id,
        push_endpoint=push_endpoint
    )

    if success:
        # Example 2: Get watch status
        logger.info("\n2. Getting watch status...")
        status = get_watch_status(user_id)

        # Example 3: Renew watch (simulate renewal)
        logger.info("\n3. Renewing watch...")
        renew_success = renew_gmail_watch(user_id)

        # Example 4: Stop watch
        logger.info("\n4. Stopping watch...")
        stop_success = stop_gmail_watch(user_id)

        logger.info("\nGmail watch example completed!")

    else:
        logger.error("Failed to set up Gmail watch")


if __name__ == "__main__":
    main()

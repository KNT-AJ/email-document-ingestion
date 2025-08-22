"""
Gmail Watch Configuration and Pub/Sub Setup

This module provides utilities for configuring Google Cloud Pub/Sub topics and subscriptions
for Gmail watch notifications. It includes functions to create topics, set up subscriptions,
and manage permissions for Gmail API push notifications.
"""

import logging
import json
from typing import Optional, Dict, Any
from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists, NotFound, PermissionDenied
import google.auth
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GmailWatchConfig:
    """
    Configuration and management class for Gmail watch Pub/Sub setup.

    This class handles:
    - Creating and managing Pub/Sub topics for Gmail notifications
    - Setting up push subscriptions with proper endpoints
    - Managing IAM permissions for Gmail API service account
    - Validating topic and subscription configurations
    """

    def __init__(self, project_id: Optional[str] = None, credentials_path: Optional[str] = None):
        """
        Initialize Gmail watch configuration.

        Args:
            project_id: Google Cloud project ID (default: from environment)
            credentials_path: Path to service account JSON file (default: from environment)
        """
        self.project_id = project_id or self._get_project_id()
        self.credentials_path = credentials_path
        self.publisher = None
        self.subscriber = None
        self._initialize_clients()

    def _get_project_id(self) -> str:
        """Get project ID from environment or credentials."""
        import os
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            # Try to get from credentials file if available
            credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path:
                try:
                    with open(credentials_path) as f:
                        creds_data = json.load(f)
                        project_id = creds_data.get('project_id')
                except Exception as e:
                    logger.warning(f"Could not extract project ID from credentials: {e}")
        return project_id

    def _initialize_clients(self):
        """Initialize Pub/Sub clients with proper credentials."""
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                self.publisher = pubsub_v1.PublisherClient(credentials=credentials)
                self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
            else:
                # Use default credentials
                self.publisher = pubsub_v1.PublisherClient()
                self.subscriber = pubsub_v1.SubscriberClient()

            logger.info("Pub/Sub clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Pub/Sub clients: {e}")
            raise

    def create_topic(self, topic_name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """
        Create a Pub/Sub topic for Gmail notifications.

        Args:
            topic_name: Name of the topic (without project prefix)
            labels: Optional labels to apply to the topic

        Returns:
            Full topic name (projects/project/topics/topic_name)
        """
        try:
            topic_path = self.publisher.topic_path(self.project_id, topic_name)

            # Check if topic already exists
            try:
                topic = self.publisher.get_topic(topic_path)
                logger.info(f"Topic {topic_path} already exists")
                return topic_path
            except NotFound:
                pass  # Topic doesn't exist, we'll create it

            # Create the topic
            topic = pubsub_v1.Topic()
            if labels:
                topic.labels.update(labels)

            topic = self.publisher.create_topic(topic_path, topic)
            logger.info(f"Created topic: {topic_path}")
            return topic_path

        except AlreadyExists:
            logger.info(f"Topic {topic_name} already exists in project {self.project_id}")
            return self.publisher.topic_path(self.project_id, topic_name)
        except Exception as e:
            logger.error(f"Failed to create topic {topic_name}: {e}")
            raise

    def create_push_subscription(self, topic_name: str, subscription_name: str,
                               push_endpoint: str, ack_deadline_seconds: int = 60) -> str:
        """
        Create a push subscription for Gmail notifications.

        Args:
            topic_name: Name of the topic (without project prefix)
            subscription_name: Name of the subscription (without project prefix)
            push_endpoint: HTTPS endpoint for push notifications
            ack_deadline_seconds: Acknowledgment deadline in seconds

        Returns:
            Full subscription name
        """
        try:
            topic_path = self.publisher.topic_path(self.project_id, topic_name)
            subscription_path = self.subscriber.subscription_path(self.project_id, subscription_name)

            # Check if subscription already exists
            try:
                subscription = self.subscriber.get_subscription(subscription_path)
                logger.info(f"Subscription {subscription_path} already exists")
                return subscription_path
            except NotFound:
                pass  # Subscription doesn't exist, we'll create it

            # Create the subscription
            push_config = pubsub_v1.types.PushConfig(
                push_endpoint=push_endpoint
            )

            subscription = self.subscriber.create_subscription(
                subscription_path,
                topic_path,
                push_config=push_config,
                ack_deadline_seconds=ack_deadline_seconds
            )

            logger.info(f"Created push subscription: {subscription_path} -> {push_endpoint}")
            return subscription_path

        except AlreadyExists:
            logger.info(f"Subscription {subscription_name} already exists in project {self.project_id}")
            return self.subscriber.subscription_path(self.project_id, subscription_name)
        except Exception as e:
            logger.error(f"Failed to create subscription {subscription_name}: {e}")
            raise

    def grant_gmail_publisher_role(self, topic_name: str) -> bool:
        """
        Grant publisher role to gmail-api-push@system.gserviceaccount.com.

        Args:
            topic_name: Name of the topic (without project prefix)

        Returns:
            True if successful, False otherwise
        """
        try:
            from google.iam.v1 import iam_policy_pb2, policy_pb2

            topic_path = self.publisher.topic_path(self.project_id, topic_name)
            gmail_service_account = "gmail-api-push@system.gserviceaccount.com"

            # Get current policy
            policy = self.publisher.get_iam_policy(topic_path)

            # Check if Gmail service account already has publisher role
            gmail_binding = None
            for binding in policy.bindings:
                if binding.role == "roles/pubsub.publisher":
                    if gmail_service_account in binding.members:
                        logger.info(f"Gmail service account already has publisher role on topic {topic_name}")
                        return True
                    gmail_binding = binding
                    break

            # Add Gmail service account to publisher role
            if gmail_binding:
                if gmail_service_account not in gmail_binding.members:
                    gmail_binding.members.append(f"serviceAccount:{gmail_service_account}")
            else:
                # Create new binding
                new_binding = policy_pb2.Binding()
                new_binding.role = "roles/pubsub.publisher"
                new_binding.members.append(f"serviceAccount:{gmail_service_account}")
                policy.bindings.append(new_binding)

            # Set the updated policy
            self.publisher.set_iam_policy(topic_path, policy)
            logger.info(f"Granted publisher role to {gmail_service_account} on topic {topic_name}")
            return True

        except PermissionDenied:
            logger.error("Insufficient permissions to modify IAM policy. "
                        "Ensure you have resourcemanager.projects.setIamPolicy permission.")
            return False
        except Exception as e:
            logger.error(f"Failed to grant publisher role on topic {topic_name}: {e}")
            return False

    def setup_gmail_watch_infrastructure(self, topic_name: str, subscription_name: str,
                                       push_endpoint: str,
                                       labels: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Complete setup for Gmail watch infrastructure.

        Args:
            topic_name: Name of the Pub/Sub topic
            subscription_name: Name of the push subscription
            push_endpoint: HTTPS endpoint for notifications
            labels: Optional labels for the topic

        Returns:
            Dictionary with created resource names
        """
        try:
            # Create topic
            full_topic_name = self.create_topic(topic_name, labels)

            # Grant permissions to Gmail service account
            if not self.grant_gmail_publisher_role(topic_name):
                raise Exception("Failed to grant permissions to Gmail service account")

            # Create push subscription
            full_subscription_name = self.create_push_subscription(
                topic_name, subscription_name, push_endpoint
            )

            logger.info("Gmail watch infrastructure setup completed successfully")
            return {
                'topic': full_topic_name,
                'subscription': full_subscription_name,
                'project': self.project_id
            }

        except Exception as e:
            logger.error(f"Failed to set up Gmail watch infrastructure: {e}")
            raise

    def validate_topic_permissions(self, topic_name: str) -> Dict[str, Any]:
        """
        Validate that Gmail service account has proper permissions on the topic.

        Args:
            topic_name: Name of the topic (without project prefix)

        Returns:
            Dictionary with validation results
        """
        try:
            from google.iam.v1 import iam_policy_pb2

            topic_path = self.publisher.topic_path(self.project_id, topic_name)
            gmail_service_account = "gmail-api-push@system.gserviceaccount.com"

            # Get current policy
            policy = self.publisher.get_iam_policy(topic_path)

            # Check for publisher role
            has_publisher_role = False
            for binding in policy.bindings:
                if binding.role == "roles/pubsub.publisher":
                    if f"serviceAccount:{gmail_service_account}" in binding.members:
                        has_publisher_role = True
                        break

            result = {
                'topic_exists': True,
                'gmail_has_publisher_role': has_publisher_role,
                'project_id': self.project_id,
                'topic_name': topic_name
            }

            if has_publisher_role:
                logger.info(f"Gmail service account has proper permissions on topic {topic_name}")
            else:
                logger.warning(f"Gmail service account missing publisher role on topic {topic_name}")

            return result

        except NotFound:
            return {
                'topic_exists': False,
                'gmail_has_publisher_role': False,
                'project_id': self.project_id,
                'topic_name': topic_name
            }
        except Exception as e:
            logger.error(f"Failed to validate topic permissions: {e}")
            return {
                'topic_exists': False,
                'gmail_has_publisher_role': False,
                'error': str(e)
            }

    def delete_topic(self, topic_name: str, force: bool = False) -> bool:
        """
        Delete a Pub/Sub topic.

        Args:
            topic_name: Name of the topic (without project prefix)
            force: If True, delete topic even if subscriptions exist

        Returns:
            True if successful, False otherwise
        """
        try:
            topic_path = self.publisher.topic_path(self.project_id, topic_name)
            self.publisher.delete_topic(topic_path)
            logger.info(f"Deleted topic: {topic_path}")
            return True

        except NotFound:
            logger.info(f"Topic {topic_name} not found, nothing to delete")
            return True
        except Exception as e:
            logger.error(f"Failed to delete topic {topic_name}: {e}")
            return False

    def delete_subscription(self, subscription_name: str) -> bool:
        """
        Delete a Pub/Sub subscription.

        Args:
            subscription_name: Name of the subscription (without project prefix)

        Returns:
            True if successful, False otherwise
        """
        try:
            subscription_path = self.subscriber.subscription_path(self.project_id, subscription_name)
            self.subscriber.delete_subscription(subscription_path)
            logger.info(f"Deleted subscription: {subscription_path}")
            return True

        except NotFound:
            logger.info(f"Subscription {subscription_name} not found, nothing to delete")
            return True
        except Exception as e:
            logger.error(f"Failed to delete subscription {subscription_name}: {e}")
            return False


# Global instance
_gmail_watch_config = None

def get_gmail_watch_config(project_id: Optional[str] = None,
                          credentials_path: Optional[str] = None) -> GmailWatchConfig:
    """Get the global Gmail watch configuration instance."""
    global _gmail_watch_config
    if _gmail_watch_config is None:
        _gmail_watch_config = GmailWatchConfig(project_id, credentials_path)
    return _gmail_watch_config


def setup_gmail_watch_topic(project_id: str, topic_name: str,
                          credentials_path: Optional[str] = None) -> str:
    """
    Convenience function to set up a Gmail watch topic with proper permissions.

    Args:
        project_id: Google Cloud project ID
        topic_name: Name of the topic to create
        credentials_path: Path to service account credentials

    Returns:
        Full topic name
    """
    config = GmailWatchConfig(project_id, credentials_path)
    return config.create_topic(topic_name)


def validate_gmail_watch_setup(project_id: str, topic_name: str,
                             credentials_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to validate Gmail watch setup.

    Args:
        project_id: Google Cloud project ID
        topic_name: Name of the topic to validate
        credentials_path: Path to service account credentials

    Returns:
        Validation results dictionary
    """
    config = GmailWatchConfig(project_id, credentials_path)
    return config.validate_topic_permissions(topic_name)

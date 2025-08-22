#!/usr/bin/env python3
"""
Gmail Message Service Example

This example demonstrates how to use the GmailMessageService to fetch, parse,
and work with Gmail messages including attachments and various content types.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services import GmailMessageService, get_gmail_service


def main():
    """Main example function demonstrating Gmail message service usage."""

    print("Gmail Message Service Example")
    print("=" * 40)

    # Initialize services
    gmail_service = get_gmail_service()
    message_service = GmailMessageService(gmail_service)

    # Check if user is authenticated
    user_id = "example_user"  # Replace with actual user ID

    if not gmail_service.is_authenticated(user_id):
        print(f"User {user_id} is not authenticated.")
        print("Please run the Gmail authentication example first.")
        return

    print(f"✓ User {user_id} is authenticated")

    # Example 1: Fetch a single message by ID
    print("\n1. Fetching a single message by ID...")
    try:
        # You would typically get a message ID from a search or list operation
        # For this example, we'll use a placeholder
        message_id = "example_message_id"

        message = message_service.fetch_message_by_id(user_id, message_id)
        if message:
            print(f"✓ Message fetched successfully:")
            print(f"  - Subject: {message['headers'].get('subject', 'N/A')}")
            print(f"  - From: {message['headers'].get('from', 'N/A')}")
            print(f"  - Body preview: {message['body']['text'][:100]}...")
            print(f"  - Attachments: {len(message.get('attachments', []))}")
        else:
            print("✗ Failed to fetch message")

    except Exception as e:
        print(f"✗ Error fetching message: {e}")

    # Example 2: Search messages with query
    print("\n2. Searching messages with query...")
    try:
        query = "subject:example"  # Gmail search syntax
        messages = message_service.fetch_messages_by_query(
            user_id,
            query=query,
            max_results=5
        )

        print(f"✓ Found {len(messages)} messages matching query: {query}")
        for i, msg in enumerate(messages[:3]):  # Show first 3
            print(f"  {i+1}. {msg['headers'].get('subject', 'No Subject')}")

    except Exception as e:
        print(f"✗ Error searching messages: {e}")

    # Example 3: Search with structured filters
    print("\n3. Searching messages with structured filters...")
    try:
        filters = {
            'from': 'noreply@example.com',
            'after': '2024-01-01',
            'has_attachment': True
        }

        messages = message_service.search_messages_with_filters(
            user_id,
            filters=filters,
            max_results=3
        )

        print(f"✓ Found {len(messages)} messages matching filters")
        for msg in messages:
            print(f"  - {msg['headers'].get('subject', 'No Subject')}")

    except Exception as e:
        print(f"✗ Error searching with filters: {e}")

    # Example 4: Get message summaries (efficient for listing)
    print("\n4. Getting message summaries...")
    try:
        # First, get some message IDs to work with
        search_results = message_service.fetch_messages_by_query(
            user_id,
            query="",
            max_results=3
        )

        if search_results:
            message_ids = [msg['id'] for msg in search_results]
            summaries = message_service.batch_fetch_message_summaries(user_id, message_ids)

            print(f"✓ Retrieved {len(summaries)} message summaries:")
            for summary in summaries:
                print(f"  - {summary['headers']['subject']} ({summary['attachment_count']} attachments)")

    except Exception as e:
        print(f"✗ Error getting summaries: {e}")

    # Example 5: Get a message thread
    print("\n5. Getting a message thread...")
    try:
        # Get first message to use its thread ID
        messages = message_service.fetch_messages_by_query(user_id, max_results=1)
        if messages:
            thread_id = messages[0]['thread_id']
            thread_messages = message_service.get_message_thread(user_id, thread_id)

            print(f"✓ Retrieved {len(thread_messages)} messages from thread")
            for i, msg in enumerate(thread_messages):
                print(f"  {i+1}. {msg['headers'].get('subject', 'No Subject')}")

    except Exception as e:
        print(f"✗ Error getting thread: {e}")

    # Example 6: Download attachment
    print("\n6. Downloading attachment...")
    try:
        # Find a message with attachments
        messages = message_service.fetch_messages_by_query(
            user_id,
            query="has:attachment",
            max_results=1
        )

        if messages and messages[0].get('attachments'):
            message = messages[0]
            attachment = message['attachments'][0]
            attachment_id = attachment['attachment_id']

            print(f"✓ Found message with attachment: {attachment['filename']}")

            # Download attachment
            attachment_data = message_service.download_attachment(
                user_id,
                message['id'],
                attachment_id
            )

            if attachment_data:
                print(f"✓ Successfully downloaded {len(attachment_data)} bytes")

                # Save attachment to file (example)
                filename = attachment['filename']
                with open(f"downloaded_{filename}", 'wb') as f:
                    f.write(attachment_data)
                print(f"✓ Saved attachment as: downloaded_{filename}")
            else:
                print("✗ Failed to download attachment")

    except Exception as e:
        print(f"✗ Error downloading attachment: {e}")

    # Example 7: Get raw message content
    print("\n7. Getting raw message content...")
    try:
        messages = message_service.fetch_messages_by_query(user_id, max_results=1)
        if messages:
            message_id = messages[0]['id']
            raw_content = message_service.get_message_raw_content(user_id, message_id)

            if raw_content:
                print("✓ Retrieved raw message content:")
                print(f"  First 200 characters: {raw_content[:200]}...")
            else:
                print("✗ Failed to get raw content")

    except Exception as e:
        print(f"✗ Error getting raw content: {e}")

    print("\n" + "=" * 40)
    print("Example completed!")


if __name__ == "__main__":
    main()

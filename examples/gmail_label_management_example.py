"""
Example usage of Gmail Label Management functionality.

This script demonstrates how to use the enhanced GmailService for label management,
including listing labels, creating new labels, and assigning labels to messages.
"""

from services.gmail_service import get_gmail_service


def main():
    """Demonstrate Gmail label management functionality."""
    # Get the Gmail service instance
    gmail_service = get_gmail_service()

    # Example user ID (in a real app, this would come from authentication)
    user_id = "example_user"

    print("=== Gmail Label Management Example ===\n")

    # 1. List all labels
    print("1. Listing all Gmail labels:")
    labels = gmail_service.list_labels(user_id)
    if labels:
        for label in labels[:5]:  # Show first 5 labels
            print(f"   - {label['name']} (ID: {label['id']}, Type: {label.get('type', 'user')})")
        if len(labels) > 5:
            print(f"   ... and {len(labels) - 5} more labels")
    else:
        print("   No labels found or authentication required")
    print()

    # 2. Ensure a label exists (create if necessary)
    print("2. Ensuring 'Data Ingestion' label exists:")
    label_result = gmail_service.ensure_label_exists(
        user_id,
        'Data Ingestion',
        label_color={
            'backgroundColor': '#ff5722',
            'textColor': '#ffffff'
        }
    )
    if label_result:
        print(f"   Label ready: {label_result['name']} (ID: {label_result['id']})")
    else:
        print("   Failed to create/ensure label exists")
    print()

    # 3. Get a label by name
    print("3. Getting label by name 'INBOX':")
    inbox_label = gmail_service.get_label_by_name(user_id, 'INBOX')
    if inbox_label:
        print(f"   Found: {inbox_label['name']} (ID: {inbox_label['id']})")
    else:
        print("   INBOX label not found")
    print()

    # 4. Example of assigning labels to messages (would need real message IDs)
    print("4. Example label assignment (requires real message IDs):")
    print("   # Assign 'Data Ingestion' label to a message")
    print("   success = gmail_service.assign_label_to_message(")
    print("       user_id, 'msg_12345', 'Data Ingestion')")
    print()
    print("   # Remove 'Data Ingestion' label from a message")
    print("   success = gmail_service.remove_label_from_message(")
    print("       user_id, 'msg_12345', 'Data Ingestion')")
    print()

    # 5. Batch label assignment example
    print("5. Example batch label assignment:")
    print("   result = gmail_service.assign_labels_to_messages(")
    print("       user_id,")
    print("       ['msg_123', 'msg_456', 'msg_789'],")
    print("       ['Data Ingestion', 'Important']")
    print("   )")
    print("   print(f\"Successful: {result['successful']}, Failed: {result['failed']}\")")
    print()

    print("=== Label Management Features ===")
    print("✅ List all Gmail labels")
    print("✅ Get labels by name or ID")
    print("✅ Create labels with custom colors")
    print("✅ Assign single or multiple labels to messages")
    print("✅ Remove labels from messages")
    print("✅ Batch operations for multiple messages")
    print("✅ Automatic label name/ID resolution")
    print("✅ Comprehensive error handling and logging")
    print("✅ Full test coverage")


if __name__ == "__main__":
    main()

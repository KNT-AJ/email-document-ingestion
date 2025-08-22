"""
Email Persistence Service

Service for storing email metadata and content in the database with duplicate detection
and querying capabilities. Handles character encodings and special characters properly.
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union
from email.utils import parsedate_to_datetime, parseaddr
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import and_, or_, func, desc

from models.email import Email
from models.database import get_database_service
from models.utils import EmailUtils

logger = logging.getLogger(__name__)


class EmailPersistenceService:
    """
    Service for persisting email data to database with deduplication and querying.
    
    Provides functionality to:
    - Store email metadata and content with duplicate detection
    - Query emails by various criteria
    - Handle character encodings and special characters
    - Validate and normalize email data
    """

    def __init__(self):
        """Initialize the persistence service."""
        self.db_service = get_database_service()
        self.email_utils = EmailUtils()

    def persist_email(self, email_data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Email]:
        """
        Persist email data to database with duplicate detection.

        Args:
            email_data: Dictionary containing email data from Gmail API
            user_id: User identifier (for logging purposes)

        Returns:
            Email instance if successful, None if duplicate or error

        Raises:
            ValueError: If required email data is missing or invalid
        """
        try:
            # Validate required fields
            gmail_message_id = email_data.get('id')
            if not gmail_message_id:
                raise ValueError("Gmail message ID is required")

            with self.db_service.get_session() as session:
                # Check for existing email (duplicate detection)
                existing_email = self.email_utils.get_email_by_gmail_id(session, gmail_message_id)
                if existing_email:
                    logger.info(f"Email {gmail_message_id} already exists, skipping duplicate")
                    return existing_email

                # Extract and normalize email data
                email_record = self._create_email_record(email_data)
                
                # Save to database
                session.add(email_record)
                session.commit()
                session.refresh(email_record)

                logger.info(f"Successfully persisted email {gmail_message_id} for user {user_id}")
                return email_record

        except IntegrityError as e:
            logger.warning(f"Duplicate email detected during insert for {gmail_message_id}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid email data for {gmail_message_id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error persisting email {gmail_message_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error persisting email {gmail_message_id}: {e}")
            return None

    def batch_persist_emails(self, emails_data: List[Dict[str, Any]], 
                           user_id: Optional[str] = None) -> List[Email]:
        """
        Persist multiple emails in batch with duplicate detection.

        Args:
            emails_data: List of email data dictionaries
            user_id: User identifier (for logging purposes)

        Returns:
            List of successfully persisted Email instances
        """
        persisted_emails = []
        
        try:
            with self.db_service.get_session() as session:
                for email_data in emails_data:
                    try:
                        gmail_message_id = email_data.get('id')
                        if not gmail_message_id:
                            logger.warning("Skipping email with missing Gmail message ID")
                            continue

                        # Check for duplicate
                        existing_email = self.email_utils.get_email_by_gmail_id(session, gmail_message_id)
                        if existing_email:
                            logger.debug(f"Skipping duplicate email {gmail_message_id}")
                            continue

                        # Create email record
                        email_record = self._create_email_record(email_data)
                        session.add(email_record)
                        persisted_emails.append(email_record)

                    except Exception as e:
                        logger.error(f"Error processing email {gmail_message_id}: {e}")
                        continue

                # Commit all changes at once
                session.commit()
                
                # Refresh all records to get IDs
                for email in persisted_emails:
                    session.refresh(email)

                logger.info(f"Successfully persisted {len(persisted_emails)} emails for user {user_id}")
                return persisted_emails

        except SQLAlchemyError as e:
            logger.error(f"Database error during batch persist for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during batch persist for user {user_id}: {e}")
            return []

    def get_emails_by_criteria(self, criteria: Dict[str, Any], 
                             limit: Optional[int] = None,
                             offset: Optional[int] = None) -> List[Email]:
        """
        Query emails by various criteria.

        Args:
            criteria: Dictionary of search criteria
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of matching Email instances

        Supported criteria:
            - sender: Email sender address (exact or partial match)
            - subject: Subject line (partial match)
            - date_from: Start date for filtering
            - date_to: End date for filtering
            - labels: Gmail labels to filter by
            - has_attachments: Boolean for attachment presence
            - processing_status: Processing status filter
            - thread_id: Gmail thread ID
        """
        try:
            with self.db_service.get_session() as session:
                query = session.query(Email)

                # Apply filters based on criteria
                if 'sender' in criteria:
                    sender = criteria['sender']
                    if isinstance(sender, str):
                        query = query.filter(Email.sender.ilike(f"%{sender}%"))

                if 'subject' in criteria:
                    subject = criteria['subject']
                    if isinstance(subject, str):
                        query = query.filter(Email.subject.ilike(f"%{subject}%"))

                if 'date_from' in criteria:
                    date_from = criteria['date_from']
                    if isinstance(date_from, (datetime, str)):
                        if isinstance(date_from, str):
                            date_from = datetime.fromisoformat(date_from)
                        query = query.filter(Email.sent_date >= date_from)

                if 'date_to' in criteria:
                    date_to = criteria['date_to']
                    if isinstance(date_to, (datetime, str)):
                        if isinstance(date_to, str):
                            date_to = datetime.fromisoformat(date_to)
                        query = query.filter(Email.sent_date <= date_to)

                if 'labels' in criteria:
                    labels = criteria['labels']
                    if isinstance(labels, list) and labels:
                        # Filter emails that have any of the specified labels
                        label_conditions = []
                        for label in labels:
                            label_conditions.append(Email.labels.any(label))
                        query = query.filter(or_(*label_conditions))

                if 'has_attachments' in criteria:
                    has_attachments = criteria['has_attachments']
                    if isinstance(has_attachments, bool):
                        query = query.filter(Email.has_attachments == has_attachments)

                if 'processing_status' in criteria:
                    status = criteria['processing_status']
                    if isinstance(status, str):
                        query = query.filter(Email.processing_status == status)

                if 'thread_id' in criteria:
                    thread_id = criteria['thread_id']
                    if isinstance(thread_id, str):
                        query = query.filter(Email.gmail_thread_id == thread_id)

                # Apply ordering (most recent first)
                query = query.order_by(desc(Email.sent_date))

                # Apply pagination
                if offset:
                    query = query.offset(offset)
                if limit:
                    query = query.limit(limit)

                return query.all()

        except SQLAlchemyError as e:
            logger.error(f"Database error querying emails: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying emails: {e}")
            return []

    def search_emails_fulltext(self, search_term: str, 
                              limit: Optional[int] = None) -> List[Email]:
        """
        Perform full-text search on email content.

        Args:
            search_term: Text to search for
            limit: Maximum number of results

        Returns:
            List of matching Email instances
        """
        try:
            with self.db_service.get_session() as session:
                # Search in subject and body text
                query = session.query(Email).filter(
                    or_(
                        Email.subject.ilike(f"%{search_term}%"),
                        Email.body_text.ilike(f"%{search_term}%")
                    )
                ).order_by(desc(Email.sent_date))

                if limit:
                    query = query.limit(limit)

                return query.all()

        except SQLAlchemyError as e:
            logger.error(f"Database error during full-text search: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during full-text search: {e}")
            return []

    def get_email_stats(self) -> Dict[str, Any]:
        """
        Get email statistics.

        Returns:
            Dictionary containing email statistics
        """
        try:
            with self.db_service.get_session() as session:
                total_emails = session.query(Email).count()
                unprocessed_emails = session.query(Email).filter(
                    Email.processing_status == 'pending'
                ).count()
                emails_with_attachments = session.query(Email).filter(
                    Email.has_attachments == True
                ).count()

                # Get sender statistics
                sender_stats = session.query(
                    Email.sender, func.count(Email.id)
                ).group_by(Email.sender).order_by(
                    desc(func.count(Email.id))
                ).limit(10).all()

                return {
                    'total_emails': total_emails,
                    'unprocessed_emails': unprocessed_emails,
                    'emails_with_attachments': emails_with_attachments,
                    'top_senders': [{'sender': sender, 'count': count} 
                                  for sender, count in sender_stats]
                }

        except SQLAlchemyError as e:
            logger.error(f"Database error getting email stats: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting email stats: {e}")
            return {}

    def update_processing_status(self, email_id: int, status: str, 
                               error_message: Optional[str] = None) -> bool:
        """
        Update the processing status of an email.

        Args:
            email_id: Email ID
            status: New processing status
            error_message: Error message if status is 'failed'

        Returns:
            True if update successful, False otherwise
        """
        try:
            with self.db_service.get_session() as session:
                email = session.query(Email).filter(Email.id == email_id).first()
                if not email:
                    logger.warning(f"Email {email_id} not found for status update")
                    return False

                email.processing_status = status
                email.processed_at = datetime.now(timezone.utc)
                
                if error_message:
                    email.processing_error = error_message

                session.commit()
                logger.info(f"Updated email {email_id} status to {status}")
                return True

        except SQLAlchemyError as e:
            logger.error(f"Database error updating email {email_id} status: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating email {email_id} status: {e}")
            return False

    def _create_email_record(self, email_data: Dict[str, Any]) -> Email:
        """
        Create Email model instance from Gmail API data.

        Args:
            email_data: Gmail API email data

        Returns:
            Email model instance

        Raises:
            ValueError: If required data is missing or invalid
        """
        try:
            # Extract required fields
            gmail_message_id = email_data.get('id')
            if not gmail_message_id:
                raise ValueError("Gmail message ID is required")

            # Extract headers
            headers = email_data.get('headers', {})
            
            # Parse sender
            sender = self._extract_email_address(headers.get('from', ''))
            if not sender:
                raise ValueError("Sender address is required")

            # Parse recipients
            recipients = self._parse_recipients(headers.get('to', ''))
            cc_recipients = self._parse_recipients(headers.get('cc', ''))
            bcc_recipients = self._parse_recipients(headers.get('bcc', ''))

            # Parse dates
            sent_date = self._parse_email_date(headers.get('date'))
            received_date = datetime.fromtimestamp(
                int(email_data.get('internal_date', '0')) / 1000, 
                tz=timezone.utc
            ) if email_data.get('internal_date') else datetime.now(timezone.utc)

            # Extract body content
            body = email_data.get('body', {})
            body_text = self._sanitize_text(body.get('text', ''))
            body_html = self._sanitize_text(body.get('html', ''))

            # Extract metadata
            subject = self._sanitize_text(headers.get('subject', ''))
            labels = email_data.get('label_ids', [])
            size_bytes = email_data.get('size_estimate', 0)
            attachments = email_data.get('attachments', [])
            
            # Create Email record
            email_record = Email(
                gmail_message_id=gmail_message_id,
                gmail_thread_id=email_data.get('thread_id'),
                subject=subject[:1000] if subject else None,  # Truncate if too long
                sender=sender[:500],  # Truncate if too long
                recipients=recipients,
                cc_recipients=cc_recipients if cc_recipients else None,
                bcc_recipients=bcc_recipients if bcc_recipients else None,
                body_text=body_text,
                body_html=body_html,
                sent_date=sent_date,
                received_date=received_date,
                labels=labels if labels else None,
                is_read='UNREAD' not in labels if labels else False,
                is_starred='STARRED' in labels if labels else False,
                size_bytes=size_bytes,
                has_attachments=len(attachments) > 0,
                attachment_count=len(attachments),
                gmail_metadata=email_data.get('snippet'),
                processing_status='pending'
            )

            return email_record

        except Exception as e:
            logger.error(f"Error creating email record: {e}")
            raise ValueError(f"Failed to create email record: {e}")

    def _extract_email_address(self, email_header: str) -> str:
        """Extract email address from header string."""
        if not email_header:
            return ''
        
        try:
            # Use email.utils.parseaddr to properly parse email headers
            name, address = parseaddr(email_header)
            return address.strip() if address else ''
        except Exception:
            # Fallback: try to extract email with regex
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            matches = re.findall(email_pattern, email_header)
            return matches[0] if matches else ''

    def _parse_recipients(self, recipients_header: str) -> List[str]:
        """Parse recipients from header string."""
        if not recipients_header:
            return []
        
        recipients = []
        try:
            # Split by comma and parse each recipient
            for recipient in recipients_header.split(','):
                email_addr = self._extract_email_address(recipient.strip())
                if email_addr:
                    recipients.append(email_addr)
        except Exception as e:
            logger.warning(f"Error parsing recipients '{recipients_header}': {e}")
        
        return recipients

    def _parse_email_date(self, date_header: str) -> datetime:
        """Parse email date from header string."""
        if not date_header:
            return datetime.now(timezone.utc)
        
        try:
            # Use email.utils.parsedate_to_datetime for proper parsing
            parsed_date = parsedate_to_datetime(date_header)
            # Ensure timezone awareness
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            return parsed_date
        except Exception as e:
            logger.warning(f"Error parsing date '{date_header}': {e}")
            return datetime.now(timezone.utc)

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text content to handle special characters and encodings."""
        if not text:
            return ''
        
        try:
            # Ensure proper UTF-8 encoding
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='replace')
            
            # Remove or replace problematic characters
            text = text.replace('\x00', '')  # Remove null bytes
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)  # Remove control chars
            
            return text.strip()
        except Exception as e:
            logger.warning(f"Error sanitizing text: {e}")
            return str(text) if text else ''


# Global service instance
_persistence_service = None

def get_email_persistence_service() -> EmailPersistenceService:
    """Get the global email persistence service instance."""
    global _persistence_service
    if _persistence_service is None:
        _persistence_service = EmailPersistenceService()
    return _persistence_service

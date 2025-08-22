"""Database utility functions for common operations."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Type, TypeVar
from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import SQLAlchemyError

from .email import Email, Document, OCRRun, DocumentPage
from .database import get_database_service

logger = logging.getLogger(__name__)

# Type variable for SQLAlchemy models - import Base later to avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .base import Base

T = TypeVar('T', bound='Base')


class DatabaseUtils:
    """Utility class for common database operations."""

    def __init__(self):
        """Initialize with database service."""
        self.db_service = get_database_service()

    def get_by_id(self, session: Session, model_class: Type[T], id: int) -> Optional[T]:
        """Get a record by ID.

        Args:
            session: Database session
            model_class: SQLAlchemy model class
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        try:
            return session.query(model_class).filter(model_class.id == id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {model_class.__name__} by ID {id}: {e}")
            return None

    def get_all(self, session: Session, model_class: Type[T],
                limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """Get all records of a model with pagination.

        Args:
            session: Database session
            model_class: SQLAlchemy model class
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        try:
            query = session.query(model_class)
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {model_class.__name__}: {e}")
            return []

    def create(self, session: Session, model_class: Type[T], **kwargs) -> Optional[T]:
        """Create a new record.

        Args:
            session: Database session
            model_class: SQLAlchemy model class
            **kwargs: Model attributes

        Returns:
            Created model instance or None if creation failed
        """
        try:
            instance = model_class(**kwargs)
            session.add(instance)
            session.flush()  # Flush to get the ID without committing
            return instance
        except SQLAlchemyError as e:
            logger.error(f"Error creating {model_class.__name__}: {e}")
            return None

    def update(self, session: Session, instance: T, **kwargs) -> bool:
        """Update a record.

        Args:
            session: Database session
            instance: Model instance to update
            **kwargs: Attributes to update

        Returns:
            True if update successful, False otherwise
        """
        try:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error updating {instance.__class__.__name__}: {e}")
            return False

    def delete(self, session: Session, instance: T) -> bool:
        """Delete a record.

        Args:
            session: Database session
            instance: Model instance to delete

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            session.delete(instance)
            session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {instance.__class__.__name__}: {e}")
            return False

    def count(self, session: Session, model_class: Type[T],
              filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters.

        Args:
            session: Database session
            model_class: SQLAlchemy model class
            filters: Dictionary of field-value filters

        Returns:
            Count of matching records
        """
        try:
            query = session.query(func.count(model_class.id))
            if filters:
                for field, value in filters.items():
                    if hasattr(model_class, field):
                        query = query.filter(getattr(model_class, field) == value)
            return query.scalar() or 0
        except SQLAlchemyError as e:
            logger.error(f"Error counting {model_class.__name__}: {e}")
            return 0

    def exists(self, session: Session, model_class: Type[T], **filters) -> bool:
        """Check if a record exists with given filters.

        Args:
            session: Database session
            model_class: SQLAlchemy model class
            **filters: Field-value filters

        Returns:
            True if record exists, False otherwise
        """
        try:
            query = session.query(model_class)
            for field, value in filters.items():
                if hasattr(model_class, field):
                    query = query.filter(getattr(model_class, field) == value)
            return session.query(query.exists()).scalar()
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {model_class.__name__}: {e}")
            return False


class EmailUtils(DatabaseUtils):
    """Utility functions specific to Email model."""

    def get_email_by_gmail_id(self, session: Session, gmail_message_id: str) -> Optional[Email]:
        """Get email by Gmail message ID."""
        return session.query(Email).filter(Email.gmail_message_id == gmail_message_id).first()

    def get_emails_by_sender(self, session: Session, sender: str,
                           limit: Optional[int] = None) -> List[Email]:
        """Get emails by sender."""
        query = session.query(Email).filter(Email.sender == sender)
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_emails_by_date_range(self, session: Session,
                                start_date: datetime, end_date: datetime) -> List[Email]:
        """Get emails within a date range."""
        return session.query(Email).filter(
            and_(Email.sent_date >= start_date, Email.sent_date <= end_date)
        ).all()

    def get_unprocessed_emails(self, session: Session, limit: Optional[int] = None) -> List[Email]:
        """Get emails that haven't been processed yet."""
        query = session.query(Email).filter(Email.processing_status.in_(['pending', 'failed']))
        if limit:
            query = query.limit(limit)
        return query.all()


class DocumentUtils(DatabaseUtils):
    """Utility functions specific to Document model."""

    def get_document_by_hash(self, session: Session, storage_hash: str) -> Optional[Document]:
        """Get document by storage hash (for deduplication)."""
        return session.query(Document).filter(Document.storage_hash == storage_hash).first()

    def get_documents_by_email(self, session: Session, email_id: int) -> List[Document]:
        """Get all documents for a specific email."""
        return session.query(Document).filter(Document.email_id == email_id).all()

    def get_unprocessed_documents(self, session: Session, limit: Optional[int] = None) -> List[Document]:
        """Get documents that haven't been processed yet."""
        query = session.query(Document).filter(
            Document.processing_status.in_(['pending', 'failed'])
        )
        if limit:
            query = query.limit(limit)
        return query.all()


class OCRRunUtils(DatabaseUtils):
    """Utility functions specific to OCRRun model."""

    def get_ocr_runs_by_document(self, session: Session, document_id: int) -> List[OCRRun]:
        """Get all OCR runs for a specific document."""
        return session.query(OCRRun).filter(OCRRun.document_id == document_id).all()

    def get_best_ocr_run(self, session: Session, document_id: int) -> Optional[OCRRun]:
        """Get the best OCR run for a document based on confidence score."""
        return session.query(OCRRun).filter(
            and_(OCRRun.document_id == document_id, OCRRun.status == 'completed')
        ).order_by(desc(OCRRun.confidence_score)).first()

    def get_ocr_runs_by_engine(self, session: Session, ocr_engine: str,
                             limit: Optional[int] = None) -> List[OCRRun]:
        """Get OCR runs by engine type."""
        query = session.query(OCRRun).filter(OCRRun.ocr_engine == ocr_engine)
        if limit:
            query = query.limit(limit)
        return query.all()


class DocumentPageUtils(DatabaseUtils):
    """Utility functions specific to DocumentPage model."""

    def get_pages_by_document(self, session: Session, document_id: int) -> List[DocumentPage]:
        """Get all pages for a specific document."""
        return session.query(DocumentPage).filter(
            DocumentPage.document_id == document_id
        ).order_by(asc(DocumentPage.page_number)).all()

    def get_pages_by_ocr_run(self, session: Session, ocr_run_id: int) -> List[DocumentPage]:
        """Get all pages for a specific OCR run."""
        return session.query(DocumentPage).filter(
            DocumentPage.ocr_run_id == ocr_run_id
        ).order_by(asc(DocumentPage.page_number)).all()


# Global utility instances (lazy initialization)
_email_utils = None
_document_utils = None
_ocr_run_utils = None
_document_page_utils = None


def get_email_utils() -> EmailUtils:
    """Get global email utilities instance."""
    global _email_utils
    if _email_utils is None:
        _email_utils = EmailUtils()
    return _email_utils


def get_document_utils() -> DocumentUtils:
    """Get global document utilities instance."""
    global _document_utils
    if _document_utils is None:
        _document_utils = DocumentUtils()
    return _document_utils


def get_ocr_run_utils() -> OCRRunUtils:
    """Get global OCR run utilities instance."""
    global _ocr_run_utils
    if _ocr_run_utils is None:
        _ocr_run_utils = OCRRunUtils()
    return _ocr_run_utils


def get_document_page_utils() -> DocumentPageUtils:
    """Get global document page utilities instance."""
    global _document_page_utils
    if _document_page_utils is None:
        _document_page_utils = DocumentPageUtils()
    return _document_page_utils

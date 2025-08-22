"""Database models package."""

from .base import Base, TimestampMixin, get_db, create_tables, drop_tables, get_session_factory, get_engine
from .email import Email, Document, OCRRun, DocumentPage
from .database import DatabaseService, get_database_service
from .utils import (
    EmailUtils, DocumentUtils, OCRRunUtils, DocumentPageUtils,
    get_email_utils, get_document_utils, get_ocr_run_utils, get_document_page_utils
)

__all__ = [
    # Base classes and utilities
    "Base",
    "TimestampMixin",
    "get_db",
    "create_tables",
    "drop_tables",
    "get_session_factory",
    "get_engine",

    # Models
    "Email",
    "Document",
    "OCRun",
    "DocumentPage",

    # Database service
    "DatabaseService",
    "get_database_service",

    # Utilities
    "EmailUtils",
    "DocumentUtils",
    "OCRunUtils",
    "DocumentPageUtils",
    "get_email_utils",
    "get_document_utils",
    "get_ocr_run_utils",
    "get_document_page_utils",
]

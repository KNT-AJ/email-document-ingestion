"""Email model for storing Gmail message metadata and content."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from .base import Base, TimestampMixin


class Email(Base, TimestampMixin):
    """Email message model."""

    __tablename__ = "emails"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Gmail-specific fields
    gmail_message_id = Column(String(255), unique=True, nullable=False, index=True,
                             doc="Unique Gmail message ID")
    gmail_thread_id = Column(String(255), index=True,
                            doc="Gmail thread ID for conversation grouping")

    # Email metadata
    subject = Column(String(1000), nullable=True, doc="Email subject line")
    sender = Column(String(500), nullable=False, index=True, doc="Email sender address")
    recipients = Column(ARRAY(String), nullable=False, doc="List of recipient email addresses")
    cc_recipients = Column(ARRAY(String), nullable=True, doc="List of CC recipient addresses")
    bcc_recipients = Column(ARRAY(String), nullable=True, doc="List of BCC recipient addresses")

    # Email content
    body_text = Column(Text, nullable=True, doc="Plain text body content")
    body_html = Column(Text, nullable=True, doc="HTML body content")

    # Email dates
    sent_date = Column(DateTime(timezone=True), nullable=False, index=True,
                      doc="When the email was sent")
    received_date = Column(DateTime(timezone=True), nullable=False, index=True,
                           doc="When the email was received")

    # Gmail-specific metadata
    labels = Column(ARRAY(String), nullable=True, doc="Gmail labels applied to the message")
    is_read = Column(Boolean, default=False, doc="Whether the email has been read")
    is_starred = Column(Boolean, default=False, doc="Whether the email is starred")
    priority = Column(String(50), default="normal", doc="Email priority (low, normal, high)")

    # Size and attachment info
    size_bytes = Column(Integer, nullable=False, doc="Total size of the email in bytes")
    has_attachments = Column(Boolean, default=False, doc="Whether the email has attachments")
    attachment_count = Column(Integer, default=0, doc="Number of attachments")

    # Additional Gmail metadata stored as JSON
    gmail_metadata = Column(JSONB, nullable=True, doc="Additional Gmail-specific metadata")

    # Processing status
    processing_status = Column(String(50), default="pending",
                              doc="Processing status: pending, processing, completed, failed")
    processing_error = Column(Text, nullable=True, doc="Error message if processing failed")
    processed_at = Column(DateTime(timezone=True), nullable=True,
                         doc="When the email was last processed")

    # Relationships
    documents = relationship("Document", back_populates="email", cascade="all, delete-orphan")

    __table_args__ = {
        'comment': 'Stores Gmail message metadata and content'
    }


class Document(Base, TimestampMixin):
    """Document model for storing extracted attachments."""

    __tablename__ = "documents"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Email relationship
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"),
                     nullable=False, index=True, doc="Reference to the parent email")

    # Document metadata
    filename = Column(String(500), nullable=False, doc="Original filename")
    content_type = Column(String(255), nullable=False, doc="MIME content type")
    size_bytes = Column(Integer, nullable=False, doc="File size in bytes")

    # Storage information
    storage_path = Column(String(1000), nullable=False, doc="Path to stored file")
    storage_hash = Column(String(128), unique=True, nullable=False, index=True,
                         doc="SHA256 hash of the file content for deduplication")

    # Document content (extracted text)
    extracted_text = Column(Text, nullable=True, doc="Full text content extracted from the document")

    # Document metadata
    page_count = Column(Integer, nullable=True, doc="Number of pages in the document")
    word_count = Column(Integer, nullable=True, doc="Approximate word count")
    language = Column(String(10), nullable=True, doc="Detected language code")

    # Processing status
    processing_status = Column(String(50), default="pending",
                              doc="Processing status: pending, processing, completed, failed")
    processing_error = Column(Text, nullable=True, doc="Error message if processing failed")
    processed_at = Column(DateTime(timezone=True), nullable=True,
                         doc="When the document was last processed")

    # OCR information
    ocr_engine = Column(String(50), nullable=True, doc="OCR engine used for text extraction")
    ocr_confidence = Column(Integer, nullable=True, doc="Average OCR confidence score (0-100)")

    # Relationships
    email = relationship("Email", back_populates="documents")
    ocr_runs = relationship("OCRRun", back_populates="document", cascade="all, delete-orphan")
    document_pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = {
        'comment': 'Stores document attachments extracted from emails'
    }


class OCRRun(Base, TimestampMixin):
    """OCR processing run model."""

    __tablename__ = "ocr_runs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Document relationship
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"),
                        nullable=False, index=True, doc="Reference to the processed document")

    # OCR engine information
    ocr_engine = Column(String(50), nullable=False, doc="OCR engine used (tesseract, google, azure, mistral)")
    ocr_engine_version = Column(String(50), nullable=True, doc="Version of the OCR engine")

    # Processing configuration
    ocr_config = Column(JSONB, nullable=True, doc="Configuration parameters used for OCR processing")

    # Performance metrics
    processing_time_seconds = Column(Integer, nullable=True, doc="Total processing time in seconds")
    latency_ms = Column(Integer, nullable=True, doc="Processing latency in milliseconds")

    # Results and quality metrics
    status = Column(String(50), default="pending",
                   doc="Processing status: pending, processing, completed, failed")
    error_message = Column(Text, nullable=True, doc="Error message if processing failed")
    error_code = Column(String(100), nullable=True, doc="Error code for categorization")

    # Quality and accuracy metrics - matching PRD specification
    confidence_mean = Column(Integer, nullable=True, doc="Mean confidence score (0-100) as per PRD")
    pages_parsed = Column(Integer, nullable=True, doc="Number of pages successfully parsed")
    word_count = Column(Integer, nullable=True, doc="Total word count extracted")
    table_count = Column(Integer, nullable=True, doc="Number of tables detected")

    # Cost tracking (for cloud OCR services) - matching PRD specification
    cost_cents = Column(Integer, nullable=True, doc="Cost in cents (e.g., 100 = $1.00)")

    # Storage information for OCR results
    raw_response_storage_path = Column(String(1000), nullable=True,
                                      doc="Storage path for raw OCR engine response")

    # Processing timestamps
    started_at = Column(DateTime(timezone=True), nullable=True, doc="When OCR processing started")
    completed_at = Column(DateTime(timezone=True), nullable=True, doc="When OCR processing completed")

    # Relationships
    document = relationship("Document", back_populates="ocr_runs")
    document_pages = relationship("DocumentPage", back_populates="ocr_run", cascade="all, delete-orphan")

    __table_args__ = {
        'comment': 'Tracks individual OCR processing runs for documents'
    }


class DocumentPage(Base, TimestampMixin):
    """Individual document page model for storing OCR results."""

    __tablename__ = "document_pages"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"),
                        nullable=False, index=True, doc="Reference to the parent document")
    ocr_run_id = Column(Integer, ForeignKey("ocr_runs.id", ondelete="CASCADE"),
                       nullable=False, index=True, doc="Reference to the OCR run that produced this page")

    # Page information
    page_number = Column(Integer, nullable=False, doc="Page number within the document (1-based)")

    # Extracted content
    text_content = Column(Text, nullable=False, doc="Extracted text content from this page")
    word_count = Column(Integer, nullable=False, doc="Word count for this page")

    # OCR quality metrics for this page
    confidence_score = Column(Integer, nullable=True, doc="OCR confidence score for this page (0-100)")

    # Page-specific metadata
    page_metadata = Column(JSONB, nullable=True, doc="Additional page-specific metadata from OCR")

    # Relationships
    document = relationship("Document", back_populates="document_pages")
    ocr_run = relationship("OCRRun", back_populates="document_pages")

    __table_args__ = {
        'comment': 'Stores individual page text and metadata from OCR processing'
    }

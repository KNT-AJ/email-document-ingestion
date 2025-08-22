"""
Document Extraction and Storage Service

Service for extracting attachments from emails, storing them in blob storage with
deduplication based on SHA256 hashes, and creating document records in the database.
Handles various file types, file type detection, and text content extraction.
"""

import hashlib
import logging
import mimetypes
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, BinaryIO
try:
    import magic  # python-magic for file type detection
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False

import chardet  # for character encoding detection

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.email import Email, Document
from models.database import get_database_service
from services.blob_storage.service import create_blob_storage_service
from utils.logging import get_logger

logger = get_logger(__name__)


class DocumentExtractionService:
    """
    Service for extracting attachments from emails and storing them as documents.

    Features:
    - Extract attachments from email data
    - Compute SHA256 hashes for deduplication
    - Store files in blob storage
    - Create document records in database
    - Detect file types and extract metadata
    - Handle text content extraction where possible
    """

    # File types that typically contain extractable text
    TEXT_FILE_EXTENSIONS = {
        '.txt', '.csv', '.json', '.xml', '.html', '.htm', '.md', '.rtf',
        '.log', '.ini', '.conf', '.config', '.yml', '.yaml'
    }

    # MIME types that are likely to contain text
    TEXT_MIME_TYPES = {
        'text/', 'application/json', 'application/xml', 'application/rtf',
        'application/csv', 'application/x-yaml', 'application/yaml'
    }

    # File types to skip (temporary files, system files, etc.)
    SKIP_EXTENSIONS = {
        '.tmp', '.temp', '.swp', '.lock', '.DS_Store', '.Thumbs.db',
        '.desktop.ini', '.lnk', '.exe', '.bat', '.cmd', '.com', '.pif',
        '.scr', '.vbs', '.js', '.jse', '.jar', '.wsf', '.wsh'
    }

    def __init__(self):
        """Initialize the document extraction service."""
        self.db_service = get_database_service()
        self.blob_storage = create_blob_storage_service()

        # Initialize MIME type detection
        mimetypes.init()

    def extract_and_store_documents(self, email: Email, attachments_data: List[Dict[str, Any]]) -> List[Document]:
        """
        Extract attachments from email and store them as documents.

        Args:
            email: Email instance
            attachments_data: List of attachment data from Gmail API

        Returns:
            List of created Document instances
        """
        documents = []
        logger.info(f"Processing {len(attachments_data)} attachments for email {email.gmail_message_id}")

        for attachment_data in attachments_data:
            try:
                document = self._process_attachment(email, attachment_data)
                if document:
                    documents.append(document)
                    logger.info(f"Successfully processed attachment: {attachment_data.get('filename', 'unknown')}")

            except Exception as e:
                attachment_name = attachment_data.get('filename', 'unknown')
                logger.error(f"Failed to process attachment {attachment_name}: {e}")
                continue

        logger.info(f"Successfully created {len(documents)} documents for email {email.gmail_message_id}")
        return documents

    def _process_attachment(self, email: Email, attachment_data: Dict[str, Any]) -> Optional[Document]:
        """
        Process a single attachment and create a document record.

        Args:
            email: Parent email instance
            attachment_data: Attachment data from Gmail API

        Returns:
            Document instance if successful, None otherwise
        """
        try:
            # Extract attachment metadata
            filename = attachment_data.get('filename', 'unnamed_attachment')
            mime_type = attachment_data.get('mimeType', 'application/octet-stream')
            size_bytes = attachment_data.get('size', 0)
            attachment_id = attachment_data.get('attachmentId')

            # Skip files we don't want to process
            if self._should_skip_file(filename, mime_type):
                logger.debug(f"Skipping file: {filename} ({mime_type})")
                return None

            # Get attachment content
            attachment_content = attachment_data.get('data')
            if not attachment_content:
                logger.warning(f"No content available for attachment: {filename}")
                return None

            # Convert base64 data to bytes
            import base64
            file_data = base64.b64decode(attachment_content)

            # Compute SHA256 hash for deduplication
            file_hash = self._compute_sha256_hash(file_data)

            # Check if document with this hash already exists
            existing_document = self._find_existing_document_by_hash(file_hash)
            if existing_document:
                logger.info(f"Document with hash {file_hash} already exists: {existing_document.filename}")
                return existing_document

            # Store file in blob storage
            storage_path = self._store_file_in_blob_storage(file_data, filename, file_hash)

            # Extract metadata and text content
            metadata = self._extract_file_metadata(filename, file_data, mime_type)
            extracted_text = self._extract_text_content(filename, file_data, mime_type)

            # Create document record
            document = self._create_document_record(
                email_id=email.id,
                filename=filename,
                content_type=mime_type,
                size_bytes=size_bytes,
                storage_path=storage_path,
                storage_hash=file_hash,
                extracted_text=extracted_text,
                metadata=metadata
            )

            return document

        except Exception as e:
            logger.error(f"Error processing attachment {attachment_data.get('filename', 'unknown')}: {e}")
            return None

    def _should_skip_file(self, filename: str, mime_type: str) -> bool:
        """
        Determine if a file should be skipped based on filename and MIME type.

        Args:
            filename: Name of the file
            mime_type: MIME type of the file

        Returns:
            True if file should be skipped, False otherwise
        """
        # Check file extension
        file_extension = Path(filename).suffix.lower()
        if file_extension in self.SKIP_EXTENSIONS:
            return True

        # Check filename patterns (case-insensitive)
        filename_lower = filename.lower()
        skip_patterns = ['thumbs.db', '.ds_store', 'desktop.ini', '~$']
        for pattern in skip_patterns:
            if pattern in filename_lower:
                return True

        # Skip very small files (likely temporary or empty)
        # Skip very large files (configurable limit)
        # These checks would be done with actual file size

        # Skip certain MIME types
        if mime_type in ['application/x-msdownload', 'application/x-executable']:
            return True

        return False

    def _compute_sha256_hash(self, file_data: bytes) -> str:
        """
        Compute SHA256 hash of file content for deduplication.

        Args:
            file_data: Binary file content

        Returns:
            SHA256 hash as hex string
        """
        hash_obj = hashlib.sha256()
        hash_obj.update(file_data)
        return hash_obj.hexdigest()

    def _find_existing_document_by_hash(self, file_hash: str) -> Optional[Document]:
        """
        Find existing document by its hash.

        Args:
            file_hash: SHA256 hash of the file

        Returns:
            Document instance if found, None otherwise
        """
        try:
            with self.db_service.get_session() as session:
                return session.query(Document).filter(
                    Document.storage_hash == file_hash
                ).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error finding document by hash {file_hash}: {e}")
            return None

    def _store_file_in_blob_storage(self, file_data: bytes, filename: str, file_hash: str) -> str:
        """
        Store file in blob storage and return the storage path.

        Args:
            file_data: Binary file content
            filename: Original filename
            file_hash: SHA256 hash of the file

        Returns:
            Storage path where file was stored
        """
        # Create a consistent storage path based on hash
        # Format: documents/{first-2-chars}/{next-2-chars}/{hash}/{filename}
        hash_prefix_1 = file_hash[:2]
        hash_prefix_2 = file_hash[2:4]
        storage_path = f"documents/{hash_prefix_1}/{hash_prefix_2}/{file_hash}/{filename}"

        # Convert bytes to file-like object for blob storage
        file_obj = BytesIO(file_data)

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(filename)

        try:
            # Upload to blob storage
            actual_path = self.blob_storage.upload_blob(storage_path, file_obj, mime_type)
            logger.debug(f"Stored file {filename} at {actual_path}")
            return actual_path

        except Exception as e:
            logger.error(f"Failed to store file {filename} in blob storage: {e}")
            raise

    def _extract_file_metadata(self, filename: str, file_data: bytes, mime_type: str) -> Dict[str, Any]:
        """
        Extract metadata from file content.

        Args:
            filename: Name of the file
            file_data: Binary file content
            mime_type: MIME type of the file

        Returns:
            Dictionary containing file metadata
        """
        metadata = {
            'original_filename': filename,
            'detected_mime_type': mime_type,
            'file_size_bytes': len(file_data)
        }

        try:
            # Detect MIME type using python-magic if available
            if MAGIC_AVAILABLE and magic:
                detected_mime = magic.from_buffer(file_data, mime=True)
                if detected_mime and detected_mime != mime_type:
                    metadata['magic_detected_mime_type'] = detected_mime
                    mime_type = detected_mime  # Use detected MIME type for further processing

            # Get file extension
            file_extension = Path(filename).suffix.lower()
            metadata['file_extension'] = file_extension

            # Determine if file is likely to contain text
            metadata['likely_contains_text'] = self._is_text_file(filename, mime_type)

            # Try to detect character encoding for text files
            if metadata['likely_contains_text'] and len(file_data) > 0:
                detected_encoding = chardet.detect(file_data)
                if detected_encoding and detected_encoding.get('confidence', 0) > 0.7:
                    metadata['detected_encoding'] = detected_encoding.get('encoding')
                    metadata['encoding_confidence'] = detected_encoding.get('confidence')

            # Additional metadata based on file type
            if mime_type.startswith('image/'):
                # Could add image dimensions, format, etc.
                metadata['file_type'] = 'image'
            elif mime_type.startswith('application/pdf'):
                metadata['file_type'] = 'pdf'
            elif mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                metadata['file_type'] = 'word_document'
            elif mime_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                metadata['file_type'] = 'spreadsheet'
            elif mime_type.startswith('text/') or file_extension in self.TEXT_FILE_EXTENSIONS:
                metadata['file_type'] = 'text'
            else:
                metadata['file_type'] = 'binary'

        except Exception as e:
            logger.warning(f"Error extracting metadata from {filename}: {e}")
            metadata['metadata_extraction_error'] = str(e)

        return metadata

    def _is_text_file(self, filename: str, mime_type: str) -> bool:
        """
        Determine if a file is likely to contain extractable text.

        Args:
            filename: Name of the file
            mime_type: MIME type of the file

        Returns:
            True if file likely contains text, False otherwise
        """
        # Check MIME type
        if mime_type:
            for text_mime in self.TEXT_MIME_TYPES:
                if mime_type.startswith(text_mime):
                    return True

        # Check file extension
        file_extension = Path(filename).suffix.lower()
        if file_extension in self.TEXT_FILE_EXTENSIONS:
            return True

        return False

    def _extract_text_content(self, filename: str, file_data: bytes, mime_type: str) -> Optional[str]:
        """
        Extract text content from file if possible.

        Args:
            filename: Name of the file
            file_data: Binary file content
            mime_type: MIME type of the file

        Returns:
            Extracted text content or None if not extractable
        """
        try:
            # Only extract text from files that are likely to contain text
            if not self._is_text_file(filename, mime_type):
                return None

            # Try to decode as text
            encoding = self._detect_encoding(file_data)
            if encoding:
                try:
                    text_content = file_data.decode(encoding)
                    # Limit text content to reasonable size
                    if len(text_content) > 1000000:  # 1MB limit
                        text_content = text_content[:1000000] + "\n[CONTENT TRUNCATED - TOO LARGE]"
                    return text_content
                except UnicodeDecodeError:
                    logger.warning(f"Failed to decode text content from {filename} with encoding {encoding}")

            # Fallback: try common encodings
            for fallback_encoding in ['utf-8', 'latin1', 'cp1252']:
                try:
                    text_content = file_data.decode(fallback_encoding)
                    logger.info(f"Successfully decoded {filename} using fallback encoding {fallback_encoding}")
                    return text_content[:1000000] if len(text_content) > 1000000 else text_content
                except UnicodeDecodeError:
                    continue

            logger.warning(f"Could not extract text content from {filename}")
            return None

        except Exception as e:
            logger.error(f"Error extracting text content from {filename}: {e}")
            return None

    def _detect_encoding(self, file_data: bytes) -> Optional[str]:
        """
        Detect character encoding of file content.

        Args:
            file_data: Binary file content

        Returns:
            Detected encoding or None if detection failed
        """
        try:
            # Use chardet for encoding detection
            result = chardet.detect(file_data)
            if result and result.get('confidence', 0) > 0.7:
                return result.get('encoding')
        except Exception as e:
            logger.debug(f"Encoding detection failed: {e}")

        return None

    def _create_document_record(self, **kwargs) -> Document:
        """
        Create a document record in the database.

        Args:
            **kwargs: Document attributes

        Returns:
            Created Document instance
        """
        try:
            with self.db_service.get_session() as session:
                # Extract metadata
                metadata = kwargs.get('metadata', {})

                # Create document instance
                document = Document(
                    email_id=kwargs['email_id'],
                    filename=kwargs['filename'][:500],  # Truncate filename if too long
                    content_type=kwargs['content_type'][:255],  # Truncate MIME type if too long
                    size_bytes=kwargs['size_bytes'],
                    storage_path=kwargs['storage_path'][:1000],  # Truncate path if too long
                    storage_hash=kwargs['storage_hash'],
                    extracted_text=kwargs.get('extracted_text'),
                    page_count=metadata.get('page_count'),
                    word_count=metadata.get('word_count'),
                    language=metadata.get('language'),
                    processing_status='pending'
                )

                session.add(document)
                session.commit()
                session.refresh(document)

                logger.debug(f"Created document record: {document.id} for file {document.filename}")
                return document

        except SQLAlchemyError as e:
            logger.error(f"Database error creating document record: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating document record: {e}")
            raise

    def get_documents_by_email(self, email_id: int) -> List[Document]:
        """
        Get all documents for a specific email.

        Args:
            email_id: Email ID

        Returns:
            List of Document instances
        """
        try:
            with self.db_service.get_session() as session:
                return session.query(Document).filter(
                    Document.email_id == email_id
                ).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error getting documents for email {email_id}: {e}")
            return []

    def get_document_by_hash(self, file_hash: str) -> Optional[Document]:
        """
        Get document by its hash.

        Args:
            file_hash: SHA256 hash of the file

        Returns:
            Document instance if found, None otherwise
        """
        try:
            with self.db_service.get_session() as session:
                return session.query(Document).filter(
                    Document.storage_hash == file_hash
                ).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error getting document by hash {file_hash}: {e}")
            return None

    def update_document_status(self, document_id: int, status: str,
                             error_message: Optional[str] = None) -> bool:
        """
        Update the processing status of a document.

        Args:
            document_id: Document ID
            status: New processing status
            error_message: Error message if status is 'failed'

        Returns:
            True if update successful, False otherwise
        """
        try:
            with self.db_service.get_session() as session:
                document = session.query(Document).filter(Document.id == document_id).first()
                if not document:
                    logger.warning(f"Document {document_id} not found for status update")
                    return False

                document.processing_status = status
                document.processed_at = datetime.now(timezone.utc)

                if error_message:
                    document.processing_error = error_message

                session.commit()
                logger.info(f"Updated document {document_id} status to {status}")
                return True

        except SQLAlchemyError as e:
            logger.error(f"Database error updating document {document_id} status: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating document {document_id} status: {e}")
            return False


# Global service instance
_extraction_service = None

def get_document_extraction_service() -> DocumentExtractionService:
    """Get the global document extraction service instance."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = DocumentExtractionService()
    return _extraction_service

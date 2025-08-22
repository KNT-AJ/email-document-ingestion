"""Google Document AI service for OCR processing."""

import json
import time
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import tempfile
import functools

from google.cloud import documentai_v1 as documentai
from google.api_core.exceptions import GoogleAPIError, RetryError
from google.auth.exceptions import GoogleAuthError
from google.api_core.retry import Retry

from config import get_settings
from services.blob_storage.interface import BlobStorageInterface
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GoogleDocumentAIError(Exception):
    """Custom exception for Google Document AI errors."""
    pass


def retry_on_google_api_error(max_retries=3, initial_delay=1.0, max_delay=60.0):
    """Decorator to retry Google API calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (GoogleAPIError, RetryError) as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            "Max retries exceeded for Google API call",
                            function=func.__name__,
                            attempt=attempt + 1,
                            error=str(e)
                        )
                        break

                    # Check if error is retryable
                    if hasattr(e, 'code') and e.code in [429, 500, 502, 503, 504]:  # Rate limit and server errors
                        logger.warning(
                            "Retrying Google API call after error",
                            function=func.__name__,
                            attempt=attempt + 1,
                            error=str(e),
                            delay=delay
                        )
                        time.sleep(delay)
                        delay = min(delay * 2, max_delay)  # Exponential backoff
                    else:
                        # Non-retryable error
                        raise e

            # If we get here, all retries failed
            raise GoogleDocumentAIError(f"Google API call failed after {max_retries + 1} attempts: {str(last_exception)}")

        return wrapper
    return decorator


class GoogleDocumentAIService:
    """Service for processing documents using Google Document AI."""

    def __init__(self, storage_service: Optional[BlobStorageInterface] = None):
        """Initialize Google Document AI service.

        Args:
            storage_service: Optional blob storage service for storing raw responses
        """
        self.storage_service = storage_service
        self._client = None
        self._processor = None

        # Initialize client and processor
        self._setup_client()

    def _setup_client(self):
        """Set up Google Document AI client and processor."""
        try:
            if not settings.GOOGLE_CREDENTIALS_PATH:
                raise GoogleDocumentAIError("GOOGLE_CREDENTIALS_PATH not configured")

            if not settings.GOOGLE_DOCUMENT_AI_ENDPOINT:
                raise GoogleDocumentAIError("GOOGLE_DOCUMENT_AI_ENDPOINT not configured")

            # Initialize client
            self._client = documentai.DocumentProcessorServiceClient.from_service_account_file(
                settings.GOOGLE_CREDENTIALS_PATH
            )

            # Parse endpoint to get processor details
            # Format: projects/{project}/locations/{location}/processors/{processor}
            self._processor_name = settings.GOOGLE_DOCUMENT_AI_ENDPOINT

            logger.info("Google Document AI client initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize Google Document AI client", error=str(e))
            raise GoogleDocumentAIError(f"Failed to initialize client: {str(e)}")

    @retry_on_google_api_error(max_retries=3, initial_delay=1.0, max_delay=32.0)
    def process_document(
        self,
        document_path: str,
        mime_type: str = "application/pdf",
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a document using Google Document AI.

        Args:
            document_path: Path to the document file
            mime_type: MIME type of the document
            document_id: Optional document ID for tracking

        Returns:
            Dictionary containing extracted text, tables, key-value pairs, and metrics

        Raises:
            GoogleDocumentAIError: If processing fails
        """
        start_time = time.time()

        try:
            logger.info(
                "Starting Google Document AI processing",
                document_path=document_path,
                mime_type=mime_type,
                document_id=document_id
            )

            # Load document content
            with open(document_path, 'rb') as f:
                document_content = f.read()

            # Create Document AI document
            document = documentai.Document()
            document.content = document_content
            document.mime_type = mime_type

            # Create processing request
            request = documentai.ProcessRequest(
                name=self._processor_name,
                document=document
            )

            # Process document
            logger.info("Sending document to Google Document AI for processing")
            response = self._client.process_document(request=request)
            document = response.document

            # Calculate processing time
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content from response
            extracted_text = self._extract_text(document)
            tables = self._extract_tables(document)
            key_value_pairs = self._extract_key_value_pairs(document)

            # Calculate metrics
            confidence_score = self._calculate_confidence_score(document)
            pages_count = len(document.pages) if document.pages else 0
            word_count = len(extracted_text.split()) if extracted_text else 0

            # Prepare result
            result = {
                'extracted_text': extracted_text,
                'tables': tables,
                'key_value_pairs': key_value_pairs,
                'confidence_score': confidence_score,
                'pages_count': pages_count,
                'word_count': word_count,
                'latency_ms': latency_ms,
                'engine': 'google_document_ai',
                'raw_response': self._serialize_document(document)
            }

            # Store raw response in blob storage if available
            if self.storage_service:
                raw_response_path = self._store_raw_response(
                    document_id or f"doc_{int(time.time())}",
                    result['raw_response']
                )
                result['raw_response_path'] = raw_response_path

            logger.info(
                "Google Document AI processing completed successfully",
                document_id=document_id,
                pages_count=pages_count,
                word_count=word_count,
                confidence_score=confidence_score,
                latency_ms=latency_ms
            )

            return result

        except (GoogleAPIError, GoogleAuthError) as e:
            logger.error(
                "Google Document AI API error",
                error=str(e),
                document_id=document_id
            )
            raise GoogleDocumentAIError(f"Google API error: {str(e)}")

        except Exception as e:
            logger.error(
                "Unexpected error in Google Document AI processing",
                error=str(e),
                document_id=document_id
            )
            raise GoogleDocumentAIError(f"Processing failed: {str(e)}")

    def _extract_text(self, document: documentai.Document) -> str:
        """Extract plain text from Document AI response.

        Args:
            document: Processed Document AI document

        Returns:
            Extracted plain text
        """
        if not document.text:
            return ""

        # Get the full text content
        full_text = document.text

        # If there are pages with structured text, use that for better formatting
        if document.pages:
            extracted_texts = []
            for page in document.pages:
                page_text = self._extract_text_from_page(page)
                if page_text:
                    extracted_texts.append(page_text)

            if extracted_texts:
                return "\n\n".join(extracted_texts)

        return full_text

    def _extract_text_from_page(self, page: documentai.Page) -> str:
        """Extract text from a single page.

        Args:
            page: Document AI page object

        Returns:
            Extracted text from the page
        """
        if not page.blocks:
            return ""

        # Sort blocks by reading order
        sorted_blocks = sorted(page.blocks, key=lambda b: (
            (b.layout.bounding_poly.vertices[0].y + b.layout.bounding_poly.vertices[2].y) / 2,
            b.layout.bounding_poly.vertices[0].x
        ))

        page_text = []
        for block in sorted_blocks:
            if block.text_anchor and block.text_anchor.text_segments:
                # Get text from the text segments
                block_text = ""
                for segment in block.text_anchor.text_segments:
                    start_index = segment.start_index or 0
                    end_index = segment.end_index or len(block.text_anchor.text_segments)
                    if end_index <= start_index:
                        continue
                    block_text += block.text_anchor.text_segments[0].text[start_index:end_index]

                if block_text.strip():
                    page_text.append(block_text.strip())

        return "\n".join(page_text)

    def _extract_tables(self, document: documentai.Document) -> list:
        """Extract tables from Document AI response.

        Args:
            document: Processed Document AI document

        Returns:
            List of extracted tables as dictionaries
        """
        tables = []

        if not document.pages:
            return tables

        for page_num, page in enumerate(document.pages):
            if not page.tables:
                continue

            for table_num, table in enumerate(page.tables):
                table_data = self._extract_table_data(table, page)
                if table_data:
                    tables.append({
                        'page': page_num + 1,
                        'table_number': table_num + 1,
                        'data': table_data,
                        'confidence': getattr(table, 'confidence', 0.0)
                    })

        return tables

    def _extract_table_data(self, table, page):
        """Extract data from a single table.

        Args:
            table: Document AI table object
            page: Parent page object

        Returns:
            Table data as list of lists
        """
        if not table.header_rows or not table.body_rows:
            return []

        # Extract headers
        headers = []
        for cell in table.header_rows[0].cells:
            headers.append(self._extract_cell_text(cell, page))

        # Extract body rows
        body_rows = []
        for row in table.body_rows:
            row_data = []
            for cell in row.cells:
                row_data.append(self._extract_cell_text(cell, page))
            body_rows.append(row_data)

        return [headers] + body_rows

    def _extract_cell_text(self, cell, page):
        """Extract text from a table cell.

        Args:
            cell: Document AI table cell
            page: Parent page object

        Returns:
            Extracted cell text
        """
        if not cell.layout or not cell.layout.text_anchor:
            return ""

        return self._extract_text_from_text_anchor(cell.layout.text_anchor, page)

    def _extract_text_from_text_anchor(self, text_anchor, page):
        """Extract text from a text anchor.

        Args:
            text_anchor: Document AI text anchor
            page: Parent page object

        Returns:
            Extracted text
        """
        if not text_anchor.text_segments:
            return ""

        text = ""
        for segment in text_anchor.text_segments:
            start_index = segment.start_index or 0
            end_index = segment.end_index or len(text_anchor.text_segments)
            if end_index <= start_index:
                continue
            # Get text from the page's text content
            segment_text = page.text[start_index:end_index]
            text += segment_text

        return text.strip()

    def _extract_key_value_pairs(self, document: documentai.Document) -> list:
        """Extract key-value pairs from Document AI response.

        Args:
            document: Processed Document AI document

        Returns:
            List of extracted key-value pairs
        """
        kv_pairs = []

        if not document.entities:
            return kv_pairs

        for entity in document.entities:
            if entity.type_ and entity.mention_text:
                kv_pairs.append({
                    'key': entity.type_,
                    'value': entity.mention_text,
                    'confidence': getattr(entity, 'confidence', 0.0)
                })

        return kv_pairs

    def _calculate_confidence_score(self, document: documentai.Document) -> float:
        """Calculate overall confidence score for the document.

        Args:
            document: Processed Document AI document

        Returns:
            Average confidence score (0.0 to 1.0)
        """
        if not document.pages:
            return 0.0

        total_confidence = 0.0
        page_count = 0

        for page in document.pages:
            if hasattr(page, 'confidence') and page.confidence is not None:
                total_confidence += page.confidence
                page_count += 1

        if page_count == 0:
            return 0.0

        return total_confidence / page_count

    def _serialize_document(self, document: documentai.Document) -> Dict[str, Any]:
        """Serialize Document AI document to dictionary.

        Args:
            document: Document AI document object

        Returns:
            Dictionary representation of the document
        """
        # Convert document to dictionary for storage
        # This is a simplified serialization - in practice you might want more details
        return {
            'text': document.text,
            'pages': [
                {
                    'page_number': i + 1,
                    'width': page.dimension.width if page.dimension else None,
                    'height': page.dimension.height if page.dimension else None,
                    'confidence': getattr(page, 'confidence', None),
                    'blocks_count': len(page.blocks) if page.blocks else 0,
                    'tables_count': len(page.tables) if page.tables else 0,
                    'paragraphs_count': len(page.paragraphs) if page.paragraphs else 0
                }
                for i, page in enumerate(document.pages or [])
            ],
            'entities': [
                {
                    'type': entity.type_,
                    'mention_text': entity.mention_text,
                    'confidence': getattr(entity, 'confidence', None)
                }
                for entity in document.entities or []
            ]
        }

    def _store_raw_response(self, document_id: str, raw_response: Dict[str, Any]) -> str:
        """Store raw Document AI response in blob storage.

        Args:
            document_id: Document identifier
            raw_response: Raw response dictionary

        Returns:
            Storage path for the raw response
        """
        if not self.storage_service:
            raise GoogleDocumentAIError("Storage service not available")

        try:
            # Create blob path
            blob_path = f"ocr-runs/google-document-ai/{document_id}/raw_response.json"

            # Convert to JSON and store
            json_data = json.dumps(raw_response, indent=2)
            self.storage_service.upload_string(json_data, blob_path, "application/json")

            logger.info(
                "Raw Document AI response stored",
                document_id=document_id,
                blob_path=blob_path
            )

            return blob_path

        except Exception as e:
            logger.error(
                "Failed to store raw Document AI response",
                error=str(e),
                document_id=document_id
            )
            raise GoogleDocumentAIError(f"Storage failed: {str(e)}")

    def health_check(self) -> Dict[str, Any]:
        """Check if Google Document AI service is healthy.

        Returns:
            Dictionary with health check results
        """
        try:
            if not self._client:
                return {
                    'status': 'unhealthy',
                    'error': 'Client not initialized'
                }

            # Try to get processor info (lightweight operation)
            request = documentai.GetProcessorRequest(name=self._processor_name)
            processor = self._client.get_processor(request=request)

            return {
                'status': 'healthy',
                'processor_name': processor.name,
                'processor_state': processor.state.name if processor.state else 'UNKNOWN'
            }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

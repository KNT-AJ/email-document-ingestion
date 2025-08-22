"""OCR run tracking service for managing OCR processing runs and their results."""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from models.email import OCRRun, Document
from models.database import get_db
from services.blob_storage import OCRBlobStorageService
from config.settings import settings


logger = logging.getLogger(__name__)


class OCRRunService:
    """Service for managing OCR runs, metrics, and persistence."""

    def __init__(self, db: Session, ocr_storage: OCRBlobStorageService):
        """
        Initialize OCR run service.

        Args:
            db: Database session
            ocr_storage: OCR blob storage service for raw responses
        """
        self.db = db
        self.ocr_storage = ocr_storage

    def create_ocr_run(self, document_id: int, ocr_engine: str, ocr_config: Optional[Dict[str, Any]] = None) -> OCRRun:
        """
        Create a new OCR run record.

        Args:
            document_id: ID of the document to process
            ocr_engine: Name of the OCR engine being used
            ocr_config: Optional configuration parameters

        Returns:
            Created OCRRun instance

        Raises:
            ValueError: If document doesn't exist
        """
        # Verify document exists
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document with ID {document_id} not found")

        # Create OCR run record
        ocr_run = OCRRun(
            document_id=document_id,
            ocr_engine=ocr_engine,
            ocr_config=ocr_config,
            status="pending"
        )

        self.db.add(ocr_run)
        self.db.commit()
        self.db.refresh(ocr_run)

        logger.info(
            f"Created OCR run {ocr_run.id} for document {document_id} "
            f"using engine {ocr_engine}"
        )

        return ocr_run

    def update_ocr_run_status(
        self,
        run_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> OCRRun:
        """
        Update OCR run status.

        Args:
            run_id: OCR run ID
            status: New status (pending, running, completed, failed)
            error_message: Optional error message if status is 'failed'

        Returns:
            Updated OCRRun instance

        Raises:
            ValueError: If OCR run doesn't exist
        """
        ocr_run = self.db.query(OCRRun).filter(OCRRun.id == run_id).first()
        if not ocr_run:
            raise ValueError(f"OCR run with ID {run_id} not found")

        old_status = ocr_run.status
        ocr_run.status = status

        # Set timestamps based on status
        now = datetime.utcnow()
        if status == "running" and ocr_run.started_at is None:
            ocr_run.started_at = now
        elif status in ["completed", "failed"]:
            ocr_run.completed_at = now

        # Handle error message
        if status == "failed":
            ocr_run.error_message = error_message

        self.db.commit()
        self.db.refresh(ocr_run)

        logger.info(
            f"Updated OCR run {run_id} status: {old_status} -> {status}"
        )

        return ocr_run

    def complete_ocr_run(
        self,
        run_id: int,
        metrics: Dict[str, Any],
        json_response: Dict[str, Any]
    ) -> OCRRun:
        """
        Mark OCR run as completed with metrics and store JSON response.

        Args:
            run_id: OCR run ID
            metrics: Dictionary containing processing metrics
            json_response: Raw JSON response from OCR engine

        Returns:
            Updated OCRRun instance

        Raises:
            ValueError: If OCR run doesn't exist
        """
        ocr_run = self.db.query(OCRRun).filter(OCRRun.id == run_id).first()
        if not ocr_run:
            raise ValueError(f"OCR run with ID {run_id} not found")

        # Update status and metrics
        ocr_run.status = "completed"
        ocr_run.completed_at = datetime.utcnow()

        # Store metrics - updated to match PRD field names
        if "latency_ms" in metrics:
            ocr_run.latency_ms = metrics["latency_ms"]
        if "cost_cents" in metrics:
            ocr_run.cost_cents = metrics["cost_cents"]
        if "confidence_mean" in metrics:
            ocr_run.confidence_mean = metrics["confidence_mean"]
        if "pages_parsed" in metrics:
            ocr_run.pages_parsed = metrics["pages_parsed"]
        if "word_count" in metrics:
            ocr_run.word_count = metrics["word_count"]
        if "table_count" in metrics:
            ocr_run.table_count = metrics["table_count"]
        if "processing_time_seconds" in metrics:
            ocr_run.processing_time_seconds = metrics["processing_time_seconds"]

        # Store JSON response in blob storage
        try:
            blob_path = self.ocr_storage.store_ocr_response(
                run_id, json_response, ocr_run.ocr_engine
            )
            ocr_run.raw_response_storage_path = blob_path
        except Exception as e:
            logger.error(f"Failed to store OCR response for run {run_id}: {e}")
            # Continue without failing the entire operation

        self.db.commit()
        self.db.refresh(ocr_run)

        logger.info(
            f"Completed OCR run {run_id} with metrics: "
            f"confidence={ocr_run.confidence_mean}, "
            f"pages={ocr_run.pages_parsed}, "
            f"words={ocr_run.word_count}"
        )

        return ocr_run

    def fail_ocr_run(self, run_id: int, error_message: str) -> OCRRun:
        """
        Mark OCR run as failed with error message.

        Args:
            run_id: OCR run ID
            error_message: Error message describing the failure

        Returns:
            Updated OCRRun instance

        Raises:
            ValueError: If OCR run doesn't exist
        """
        return self.update_ocr_run_status(run_id, "failed", error_message)

    def get_ocr_run(self, run_id: int) -> Optional[OCRRun]:
        """
        Get OCR run by ID.

        Args:
            run_id: OCR run ID

        Returns:
            OCRRun instance if found, None otherwise
        """
        return self.db.query(OCRRun).filter(OCRRun.id == run_id).first()

    def get_ocr_runs_by_document(self, document_id: int, limit: int = 10) -> List[OCRRun]:
        """
        Get OCR runs for a specific document.

        Args:
            document_id: Document ID
            limit: Maximum number of runs to return

        Returns:
            List of OCRRun instances
        """
        return (
            self.db.query(OCRRun)
            .filter(OCRRun.document_id == document_id)
            .order_by(OCRRun.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_ocr_runs_by_status(self, status: str, limit: int = 100) -> List[OCRRun]:
        """
        Get OCR runs by status.

        Args:
            status: Status to filter by
            limit: Maximum number of runs to return

        Returns:
            List of OCRRun instances
        """
        return (
            self.db.query(OCRRun)
            .filter(OCRRun.status == status)
            .order_by(OCRRun.created_at.desc())
            .limit(limit)
            .all()
        )

    def calculate_metrics(self, start_time: datetime, json_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate processing metrics from start time and JSON response.

        Args:
            start_time: When processing started
            json_response: Raw JSON response from OCR engine

        Returns:
            Dictionary containing calculated metrics
        """
        end_time = datetime.utcnow()
        processing_time = end_time - start_time

        metrics = {
            "latency_ms": int(processing_time.total_seconds() * 1000),
            "processing_time_seconds": processing_time.total_seconds()
        }

        # Extract metrics from JSON response if available
        # This will vary depending on the OCR engine format
        if isinstance(json_response, dict):
            # Look for common OCR response patterns - updated field names
            if "confidence" in json_response:
                metrics["confidence_mean"] = json_response["confidence"]
            elif "document" in json_response and "confidence" in json_response["document"]:
                metrics["confidence_mean"] = json_response["document"]["confidence"]

            # Count pages
            if "pages" in json_response:
                metrics["pages_parsed"] = len(json_response["pages"])
            elif "document" in json_response and "pages" in json_response["document"]:
                metrics["pages_parsed"] = len(json_response["document"]["pages"])

            # Estimate word count
            word_count = 0
            if "pages" in json_response:
                for page in json_response["pages"]:
                    if "text" in page:
                        word_count += len(page["text"].split())
            elif "document" in json_response and "pages" in json_response["document"]:
                for page in json_response["document"]["pages"]:
                    if "text" in page:
                        word_count += len(page["text"].split())

            if word_count > 0:
                metrics["word_count"] = word_count

        return metrics


def create_ocr_run_service(
    db: Optional[Session] = None,
    ocr_storage: Optional[OCRBlobStorageService] = None
) -> OCRRunService:
    """
    Factory function to create an OCR run service.

    Args:
        db: Optional database session (creates new one if not provided)
        ocr_storage: Optional OCR blob storage service (creates new one if not provided)

    Returns:
        Configured OCR run service
    """
    if db is None:
        db = next(get_db())

    if ocr_storage is None:
        from services.blob_storage import create_ocr_blob_storage_service
        ocr_storage = create_ocr_blob_storage_service()

    return OCRRunService(db, ocr_storage)

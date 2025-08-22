"""Reprocessing API routes for documents and emails."""

from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, validator
import uuid
from datetime import datetime

from config import get_settings
from utils.logging import get_logger

router = APIRouter()
logger = get_logger("api.reprocess")
settings = get_settings()


class ReprocessDocumentRequest(BaseModel):
    """Request model for document reprocessing."""

    ocr_engine: Optional[str] = Query(
        None, description="Specific OCR engine to use (e.g., 'azure', 'google', 'tesseract')"
    )
    workflow_config: Optional[str] = Query(
        "azure_primary", description="Workflow configuration name"
    )
    priority: str = Query("normal", description="Processing priority (high, normal, low)")

    class Config:
        validate_assignment = True

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['high', 'normal', 'low']:
            raise ValueError("Priority must be one of: high, normal, low")
        return v

    @validator('ocr_engine')
    def validate_ocr_engine(cls, v):
        if v is not None:
            valid_engines = ['azure', 'google', 'tesseract', 'mistral', 'easyocr']
            if v not in valid_engines:
                raise ValueError(f"OCR engine must be one of: {', '.join(valid_engines)}")
        return v


class ReprocessEmailRequest(BaseModel):
    """Request model for email reprocessing."""

    ocr_engine: Optional[str] = Query(
        None, description="Specific OCR engine to use for attachments"
    )
    workflow_config: Optional[str] = Query(
        "azure_primary", description="Workflow configuration name"
    )
    process_attachments: bool = Query(True, description="Whether to reprocess attachments")
    priority: str = Query("normal", description="Processing priority (high, normal, low)")

    class Config:
        validate_assignment = True

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['high', 'normal', 'low']:
            raise ValueError("Priority must be one of: high, normal, low")
        return v

    @validator('ocr_engine')
    def validate_ocr_engine(cls, v):
        if v is not None:
            valid_engines = ['azure', 'google', 'tesseract', 'mistral', 'easyocr']
            if v not in valid_engines:
                raise ValueError(f"OCR engine must be one of: {', '.join(valid_engines)}")
        return v


class ReprocessResponse(BaseModel):
    """Response model for reprocessing requests."""

    job_id: str
    status: str
    message: str
    item_type: str  # "document" or "email"
    item_id: int


class ReprocessStatus(BaseModel):
    """Status model for reprocessing jobs."""

    job_id: str
    status: str
    progress: float
    message: str
    item_type: str
    item_id: int
    created_at: str
    updated_at: str


@router.post("/document/{document_id}", response_model=ReprocessResponse)
async def reprocess_document(
    document_id: int,
    request: ReprocessDocumentRequest,
    background_tasks: BackgroundTasks
):
    """Reprocess a document with OCR.

    This endpoint allows reprocessing a specific document with optional
    OCR engine selection for comparison or forced reprocessing.

    Args:
        document_id: Database ID of the document to reprocess
        request: Reprocessing configuration including OCR engine and workflow
        background_tasks: FastAPI background tasks for async processing

    Returns:
        ReprocessResponse with job details
    """
    try:
        # Generate a job ID
        job_id = str(uuid.uuid4())

        logger.info(
            "Document reprocessing request received",
            job_id=job_id,
            document_id=document_id,
            ocr_engine=request.ocr_engine,
            workflow_config=request.workflow_config,
            priority=request.priority
        )

        # Validate document exists
        from models.database import get_db_session
        from models.email import Document

        with get_db_session() as db:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

            # Check if document has a valid file path
            if not document.storage_path:
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {document_id} has no valid storage path"
                )

        # Queue the reprocessing task
        from workers.tasks.ocr_workflow import reprocess_document_ocr

        # Prepare workflow overrides if OCR engine is specified
        workflow_overrides = None
        if request.ocr_engine:
            workflow_overrides = {
                "primary_engine": {"engine_name": request.ocr_engine},
                "fallback_engines": []  # Disable fallbacks if specific engine requested
            }

        # Queue the task
        task = reprocess_document_ocr.delay(
            job_id=job_id,
            document_id=document_id,
            workflow_config_name=request.workflow_config,
            workflow_overrides=workflow_overrides,
            priority=request.priority
        )

        logger.info(
            "Document reprocessing task queued",
            job_id=job_id,
            document_id=document_id,
            task_id=task.id
        )

        return ReprocessResponse(
            job_id=job_id,
            status="queued",
            message=f"Document {document_id} reprocessing job queued successfully",
            item_type="document",
            item_id=document_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to queue document reprocessing",
            document_id=document_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to queue reprocessing job")


@router.post("/email/{email_id}", response_model=ReprocessResponse)
async def reprocess_email(
    email_id: int,
    request: ReprocessEmailRequest,
    background_tasks: BackgroundTasks
):
    """Reprocess an email and its attachments.

    This endpoint allows reprocessing a specific email, including re-extracting
    attachments and reprocessing them with OCR if requested.

    Args:
        email_id: Database ID of the email to reprocess
        request: Reprocessing configuration including attachment processing options
        background_tasks: FastAPI background tasks for async processing

    Returns:
        ReprocessResponse with job details
    """
    try:
        # Generate a job ID
        job_id = str(uuid.uuid4())

        logger.info(
            "Email reprocessing request received",
            job_id=job_id,
            email_id=email_id,
            ocr_engine=request.ocr_engine,
            process_attachments=request.process_attachments,
            workflow_config=request.workflow_config,
            priority=request.priority
        )

        # Validate email exists
        from models.database import get_db_session
        from models.email import Email

        with get_db_session() as db:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                raise HTTPException(status_code=404, detail=f"Email {email_id} not found")

        # Queue the reprocessing task
        from workers.tasks.email_ingestion import reprocess_email_ingestion

        # Queue the task
        task = reprocess_email_ingestion.delay(
            job_id=job_id,
            email_id=email_id,
            ocr_engine=request.ocr_engine,
            workflow_config_name=request.workflow_config,
            process_attachments=request.process_attachments,
            priority=request.priority
        )

        logger.info(
            "Email reprocessing task queued",
            job_id=job_id,
            email_id=email_id,
            task_id=task.id
        )

        return ReprocessResponse(
            job_id=job_id,
            status="queued",
            message=f"Email {email_id} reprocessing job queued successfully",
            item_type="email",
            item_id=email_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to queue email reprocessing",
            email_id=email_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to queue reprocessing job")


@router.get("/status/{job_id}", response_model=ReprocessStatus)
async def get_reprocessing_status(job_id: str):
    """Get the status of a reprocessing job.

    Args:
        job_id: Unique job identifier

    Returns:
        ReprocessStatus with current job status and progress
    """
    try:
        # In a real implementation, you would check the database or task result
        # For now, return a mock status
        return ReprocessStatus(
            job_id=job_id,
            status="processing",
            progress=0.5,
            message="Reprocessing in progress",
            item_type="unknown",
            item_id=0,
            created_at=datetime.utcnow().isoformat() + "Z",
            updated_at=datetime.utcnow().isoformat() + "Z"
        )

    except Exception as e:
        logger.error(
            "Failed to get reprocessing status",
            job_id=job_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to get job status")


__all__ = ["router"]

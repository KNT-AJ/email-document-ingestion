"""Email ingestion API routes."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from config import get_settings
from utils.logging import get_logger

router = APIRouter()
logger = get_logger("api.ingestion")
settings = get_settings()


class EmailIngestionRequest(BaseModel):
    """Request model for email ingestion."""

    email_id: str
    subject: Optional[str] = None
    sender: Optional[str] = None
    process_attachments: bool = True
    priority: str = "medium"


class IngestionResponse(BaseModel):
    """Response model for ingestion requests."""

    job_id: str
    status: str
    message: str


class IngestionStatus(BaseModel):
    """Status model for ingestion jobs."""

    job_id: str
    status: str
    progress: float
    message: str
    created_at: str
    updated_at: str


@router.post("/ingest/email", response_model=IngestionResponse)
async def ingest_email(request: EmailIngestionRequest, background_tasks: BackgroundTasks):
    """Ingest an email and process its attachments.

    This endpoint accepts email ingestion requests and queues them for processing.
    The actual processing will be handled by Celery workers.
    """
    try:
        # Generate a job ID
        import uuid
        job_id = str(uuid.uuid4())

        logger.info(
            "Email ingestion request received",
            job_id=job_id,
            email_id=request.email_id,
            sender=request.sender,
            process_attachments=request.process_attachments
        )

        # Here you would typically:
        # 1. Validate the email exists
        # 2. Create a database record for the job
        # 3. Queue the task for processing
        # 4. For now, we'll just simulate queuing

        # TODO: Implement actual task queuing with Celery
        # background_tasks.add_task(process_email_ingestion, job_id, request)

        return IngestionResponse(
            job_id=job_id,
            status="queued",
            message=f"Email ingestion job queued successfully"
        )

    except Exception as e:
        logger.error(
            "Failed to queue email ingestion",
            email_id=request.email_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to queue ingestion job")


@router.get("/ingest/status/{job_id}", response_model=IngestionStatus)
async def get_ingestion_status(job_id: str):
    """Get the status of an ingestion job."""

    # TODO: Implement actual status checking from database
    # For now, return a mock status
    return IngestionStatus(
        job_id=job_id,
        status="processing",
        progress=0.5,
        message="Processing email attachments",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:01:00Z"
    )


@router.post("/ingest/batch")
async def ingest_batch_emails(requests: List[EmailIngestionRequest]):
    """Ingest multiple emails in batch."""

    if len(requests) > settings.BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size too large. Maximum allowed: {settings.BATCH_SIZE}"
        )

    job_ids = []
    for request in requests:
        # Generate job ID for each request
        import uuid
        job_id = str(uuid.uuid4())
        job_ids.append(job_id)

        logger.info(
            "Batch email ingestion request",
            job_id=job_id,
            email_id=request.email_id
        )

        # TODO: Queue batch processing tasks

    return {
        "job_ids": job_ids,
        "total_jobs": len(job_ids),
        "message": "Batch ingestion jobs queued successfully"
    }


@router.delete("/ingest/{job_id}")
async def cancel_ingestion(job_id: str):
    """Cancel an ingestion job."""

    logger.info("Ingestion cancellation request", job_id=job_id)

    # TODO: Implement actual job cancellation
    # This would involve:
    # 1. Finding the job in the database
    # 2. Updating its status to cancelled
    # 3. Revoking any Celery tasks

    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "Ingestion job cancelled successfully"
    }

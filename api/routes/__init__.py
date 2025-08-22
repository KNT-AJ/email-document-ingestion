"""API routes package."""

from fastapi import APIRouter

from .health import router as health_router
from .ingestion import router as ingestion_router
from .gmail import router as gmail_router
from .reprocess import router as reprocess_router
from .metrics import router as metrics_router

# Create main API router
router = APIRouter()

# Include sub-routers
router.include_router(health_router, tags=["Health"])
router.include_router(ingestion_router, tags=["Ingestion"])
router.include_router(gmail_router, tags=["Gmail"])
router.include_router(reprocess_router, prefix="/reprocess", tags=["Reprocess"])
router.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])

__all__ = ["router"]
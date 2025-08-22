"""Metrics dashboard endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Optional
from utils.metrics import get_metrics_collector
from utils.logging import get_logger

router = APIRouter()
logger = get_logger("api.metrics")


@router.get("/dashboard")
async def get_metrics_dashboard():
    """Get comprehensive metrics dashboard data."""
    try:
        collector = get_metrics_collector()

        # Get OCR metrics for all engines
        ocr_metrics = collector.get_ocr_metrics()

        # Get system-wide metrics
        system_metrics = collector.get_system_metrics()

        # Combine into dashboard format
        dashboard_data = {
            "system": system_metrics,
            "engines": ocr_metrics,
            "summary": {
                "total_engines": len(ocr_metrics),
                "engines_with_data": sum(1 for engine_data in ocr_metrics.values() if engine_data["requests"] > 0),
                "total_pages_processed": sum(engine_data["total_pages_processed"] for engine_data in ocr_metrics.values()),
                "total_words_extracted": sum(engine_data["total_words_extracted"] for engine_data in ocr_metrics.values()),
                "total_cost_cents": sum(engine_data["total_cost_cents"] for engine_data in ocr_metrics.values()),
            }
        }

        logger.info("Metrics dashboard data retrieved", engines_count=len(ocr_metrics))
        return dashboard_data

    except Exception as e:
        logger.error("Error retrieving metrics dashboard", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/engines/{engine_name}")
async def get_engine_metrics(engine_name: str):
    """Get metrics for a specific OCR engine."""
    try:
        collector = get_metrics_collector()
        engine_metrics = collector.get_ocr_metrics(engine_name)

        if engine_name not in engine_metrics:
            raise HTTPException(status_code=404, detail=f"Engine '{engine_name}' not found")

        logger.info("Engine metrics retrieved", engine=engine_name)
        return engine_metrics[engine_name]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving engine metrics", engine=engine_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve engine metrics")


@router.get("/engines")
async def get_all_engines_metrics():
    """Get metrics for all OCR engines."""
    try:
        collector = get_metrics_collector()
        ocr_metrics = collector.get_ocr_metrics()

        logger.info("All engines metrics retrieved", engines_count=len(ocr_metrics))
        return {"engines": ocr_metrics}

    except Exception as e:
        logger.error("Error retrieving engines metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve engines metrics")


@router.post("/reset")
async def reset_metrics(engine: Optional[str] = None):
    """Reset metrics for a specific engine or all engines."""
    try:
        collector = get_metrics_collector()
        collector.reset_metrics(engine)

        if engine:
            logger.info("Engine metrics reset", engine=engine)
            return {"message": f"Metrics reset for engine '{engine}'"}
        else:
            logger.info("All metrics reset")
            return {"message": "All metrics reset"}

    except Exception as e:
        logger.error("Error resetting metrics", engine=engine, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reset metrics")


@router.get("/system")
async def get_system_metrics():
    """Get system-wide metrics."""
    try:
        collector = get_metrics_collector()
        system_metrics = collector.get_system_metrics()

        logger.info("System metrics retrieved")
        return system_metrics

    except Exception as e:
        logger.error("Error retrieving system metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")

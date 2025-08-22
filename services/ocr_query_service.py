"""OCR run query utilities for retrieving and analyzing OCR processing data."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import Session, joinedload

from models.email import OCRRun, Document
from models.database import get_db


logger = logging.getLogger(__name__)


class OCRQueryService:
    """Service for querying OCR runs with various filters and aggregations."""

    def __init__(self, db: Session):
        """
        Initialize OCR query service.

        Args:
            db: Database session
        """
        self.db = db

    def get_ocr_runs_by_document_id(
        self,
        document_id: int,
        limit: int = 10,
        offset: int = 0,
        include_document: bool = False
    ) -> List[OCRRun]:
        """
        Get OCR runs for a specific document.

        Args:
            document_id: Document ID
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            include_document: Whether to eagerly load document data

        Returns:
            List of OCRRun instances
        """
        query = self.db.query(OCRRun).filter(OCRRun.document_id == document_id)

        if include_document:
            query = query.options(joinedload(OCRRun.document))

        runs = (
            query.order_by(OCRRun.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        logger.debug(f"Found {len(runs)} OCR runs for document {document_id}")
        return runs

    def get_ocr_runs_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
        include_document: bool = False
    ) -> List[OCRRun]:
        """
        Get OCR runs by status.

        Args:
            status: Status to filter by
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            include_document: Whether to eagerly load document data

        Returns:
            List of OCRRun instances
        """
        query = self.db.query(OCRRun).filter(OCRRun.status == status)

        if include_document:
            query = query.options(joinedload(OCRRun.document))

        runs = (
            query.order_by(OCRRun.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        logger.debug(f"Found {len(runs)} OCR runs with status '{status}'")
        return runs

    def get_ocr_runs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
        offset: int = 0,
        include_document: bool = False
    ) -> List[OCRRun]:
        """
        Get OCR runs within a date range.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            include_document: Whether to eagerly load document data

        Returns:
            List of OCRRun instances
        """
        query = self.db.query(OCRRun).filter(
            and_(
                OCRRun.created_at >= start_date,
                OCRRun.created_at <= end_date
            )
        )

        if include_document:
            query = query.options(joinedload(OCRRun.document))

        runs = (
            query.order_by(OCRRun.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        logger.debug(
            f"Found {len(runs)} OCR runs between {start_date} and {end_date}"
        )
        return runs

    def get_ocr_runs_by_metrics(
        self,
        min_confidence: Optional[int] = None,
        max_latency: Optional[int] = None,
        min_pages: Optional[int] = None,
        max_pages: Optional[int] = None,
        ocr_engine: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        include_document: bool = False
    ) -> List[OCRRun]:
        """
        Get OCR runs by performance metrics.

        Args:
            min_confidence: Minimum confidence score (0-100)
            max_latency: Maximum latency in milliseconds
            min_pages: Minimum number of pages
            max_pages: Maximum number of pages
            ocr_engine: Filter by specific OCR engine
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            include_document: Whether to eagerly load document data

        Returns:
            List of OCRRun instances
        """
        filters = []

        if min_confidence is not None:
            filters.append(OCRRun.confidence_mean >= min_confidence)
        if max_latency is not None:
            filters.append(OCRRun.latency_ms <= max_latency)
        if min_pages is not None:
            filters.append(OCRRun.pages_parsed >= min_pages)
        if max_pages is not None:
            filters.append(OCRRun.pages_parsed <= max_pages)
        if ocr_engine is not None:
            filters.append(OCRRun.ocr_engine == ocr_engine)

        query = self.db.query(OCRRun)
        if filters:
            query = query.filter(and_(*filters))

        if include_document:
            query = query.options(joinedload(OCRRun.document))

        runs = (
            query.order_by(OCRRun.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        logger.debug(f"Found {len(runs)} OCR runs matching metric filters")
        return runs

    def get_latest_successful_ocr_run(self, document_id: int) -> Optional[OCRRun]:
        """
        Get the most recent successful OCR run for a document.

        Args:
            document_id: Document ID

        Returns:
            Latest successful OCRRun instance, or None if not found
        """
        run = (
            self.db.query(OCRRun)
            .filter(
                and_(
                    OCRRun.document_id == document_id,
                    OCRRun.status == "completed"
                )
            )
            .options(joinedload(OCRRun.document))
            .order_by(OCRRun.completed_at.desc())
            .first()
        )

        if run:
            logger.debug(f"Found latest successful OCR run {run.id} for document {document_id}")
        else:
            logger.debug(f"No successful OCR runs found for document {document_id}")

        return run

    def get_ocr_runs_by_engine(
        self,
        ocr_engine: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        include_document: bool = False
    ) -> List[OCRRun]:
        """
        Get OCR runs by engine type.

        Args:
            ocr_engine: OCR engine name
            status: Optional status filter
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            include_document: Whether to eagerly load document data

        Returns:
            List of OCRRun instances
        """
        filters = [OCRRun.ocr_engine == ocr_engine]

        if status:
            filters.append(OCRRun.status == status)

        query = self.db.query(OCRRun).filter(and_(*filters))

        if include_document:
            query = query.options(joinedload(OCRRun.document))

        runs = (
            query.order_by(OCRRun.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        logger.debug(f"Found {len(runs)} OCR runs for engine '{ocr_engine}'")
        return runs

    def get_ocr_performance_stats(
        self,
        days: int = 7,
        ocr_engine: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get performance statistics for OCR runs.

        Args:
            days: Number of days to look back
            ocr_engine: Filter by specific OCR engine

        Returns:
            Dictionary containing performance statistics
        """
        since_date = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(OCRRun).filter(
            and_(
                OCRRun.created_at >= since_date,
                OCRRun.status == "completed"
            )
        )

        if ocr_engine:
            query = query.filter(OCRRun.ocr_engine == ocr_engine)

        # Get basic counts
        total_runs = query.count()

        if total_runs == 0:
            return {
                "total_runs": 0,
                "avg_confidence": 0,
                "avg_latency_ms": 0,
                "avg_pages": 0,
                "avg_words": 0,
                "total_pages": 0,
                "total_words": 0,
                "engine_breakdown": {}
            }

        # Calculate aggregates
        result = query.with_entities(
            func.avg(OCRRun.confidence_mean).label('avg_confidence'),
            func.avg(OCRRun.latency_ms).label('avg_latency'),
            func.avg(OCRRun.pages_parsed).label('avg_pages'),
            func.avg(OCRRun.word_count).label('avg_words'),
            func.sum(OCRRun.pages_parsed).label('total_pages'),
            func.sum(OCRRun.word_count).label('total_words')
        ).first()

        stats = {
            "total_runs": total_runs,
            "avg_confidence": round(result.avg_confidence or 0, 2),
            "avg_latency_ms": round(result.avg_latency or 0, 2),
            "avg_pages": round(result.avg_pages or 0, 2),
            "avg_words": round(result.avg_words or 0, 2),
            "total_pages": result.total_pages or 0,
            "total_words": result.total_words or 0
        }

        # Get engine breakdown
        engine_stats = (
            self.db.query(
                OCRRun.ocr_engine,
                func.count(OCRRun.id).label('count'),
                func.avg(OCRRun.confidence_mean).label('avg_confidence')
            )
            .filter(
                and_(
                    OCRRun.created_at >= since_date,
                    OCRRun.status == "completed"
                )
            )
            .group_by(OCRRun.ocr_engine)
            .all()
        )

        stats["engine_breakdown"] = {
            engine: {
                "count": count,
                "avg_confidence": round(avg_conf or 0, 2)
            }
            for engine, count, avg_conf in engine_stats
        }

        logger.info(f"Calculated OCR performance stats for last {days} days")
        return stats

    def search_ocr_runs(
        self,
        document_id: Optional[int] = None,
        ocr_engine: Optional[str] = None,
        status: Optional[str] = None,
        min_confidence: Optional[int] = None,
        max_latency: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[OCRRun], int]:
        """
        Advanced search for OCR runs with multiple filters.

        Args:
            document_id: Filter by document ID
            ocr_engine: Filter by OCR engine
            status: Filter by status
            min_confidence: Minimum confidence score
            max_latency: Maximum latency
            date_from: Start date filter
            date_to: End date filter
            limit: Maximum number of results
            offset: Pagination offset
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)

        Returns:
            Tuple of (results, total_count)
        """
        filters = []

        if document_id is not None:
            filters.append(OCRRun.document_id == document_id)
        if ocr_engine:
            filters.append(OCRRun.ocr_engine == ocr_engine)
        if status:
            filters.append(OCRRun.status == status)
        if min_confidence is not None:
            filters.append(OCRRun.confidence_mean >= min_confidence)
        if max_latency is not None:
            filters.append(OCRRun.latency_ms <= max_latency)
        if date_from:
            filters.append(OCRRun.created_at >= date_from)
        if date_to:
            filters.append(OCRRun.created_at <= date_to)

        # Count query for total results
        count_query = self.db.query(func.count(OCRRun.id))
        if filters:
            count_query = count_query.filter(and_(*filters))
        total_count = count_query.scalar()

        # Main query with sorting
        query = self.db.query(OCRRun)
        if filters:
            query = query.filter(and_(*filters))

        # Apply sorting
        sort_column = getattr(OCRRun, sort_by, OCRRun.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Apply pagination
        results = query.limit(limit).offset(offset).all()

        logger.debug(f"OCR search returned {len(results)} results (total: {total_count})")
        return results, total_count


def create_ocr_query_service(db: Optional[Session] = None) -> OCRQueryService:
    """
    Factory function to create an OCR query service.

    Args:
        db: Optional database session (creates new one if not provided)

    Returns:
        Configured OCR query service
    """
    if db is None:
        db = next(get_db())

    return OCRQueryService(db)

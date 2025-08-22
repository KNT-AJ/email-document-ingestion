"""Document update service for selecting best OCR results and updating document records."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from models.email import Document, OCRRun
from models.database import get_db
from services.ocr_query_service import OCRQueryService
from services.blob_storage import OCRBlobStorageService


logger = logging.getLogger(__name__)


class OCRDocumentService:
    """Service for updating documents with best OCR run results."""

    def __init__(self, db: Session, query_service: OCRQueryService, ocr_storage: OCRBlobStorageService):
        """
        Initialize OCR document service.

        Args:
            db: Database session
            query_service: OCR query service for finding runs
            ocr_storage: OCR blob storage service for retrieving responses
        """
        self.db = db
        self.query_service = query_service
        self.ocr_storage = ocr_storage

    def update_document_with_best_ocr_run(
        self,
        document_id: int,
        criteria: str = "confidence"
    ) -> bool:
        """
        Update document with the best OCR run results.

        Args:
            document_id: Document ID to update
            criteria: Selection criteria (confidence, recency, word_count, custom)

        Returns:
            True if document was updated, False if no suitable OCR run found
        """
        try:
            # Get the best OCR run for this document
            best_run = self.get_best_ocr_run(document_id, criteria)

            if not best_run:
                logger.info(f"No suitable OCR run found for document {document_id}")
                return False

            # Get document
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if not document:
                logger.error(f"Document {document_id} not found")
                return False

            # Extract text content from OCR run
            text_content = self._extract_text_from_ocr_run(best_run)
            if not text_content:
                logger.warning(f"No text content extracted from OCR run {best_run.id}")
                return False

            # Update document with OCR results
            old_engine = document.ocr_engine
            old_confidence = document.ocr_confidence

            document.extracted_text = text_content
            document.ocr_engine = best_run.ocr_engine
            document.ocr_confidence = best_run.confidence_mean
            document.page_count = best_run.pages_parsed
            document.word_count = best_run.word_count
            document.processing_status = "completed"
            document.processed_at = datetime.utcnow()

            self.db.commit()

            logger.info(
                f"Updated document {document_id} with OCR run {best_run.id} "
                f"(engine: {old_engine} -> {best_run.ocr_engine}, "
                f"confidence: {old_confidence} -> {best_run.confidence_score})"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update document {document_id}: {e}")
            self.db.rollback()
            return False

    def get_best_ocr_run(
        self,
        document_id: int,
        criteria: str = "prd_policy"
    ) -> Optional[OCRRun]:
        """
        Get the best OCR run for a document based on PRD selection policy.

        Args:
            document_id: Document ID
            criteria: Selection criteria (for backward compatibility, default is PRD policy)

        Returns:
            Best OCRRun instance, or None if not found
        """
        # Get all completed OCR runs for this document
        runs = self.query_service.get_ocr_runs_by_document_id(
            document_id, limit=50  # Limit to prevent excessive processing
        )

        # Filter to only completed runs
        completed_runs = [run for run in runs if run.status == "completed"]

        if not completed_runs:
            return None

        # Use PRD selection policy as default
        if criteria == "prd_policy" or criteria not in ["confidence", "recency", "word_count", "custom"]:
            return self._get_best_run_prd_policy(completed_runs)

        if criteria == "confidence":
            # Select run with highest confidence score
            return max(completed_runs,
                      key=lambda r: r.confidence_mean or 0)

        elif criteria == "recency":
            # Select most recent run
            return max(completed_runs,
                      key=lambda r: r.completed_at or r.created_at)

        elif criteria == "word_count":
            # Select run with highest word count
            return max(completed_runs,
                      key=lambda r: r.word_count or 0)

        elif criteria == "custom":
            # Use custom weighted scoring
            return self._get_best_run_custom_scoring(completed_runs)

        else:
            # Default to PRD policy
            logger.warning(f"Unknown criteria '{criteria}', falling back to PRD policy")
            return self._get_best_run_prd_policy(completed_runs)

    def _get_best_run_custom_scoring(self, runs: List[OCRRun]) -> Optional[OCRRun]:
        """
        Get best run using custom weighted scoring algorithm.

        Args:
            runs: List of completed OCR runs

        Returns:
            Best OCRRun based on custom scoring
        """
        if not runs:
            return None

        scored_runs = []

        for run in runs:
            score = 0.0

            # Confidence score (0-100) - weight: 0.4
            confidence = run.confidence_score or 0
            score += (confidence / 100.0) * 0.4

            # Word count (normalized) - weight: 0.3
            # Assume max reasonable word count is 50,000
            word_count = run.word_count or 0
            normalized_words = min(word_count / 50000.0, 1.0)
            score += normalized_words * 0.3

            # Recency bonus - weight: 0.2
            # More recent runs get a small bonus
            now = datetime.utcnow()
            completed_at = run.completed_at or run.created_at
            hours_old = (now - completed_at).total_seconds() / 3600

            # Bonus decreases over time (max 1.0 for runs < 1 hour old)
            recency_bonus = max(0, 1.0 - (hours_old / 168))  # 168 hours = 1 week
            score += recency_bonus * 0.2

            # Small bonus for successful runs with low latency - weight: 0.1
            if run.latency_ms and run.latency_ms < 30000:  # Less than 30 seconds
                score += 0.1

            scored_runs.append((run, score))

        # Return run with highest score
        return max(scored_runs, key=lambda x: x[1])[0]

    def _get_best_run_prd_policy(self, runs: List[OCRRun]) -> Optional[OCRRun]:
        """
        Get best run using PRD selection policy as specified in section 7.

        Score rubric (first satisfied wins):
        1. Highest confidence_mean (if engine provides) above threshold, AND pages_parsed == page_count.
        2. Else most pages parsed with non-empty text.
        3. Else highest word_count with ≥1 table detected (if available).
        4. Tie-break: lowest latency_ms; if still tied, lowest cost_cents.

        Args:
            runs: List of completed OCR runs

        Returns:
            Best OCRRun based on PRD policy
        """
        if not runs:
            return None

        # Get the document to determine total page count for comparison
        document = runs[0].document  # All runs should have the same document
        total_pages = document.page_count if document else None

        # Initialize variable for tracking runs from criteria 2
        best_pages_runs = []

        # Filter runs that meet criteria 1: highest confidence_mean above threshold AND pages_parsed == page_count
        confidence_threshold = 70  # Configurable threshold for confidence

        criteria_1_runs = []
        for run in runs:
            confidence = run.confidence_mean or 0
            pages_parsed = run.pages_parsed or 0

            # Check if confidence is above threshold and all pages were parsed
            if (confidence > confidence_threshold and
                total_pages is not None and
                pages_parsed == total_pages):
                criteria_1_runs.append(run)

        if criteria_1_runs:
            # Select the one with highest confidence_mean
            return max(criteria_1_runs, key=lambda r: r.confidence_mean or 0)

        # Criteria 2: Most pages parsed with non-empty text (word_count > 0)
        criteria_2_runs = [run for run in runs if (run.pages_parsed or 0) > 0 and (run.word_count or 0) > 0]
        if criteria_2_runs:
            # Find the maximum pages_parsed value
            max_pages = max(run.pages_parsed or 0 for run in criteria_2_runs)

            # Get all runs with the maximum pages_parsed value
            best_pages_runs = [run for run in criteria_2_runs if (run.pages_parsed or 0) == max_pages]

            if len(best_pages_runs) == 1:
                # Only one run has the most pages, return it
                return best_pages_runs[0]
            else:
                # Multiple runs have the same max pages, fall through to word count tie-breaking
                # Continue to word count logic with these runs
                pass

        # Criteria 3: Highest word_count with ≥1 table detected (if available)
        criteria_3_runs = []
        for run in runs:
            word_count = run.word_count or 0
            table_count = run.table_count or 0

            if word_count > 0 and table_count >= 1:
                criteria_3_runs.append(run)

        if criteria_3_runs:
            # Select the one with highest word_count
            return max(criteria_3_runs, key=lambda r: r.word_count or 0)

        # If we get here, none of the runs met the table criteria, so use highest word_count overall
        # If we have best_pages_runs from criteria 2, use those; otherwise use all runs
        word_count_runs = best_pages_runs if best_pages_runs else [run for run in runs if (run.word_count or 0) > 0]
        if word_count_runs:
            best_by_words = max(word_count_runs, key=lambda r: r.word_count or 0)

            # Apply tie-breakers: lowest latency_ms, then lowest cost_cents
            candidates = [best_by_words]
            max_words = best_by_words.word_count

            # Find all runs with the same word count
            for run in word_count_runs:
                if run != best_by_words and (run.word_count or 0) == max_words:
                    candidates.append(run)

            if len(candidates) > 1:
                # Tie-break by lowest latency_ms
                candidates.sort(key=lambda r: r.latency_ms or float('inf'))

                # If still tied, tie-break by lowest cost_cents
                if (len(candidates) > 1 and
                    candidates[0].latency_ms == candidates[1].latency_ms):
                    candidates.sort(key=lambda r: r.cost_cents or float('inf'))

            return candidates[0]

        # Final fallback: return any completed run with lowest latency
        return min(runs, key=lambda r: r.latency_ms or float('inf'))

    def compare_ocr_runs(self, run_ids: List[int]) -> Dict[str, Any]:
        """
        Compare multiple OCR runs and return analysis.

        Args:
            run_ids: List of OCR run IDs to compare

        Returns:
            Dictionary containing comparison results
        """
        runs = []
        for run_id in run_ids:
            run = self.query_service.db.query(OCRRun).filter(OCRRun.id == run_id).first()
            if run and run.status == "completed":
                runs.append(run)

        if not runs:
            return {"error": "No valid completed OCR runs found"}

        # Extract metrics for comparison
        comparison = {
            "run_count": len(runs),
            "runs": [],
            "best_by_confidence": None,
            "best_by_word_count": None,
            "best_by_recency": None
        }

        for run in runs:
            run_data = {
                "id": run.id,
                "ocr_engine": run.ocr_engine,
                "confidence_mean": run.confidence_mean,
                "word_count": run.word_count,
                "pages_parsed": run.pages_parsed,
                "table_count": run.table_count,
                "latency_ms": run.latency_ms,
                "cost_cents": run.cost_cents,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None
            }
            comparison["runs"].append(run_data)

        # Find best by different criteria
        if runs:
            comparison["best_by_confidence"] = max(runs, key=lambda r: r.confidence_mean or 0).id
            comparison["best_by_word_count"] = max(runs, key=lambda r: r.word_count or 0).id
            comparison["best_by_recency"] = max(runs, key=lambda r: r.completed_at or r.created_at).id

        return comparison

    def _extract_text_from_ocr_run(self, ocr_run: OCRRun) -> Optional[str]:
        """
        Extract text content from an OCR run.

        Args:
            ocr_run: OCRRun instance

        Returns:
            Extracted text content, or None if not available
        """
        try:
            # If no blob storage path, try to get text from document pages
            if not ocr_run.raw_response_storage_path:
                # Fallback to extracting from document pages
                text_parts = []
                for page in ocr_run.document_pages:
                    if page.text_content:
                        text_parts.append(page.text_content)

                if text_parts:
                    return "\n\n".join(text_parts)
                return None

            # Retrieve JSON response from blob storage
            json_response = self.ocr_storage.retrieve_ocr_response(
                ocr_run.raw_response_storage_path
            )

            # Extract text based on common OCR response formats
            return self._extract_text_from_json_response(json_response)

        except Exception as e:
            logger.error(f"Failed to extract text from OCR run {ocr_run.id}: {e}")
            return None

    def _extract_text_from_json_response(self, json_response: Dict[str, Any]) -> str:
        """
        Extract text content from OCR JSON response.

        Args:
            json_response: JSON response from OCR engine

        Returns:
            Extracted text content
        """
        text_parts = []

        # Handle different OCR engine response formats
        if "pages" in json_response:
            # Direct pages array
            for page in json_response["pages"]:
                if "text" in page:
                    text_parts.append(page["text"])
                elif "content" in page:
                    text_parts.append(page["content"])

        elif "document" in json_response and "pages" in json_response["document"]:
            # Nested document.pages format
            for page in json_response["document"]["pages"]:
                if "text" in page:
                    text_parts.append(page["text"])
                elif "content" in page:
                    text_parts.append(page["content"])

        elif "text" in json_response:
            # Simple text field
            text_parts.append(json_response["text"])

        elif "fullTextAnnotation" in json_response:
            # Google Vision API format
            if "text" in json_response["fullTextAnnotation"]:
                text_parts.append(json_response["fullTextAnnotation"]["text"])

        elif "responses" in json_response:
            # Google Document AI format
            for response in json_response["responses"]:
                if "fullTextAnnotation" in response and "text" in response["fullTextAnnotation"]:
                    text_parts.append(response["fullTextAnnotation"]["text"])

        # Join all text parts with double newlines for page separation
        return "\n\n".join(text_parts)

    def get_document_ocr_status(self, document_id: int) -> Dict[str, Any]:
        """
        Get OCR processing status for a document.

        Args:
            document_id: Document ID

        Returns:
            Dictionary containing OCR status information
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": "Document not found"}

        # Get all OCR runs for this document
        runs = self.query_service.get_ocr_runs_by_document_id(document_id, limit=20)

        status_info = {
            "document_id": document_id,
            "filename": document.filename,
            "processing_status": document.processing_status,
            "ocr_engine": document.ocr_engine,
            "ocr_confidence": document.ocr_confidence,
            "total_ocr_runs": len(runs),
            "completed_runs": len([r for r in runs if r.status == "completed"]),
            "failed_runs": len([r for r in runs if r.status == "failed"]),
            "pending_runs": len([r for r in runs if r.status == "pending"]),
            "running_runs": len([r for r in runs if r.status == "running"]),
            "runs": []
        }

        # Add details for each run
        for run in runs:
            run_info = {
                "id": run.id,
                "ocr_engine": run.ocr_engine,
                "status": run.status,
                "confidence_score": run.confidence_score,
                "latency_ms": run.latency_ms,
                "created_at": run.created_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None
            }
            status_info["runs"].append(run_info)

        return status_info

    def test_ocr_selection_policy(self) -> Dict[str, Any]:
        """
        Test the OCR selection policy with various scenarios.

        Returns:
            Dictionary containing test results
        """
        test_results = {
            "test_name": "OCR Selection Policy Test",
            "passed": 0,
            "failed": 0,
            "results": []
        }

        # Mock runs for testing - simulating different OCR engines with different metrics
        class MockRun:
            def __init__(self, id, confidence_mean, pages_parsed, word_count, table_count, latency_ms, cost_cents):
                self.id = id
                self.confidence_mean = confidence_mean
                self.pages_parsed = pages_parsed
                self.word_count = word_count
                self.table_count = table_count
                self.latency_ms = latency_ms
                self.cost_cents = cost_cents

        class MockDocument:
            def __init__(self, page_count):
                self.page_count = page_count

        # Test Case 1: High confidence, all pages parsed (should win with criteria 1)
        doc = MockDocument(page_count=5)
        runs = [
            MockRun(1, confidence_mean=85, pages_parsed=5, word_count=1000, table_count=0, latency_ms=1000, cost_cents=50),  # Should win
            MockRun(2, confidence_mean=65, pages_parsed=5, word_count=1200, table_count=1, latency_ms=800, cost_cents=75),
        ]
        for run in runs:
            run.document = doc

        best = self._get_best_run_prd_policy(runs)
        expected_id = 1
        passed = best.id == expected_id
        test_results["passed" if passed else "failed"] += 1
        test_results["results"].append({
            "test": "High confidence, all pages parsed",
            "expected": expected_id,
            "actual": best.id,
            "passed": passed
        })

        # Test Case 2: No high confidence runs, should select most pages parsed (criteria 2)
        runs = [
            MockRun(1, confidence_mean=45, pages_parsed=3, word_count=800, table_count=0, latency_ms=1000, cost_cents=50),
            MockRun(2, confidence_mean=55, pages_parsed=4, word_count=900, table_count=0, latency_ms=800, cost_cents=75),  # Should win
            MockRun(3, confidence_mean=50, pages_parsed=2, word_count=1000, table_count=1, latency_ms=600, cost_cents=100),
        ]
        for run in runs:
            run.document = doc

        best = self._get_best_run_prd_policy(runs)
        expected_id = 2
        passed = best.id == expected_id
        test_results["passed" if passed else "failed"] += 1
        test_results["results"].append({
            "test": "Most pages parsed (no high confidence)",
            "expected": expected_id,
            "actual": best.id,
            "passed": passed
        })

        # Test Case 3: Table detection priority (criteria 3)
        runs = [
            MockRun(1, confidence_mean=45, pages_parsed=3, word_count=800, table_count=2, latency_ms=1000, cost_cents=50),  # Should win
            MockRun(2, confidence_mean=55, pages_parsed=4, word_count=700, table_count=0, latency_ms=800, cost_cents=75),
            MockRun(3, confidence_mean=50, pages_parsed=2, word_count=900, table_count=1, latency_ms=600, cost_cents=100),
        ]
        for run in runs:
            run.document = doc

        best = self._get_best_run_prd_policy(runs)
        expected_id = 1
        passed = best.id == expected_id
        test_results["passed" if passed else "failed"] += 1
        test_results["results"].append({
            "test": "Table detection priority",
            "expected": expected_id,
            "actual": best.id,
            "passed": passed
        })

        # Test Case 4: Tie-breaking by latency and cost
        runs = [
            MockRun(1, confidence_mean=45, pages_parsed=3, word_count=1000, table_count=0, latency_ms=1000, cost_cents=75),
            MockRun(2, confidence_mean=55, pages_parsed=3, word_count=1000, table_count=0, latency_ms=800, cost_cents=50),  # Should win (lower latency)
        ]
        for run in runs:
            run.document = doc

        best = self._get_best_run_prd_policy(runs)
        expected_id = 2
        passed = best.id == expected_id
        test_results["passed" if passed else "failed"] += 1
        test_results["results"].append({
            "test": "Tie-breaking by latency",
            "expected": expected_id,
            "actual": best.id,
            "passed": passed
        })

        return test_results


def create_ocr_document_service(
    db: Optional[Session] = None,
    query_service: Optional[OCRQueryService] = None,
    ocr_storage: Optional[OCRBlobStorageService] = None
) -> OCRDocumentService:
    """
    Factory function to create an OCR document service.

    Args:
        db: Optional database session (creates new one if not provided)
        query_service: Optional OCR query service (creates new one if not provided)
        ocr_storage: Optional OCR blob storage service (creates new one if not provided)

    Returns:
        Configured OCR document service
    """
    if db is None:
        db = next(get_db())

    if query_service is None:
        query_service = OCRQueryService(db)

    if ocr_storage is None:
        from services.blob_storage import create_ocr_blob_storage_service
        ocr_storage = create_ocr_blob_storage_service()

    return OCRDocumentService(db, query_service, ocr_storage)

#!/usr/bin/env python3
"""
Test script for OCR selection policy implementation.
Tests the PRD-compliant selection policy with various scenarios.
"""

from typing import List, Optional, Any, Dict


def get_best_run_prd_policy(runs: List[Any], document_page_count: int) -> Optional[Any]:
    """
    Get best run using PRD selection policy as specified in section 7.

    Score rubric (first satisfied wins):
    1. Highest confidence_mean (if engine provides) above threshold, AND pages_parsed == page_count.
    2. Else most pages parsed with non-empty text.
    3. Else highest word_count with ≥1 table detected (if available).
    4. Tie-break: lowest latency_ms; if still tied, lowest cost_cents.

    Args:
        runs: List of completed OCR runs
        document_page_count: Total page count of the document

    Returns:
        Best OCRRun based on PRD policy
    """
    if not runs:
        return None

    print(f"  Evaluating criteria for {len(runs)} runs")

    # Initialize variable for tracking runs from criteria 2
    best_pages_runs = []

    # Filter runs that meet criteria 1: highest confidence_mean above threshold AND pages_parsed == page_count
    confidence_threshold = 70  # Configurable threshold for confidence

    criteria_1_runs = []
    for run in runs:
        confidence = getattr(run, 'confidence_mean', 0) or 0
        pages_parsed = getattr(run, 'pages_parsed', 0) or 0

        # Check if confidence is above threshold and all pages were parsed
        if (confidence > confidence_threshold and
            document_page_count is not None and
            pages_parsed == document_page_count):
            criteria_1_runs.append(run)

    print(f"  Criteria 1 (high confidence + all pages): {len(criteria_1_runs)} runs")
    if criteria_1_runs:
        # Select the one with highest confidence_mean
        best = max(criteria_1_runs, key=lambda r: getattr(r, 'confidence_mean', 0) or 0)
        print(f"  Selected run {best.id} by criteria 1")
        return best

    # Criteria 2: Most pages parsed with non-empty text (word_count > 0)
    criteria_2_runs = [run for run in runs if (getattr(run, 'pages_parsed', 0) or 0) > 0 and (getattr(run, 'word_count', 0) or 0) > 0]
    print(f"  Criteria 2 (most pages parsed): {len(criteria_2_runs)} runs")
    if criteria_2_runs:
        # Find the maximum pages_parsed value
        max_pages = max(getattr(run, 'pages_parsed', 0) or 0 for run in criteria_2_runs)

        # Get all runs with the maximum pages_parsed value
        best_pages_runs = [run for run in criteria_2_runs if (getattr(run, 'pages_parsed', 0) or 0) == max_pages]

        if len(best_pages_runs) == 1:
            # Only one run has the most pages, return it
            best = best_pages_runs[0]
            print(f"  Selected run {best.id} by criteria 2 (unique max pages)")
            return best
        else:
            # Multiple runs have the same max pages, store them for tie-breaking
            print(f"  Multiple runs ({len(best_pages_runs)}) have same max pages ({max_pages}), will apply tie-breaking")
            # Continue to word count logic with these runs

    # Criteria 3: Highest word_count with ≥1 table detected (if available)
    criteria_3_runs = []
    for run in runs:
        word_count = getattr(run, 'word_count', 0) or 0
        table_count = getattr(run, 'table_count', 0) or 0

        if word_count > 0 and table_count >= 1:
            criteria_3_runs.append(run)

    print(f"  Criteria 3 (tables + high word count): {len(criteria_3_runs)} runs")
    if criteria_3_runs:
        # Select the one with highest word_count
        best = max(criteria_3_runs, key=lambda r: getattr(r, 'word_count', 0) or 0)
        print(f"  Selected run {best.id} by criteria 3")
        return best

    # If we get here, none of the runs met the table criteria, so use highest word_count overall
    # If we have best_pages_runs from criteria 2, use those; otherwise use all runs
    word_count_runs = best_pages_runs if 'best_pages_runs' in locals() and best_pages_runs else [run for run in runs if (getattr(run, 'word_count', 0) or 0) > 0]
    print(f"  Criteria 4 (highest word count overall): {len(word_count_runs)} runs")
    if word_count_runs:
        best_by_words = max(word_count_runs, key=lambda r: getattr(r, 'word_count', 0) or 0)

        # Apply tie-breakers: lowest latency_ms, then lowest cost_cents
        candidates = [best_by_words]
        max_words = getattr(best_by_words, 'word_count', 0)

        # Find all runs with the same word count
        for run in word_count_runs:
            if run != best_by_words and (getattr(run, 'word_count', 0) or 0) == max_words:
                candidates.append(run)

        print(f"  Found {len(candidates)} candidates with word_count {max_words}")
        print(f"  Candidates: {[(r.id, getattr(r, 'word_count', None), getattr(r, 'latency_ms', None)) for r in candidates]}")

        if len(candidates) > 1:
            # Debug: Print candidates before sorting
            print(f"  Before sorting - candidates: {[(r.id, getattr(r, 'latency_ms', None)) for r in candidates]}")

            # Tie-break by lowest latency_ms
            candidates.sort(key=lambda r: getattr(r, 'latency_ms', float('inf')) or float('inf'))

            # Debug: Print candidates after sorting
            print(f"  After latency sorting - candidates: {[(r.id, getattr(r, 'latency_ms', None)) for r in candidates]}")

            # If still tied, tie-break by lowest cost_cents
            if (len(candidates) > 1 and
                getattr(candidates[0], 'latency_ms', None) == getattr(candidates[1], 'latency_ms', None)):
                candidates.sort(key=lambda r: getattr(r, 'cost_cents', float('inf')) or float('inf'))
                print(f"  After cost sorting - candidates: {[(r.id, getattr(r, 'cost_cents', None)) for r in candidates]}")

        best = candidates[0]
        print(f"  Selected run {best.id} by criteria 4 (word count + tie-breaking)")
        return best

    # Final fallback: return any completed run with lowest latency
    return min(runs, key=lambda r: getattr(r, 'latency_ms', float('inf')) or float('inf'))


def test_ocr_selection_policy():
    """Test the OCR selection policy implementation."""
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

    # Test Case 1: High confidence, all pages parsed (should win with criteria 1)
    document_page_count = 5
    runs = [
        MockRun(1, confidence_mean=85, pages_parsed=5, word_count=1000, table_count=0, latency_ms=1000, cost_cents=50),  # Should win
        MockRun(2, confidence_mean=65, pages_parsed=5, word_count=1200, table_count=1, latency_ms=800, cost_cents=75),
    ]

    best = get_best_run_prd_policy(runs, document_page_count)
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

    best = get_best_run_prd_policy(runs, document_page_count)
    expected_id = 2
    passed = best.id == expected_id
    test_results["passed" if passed else "failed"] += 1
    test_results["results"].append({
        "test": "Most pages parsed (no high confidence)",
        "expected": expected_id,
        "actual": best.id,
        "passed": passed
    })

    # Test Case 3: Table detection priority (criteria 3) - but first check criteria 2 (most pages parsed)
    runs = [
        MockRun(1, confidence_mean=45, pages_parsed=3, word_count=800, table_count=2, latency_ms=1000, cost_cents=50),
        MockRun(2, confidence_mean=55, pages_parsed=4, word_count=700, table_count=0, latency_ms=800, cost_cents=75),  # Should win (most pages parsed)
        MockRun(3, confidence_mean=50, pages_parsed=2, word_count=900, table_count=1, latency_ms=600, cost_cents=100),
    ]

    best = get_best_run_prd_policy(runs, document_page_count)
    expected_id = 2  # Run 2 has most pages parsed (4), so wins under criteria 2
    passed = best.id == expected_id
    test_results["passed" if passed else "failed"] += 1
    test_results["results"].append({
        "test": "Most pages parsed takes precedence over table detection",
        "expected": expected_id,
        "actual": best.id,
        "passed": passed
    })

    # Test Case 4: Table detection priority (when pages parsed are equal)
    runs = [
        MockRun(1, confidence_mean=45, pages_parsed=3, word_count=800, table_count=2, latency_ms=1000, cost_cents=50),  # Should win (has tables)
        MockRun(2, confidence_mean=55, pages_parsed=3, word_count=700, table_count=0, latency_ms=800, cost_cents=75),
        MockRun(3, confidence_mean=50, pages_parsed=3, word_count=600, table_count=0, latency_ms=600, cost_cents=100),
    ]

    best = get_best_run_prd_policy(runs, document_page_count)
    expected_id = 1  # Run 1 has tables and highest word count among table runs
    passed = best.id == expected_id
    test_results["passed" if passed else "failed"] += 1
    test_results["results"].append({
        "test": "Table detection priority",
        "expected": expected_id,
        "actual": best.id,
        "passed": passed
    })

    # Test Case 5: Tie-breaking by latency and cost
    runs = [
        MockRun(1, confidence_mean=45, pages_parsed=3, word_count=1000, table_count=0, latency_ms=1000, cost_cents=75),
        MockRun(2, confidence_mean=55, pages_parsed=3, word_count=1000, table_count=0, latency_ms=800, cost_cents=50),  # Should win (lower latency)
    ]

    print(f"\nDebug Test Case 5:")
    print(f"Run 1 - latency_ms: {runs[0].latency_ms}, word_count: {runs[0].word_count}")
    print(f"Run 2 - latency_ms: {runs[1].latency_ms}, word_count: {runs[1].word_count}")

    best = get_best_run_prd_policy(runs, document_page_count)

    print(f"Best run selected: {best.id} (latency_ms: {best.latency_ms})")

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


def main():
    """Main function to run the test."""
    results = test_ocr_selection_policy()

    print("=" * 60)
    print(f"OCR Selection Policy Test Results")
    print("=" * 60)
    print(f"Total Tests: {results['passed'] + results['failed']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print()

    for i, test_result in enumerate(results['results'], 1):
        status = "✅ PASS" if test_result['passed'] else "❌ FAIL"
        print(f"Test {i}: {test_result['test']}")
        print(f"  Expected: Run {test_result['expected']}")
        print(f"  Actual:   Run {test_result['actual']}")
        print(f"  Status:   {status}")
        print()

    if results['failed'] == 0:
        print("🎉 All tests passed! OCR selection policy is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)

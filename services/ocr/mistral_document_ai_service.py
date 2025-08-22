"""Mistral Document AI OCR service implementation."""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import requests
from urllib.parse import urljoin

from .interface import OCRServiceInterface, OCRConfigurationError, OCRProcessingError, OCRTimeoutError
from ..blob_storage.service import BlobStorageService
from .config import get_ocr_config


class MistralDocumentAIService(OCRServiceInterface):
    """Mistral Document AI service for OCR processing."""

    def __init__(self):
        """Initialize the Mistral Document AI service."""
        config = get_ocr_config()

        # Get Mistral Document AI configuration
        if not config.is_mistral_configured():
            raise OCRConfigurationError(
                "Mistral Document AI API key is required. "
                "Set MISTRAL_API_KEY in your environment variables.",
                service_name="Mistral Document AI"
            )

        mistral_config = config.get_mistral_config()

        # Initialize configuration
        self.api_key = mistral_config["api_key"]
        self.base_url = mistral_config["base_url"]
        self.model = mistral_config["model"]

        # Initialize blob storage for raw response storage
        try:
            self.blob_storage = BlobStorageService()
        except Exception as e:
            raise OCRConfigurationError(
                f"Failed to initialize blob storage for OCR responses: {str(e)}",
                service_name="Mistral Document AI",
                original_error=e
            )

        # Configuration
        self.max_polling_time = config.max_polling_time
        self.polling_interval = config.polling_interval

    def analyze_document(self, document_path: Path, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a document using Mistral Document AI.

        Args:
            document_path: Path to the document file
            features: List of features to enable

        Returns:
            Dictionary containing analysis results
        """
        if not document_path.exists():
            raise OCRProcessingError(f"Document file not found: {document_path}")

        if features is None:
            features = ['tables', 'key_value_pairs']

        try:
            # Submit document for processing
            result = self._submit_document(document_path)

            # Convert to our standard format
            return self._convert_result_to_standard_format(result, document_path)

        except Exception as e:
            if isinstance(e, (OCRConfigurationError, OCRProcessingError, OCRTimeoutError)):
                raise
            raise OCRProcessingError(
                f"Failed to analyze document with Mistral Document AI: {str(e)}",
                service_name="Mistral Document AI",
                original_error=e
            )

    def _submit_document(self, document_path: Path) -> Dict[str, Any]:
        """Submit document to Mistral Document AI for processing."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Read and encode document
        with open(document_path, "rb") as f:
            document_data = f.read()

        # Prepare request data
        request_data = {
            "model": self.model,
            "document": document_data.hex(),  # Convert bytes to hex string
            "filename": document_path.name,
            "features": ["text", "tables", "key_value_pairs"]  # Default features
        }

        # Submit to Mistral API
        response = requests.post(
            urljoin(self.base_url, "/v1/ocr/process"),
            headers=headers,
            json=request_data,
            timeout=self.max_polling_time
        )

        if response.status_code != 200:
            raise OCRProcessingError(
                f"Mistral API error: {response.status_code} - {response.text}",
                service_name="Mistral Document AI"
            )

        result = response.json()
        if not result.get("success"):
            raise OCRProcessingError(
                f"Mistral processing failed: {result.get('error', 'Unknown error')}",
                service_name="Mistral Document AI"
            )

        return result

    def _convert_result_to_standard_format(self, result: Dict[str, Any], document_path: Path) -> Dict[str, Any]:
        """Convert Mistral Document AI result to our standard format."""
        # Store raw response in blob storage
        raw_response_blob_path = self._store_raw_response(result, document_path)

        # Extract and structure the results
        analysis_result = {
            'text': self.extract_text({'raw_result': result}),
            'tables': self.extract_tables({'raw_result': result}),
            'key_value_pairs': self.extract_key_value_pairs({'raw_result': result}),
            'pages': self._extract_pages(result),
            'raw_response': result,
            'raw_response_blob_path': raw_response_blob_path,
            'metadata': {
                'service': 'Mistral Document AI',
                'model': self.model,
                'document_path': str(document_path),
                'analysis_date': time.time()
            }
        }

        return analysis_result

    def _store_raw_response(self, result: Dict[str, Any], document_path: Path) -> str:
        """Store the raw JSON response in blob storage."""
        try:
            # Create blob path
            timestamp = int(time.time())
            filename = document_path.stem
            blob_path = f"ocr-responses/mistral/{filename}_{timestamp}.json"

            # Upload to blob storage
            json_data = json.dumps(result, default=str, ensure_ascii=False)
            self.blob_storage.upload(
                blob_path=blob_path,
                data=json_data.encode('utf-8'),
                content_type='application/json'
            )

            return blob_path

        except Exception as e:
            # Log warning but don't fail the entire analysis
            print(f"Warning: Failed to store raw response: {e}")
            return None

    def extract_text(self, analysis_result: Dict[str, Any]) -> str:
        """Extract plain text from analysis results."""
        result = analysis_result.get('raw_result', {})
        if not result:
            return ""

        text_content = []

        # Extract text from pages
        pages = result.get('pages', [])
        for page in pages:
            # Extract text from lines
            lines = page.get('lines', [])
            for line in lines:
                content = line.get('content', '')
                if content:
                    text_content.append(content)

            # Extract text from paragraphs if available
            paragraphs = page.get('paragraphs', [])
            for paragraph in paragraphs:
                content = paragraph.get('content', '')
                if content:
                    text_content.append(content)

        return '\n'.join(text_content)

    def extract_tables(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables from analysis results."""
        result = analysis_result.get('raw_result', {})
        if not result or 'tables' not in result:
            return []

        tables = []
        for table in result['tables']:
            table_data = {
                'row_count': table.get('row_count', 0),
                'column_count': table.get('column_count', 0),
                'cells': []
            }

            cells = table.get('cells', [])
            for cell in cells:
                cell_data = {
                    'row_index': cell.get('row_index', 0),
                    'column_index': cell.get('column_index', 0),
                    'content': cell.get('content', ''),
                    'confidence': cell.get('confidence', 0.0),
                    'bounding_regions': cell.get('bounding_regions', [])
                }
                table_data['cells'].append(cell_data)

            tables.append(table_data)

        return tables

    def extract_key_value_pairs(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key-value pairs from analysis results."""
        result = analysis_result.get('raw_result', {})
        if not result or 'key_value_pairs' not in result:
            return []

        kv_pairs = []
        for kv_pair in result['key_value_pairs']:
            kv_data = {
                'key': {
                    'content': kv_pair.get('key', {}).get('content', ''),
                    'confidence': kv_pair.get('key', {}).get('confidence', 0.0),
                    'bounding_regions': kv_pair.get('key', {}).get('bounding_regions', [])
                },
                'value': {
                    'content': kv_pair.get('value', {}).get('content', ''),
                    'confidence': kv_pair.get('value', {}).get('confidence', 0.0),
                    'bounding_regions': kv_pair.get('value', {}).get('bounding_regions', [])
                }
            }
            kv_pairs.append(kv_data)

        return kv_pairs

    def _extract_pages(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract page information from analysis results."""
        pages = result.get('pages', [])
        if not pages:
            return []

        page_list = []
        for i, page in enumerate(pages):
            page_data = {
                'page_number': page.get('page_number', i + 1),
                'width': page.get('width', 0.0),
                'height': page.get('height', 0.0),
                'unit': page.get('unit', 'pixel'),
                'line_count': len(page.get('lines', [])),
                'word_count': len(page.get('words', [])),
                'table_count': len([t for t in result.get('tables', []) if self._table_on_page(t, page.get('page_number', i + 1))])
            }
            page_list.append(page_data)

        return page_list

    def _table_on_page(self, table: Dict[str, Any], page_number: int) -> bool:
        """Check if a table appears on a specific page."""
        bounding_regions = table.get('bounding_regions', [])
        for region in bounding_regions:
            if region.get('page_number', 0) == page_number:
                return True
        return False

    def calculate_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics from analysis results."""
        result = analysis_result.get('raw_result', {})
        if not result:
            return {}

        metrics = {
            'page_count': len(result.get('pages', [])),
            'table_count': len(result.get('tables', [])),
            'key_value_pair_count': len(result.get('key_value_pairs', [])),
            'word_count': 0,
            'line_count': 0,
            'average_confidence': 0.0,
            'total_confidence_sum': 0.0,
            'confidence_count': 0
        }

        # Calculate word and line counts, confidence scores
        pages = result.get('pages', [])
        for page in pages:
            words = page.get('words', [])
            lines = page.get('lines', [])

            metrics['word_count'] += len(words)
            metrics['line_count'] += len(lines)

            # Sum confidence scores from words
            for word in words:
                confidence = word.get('confidence', 0.0)
                if confidence > 0:
                    metrics['total_confidence_sum'] += confidence
                    metrics['confidence_count'] += 1

        # Calculate average confidence
        if metrics['confidence_count'] > 0:
            metrics['average_confidence'] = metrics['total_confidence_sum'] / metrics['confidence_count']

        return metrics

    def get_supported_features(self) -> List[str]:
        """Get list of supported features for Mistral Document AI."""
        return [
            'tables',
            'key_value_pairs',
            'text'
        ]

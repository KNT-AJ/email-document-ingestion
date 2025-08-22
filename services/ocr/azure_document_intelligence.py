"""Azure Document Intelligence OCR service implementation."""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeResult,
    DocumentAnalysisFeature,
    AnalyzeOutputOption
)

from .interface import OCRServiceInterface, OCRConfigurationError, OCRProcessingError, OCRTimeoutError
from ..blob_storage.service import BlobStorageService
from .config import get_ocr_config


class AzureDocumentIntelligenceService(OCRServiceInterface):
    """Azure Document Intelligence service for OCR processing."""

    def __init__(self):
        """Initialize the Azure Document Intelligence service."""
        config = get_ocr_config()

        # Get Azure Document Intelligence configuration
        if not config.is_azure_configured():
            raise OCRConfigurationError(
                "Azure Document Intelligence endpoint and API key are required. "
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_API_KEY "
                "in your environment variables.",
                service_name="Azure Document Intelligence"
            )

        azure_config = config.get_azure_config()

        # Initialize the client
        try:
            self.client = DocumentIntelligenceClient(
                endpoint=azure_config["endpoint"],
                credential=AzureKeyCredential(azure_config["api_key"])
            )
        except Exception as e:
            raise OCRConfigurationError(
                f"Failed to initialize Azure Document Intelligence client: {str(e)}",
                service_name="Azure Document Intelligence",
                original_error=e
            )

        # Initialize blob storage for raw response storage
        try:
            self.blob_storage = BlobStorageService()
        except Exception as e:
            raise OCRConfigurationError(
                f"Failed to initialize blob storage for OCR responses: {str(e)}",
                service_name="Azure Document Intelligence",
                original_error=e
            )

        # Configuration
        self.max_polling_time = config.max_polling_time
        self.polling_interval = config.polling_interval
        self.model_id = config.azure_model

    def analyze_document(self, document_path: Path, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a document using Azure Document Intelligence.

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
            # Map feature names to Azure Document Intelligence features
            azure_features = self._map_features_to_azure(features)

            # Start document analysis
            with open(document_path, "rb") as f:
                poller = self.client.begin_analyze_document(
                    model_id=self.model_id,
                    body=f,
                    features=azure_features,
                    output=[AnalyzeOutputOption.JSON]  # Include raw JSON in response
                )

            # Wait for completion with timeout
            result = self._wait_for_completion(poller)

            # Convert to our standard format
            return self._convert_result_to_standard_format(result, document_path)

        except Exception as e:
            if isinstance(e, (OCRConfigurationError, OCRProcessingError, OCRTimeoutError)):
                raise
            raise OCRProcessingError(
                f"Failed to analyze document with Azure Document Intelligence: {str(e)}",
                service_name="Azure Document Intelligence",
                original_error=e
            )

    def _map_features_to_azure(self, features: List[str]) -> List[DocumentAnalysisFeature]:
        """Map feature names to Azure Document Intelligence features."""
        feature_mapping = {
            'key_value_pairs': DocumentAnalysisFeature.KEY_VALUE_PAIRS,
            'tables': DocumentAnalysisFeature.FORMULAS,  # Note: Tables are included in layout analysis
            'languages': DocumentAnalysisFeature.LANGUAGES,
            'barcodes': DocumentAnalysisFeature.BARCODES,
            'formulas': DocumentAnalysisFeature.FORMULAS,
            'style_font': DocumentAnalysisFeature.STYLE_FONT,
            'ocr_high_resolution': DocumentAnalysisFeature.OCR_HIGH_RESOLUTION,
        }

        azure_features = []
        for feature in features:
            if feature in feature_mapping:
                azure_features.append(feature_mapping[feature])

        return azure_features

    def _wait_for_completion(self, poller) -> AnalyzeResult:
        """Wait for the analysis to complete with timeout."""
        start_time = time.time()

        while not poller.done():
            if time.time() - start_time > self.max_polling_time:
                raise OCRTimeoutError(
                    f"OCR analysis timed out after {self.max_polling_time} seconds",
                    service_name="Azure Document Intelligence"
                )

            time.sleep(self.polling_interval)

        return poller.result()

    def _convert_result_to_standard_format(self, result: AnalyzeResult, document_path: Path) -> Dict[str, Any]:
        """Convert Azure Document Intelligence result to our standard format."""
        # Store raw response in blob storage
        raw_response_blob_path = self._store_raw_response(result, document_path)

        # Extract and structure the results
        analysis_result = {
            'text': self.extract_text({'raw_result': result}),
            'tables': self.extract_tables({'raw_result': result}),
            'key_value_pairs': self.extract_key_value_pairs({'raw_result': result}),
            'pages': self._extract_pages(result),
            'raw_response': result.as_dict() if hasattr(result, 'as_dict') else result.__dict__,
            'raw_response_blob_path': raw_response_blob_path,
            'metadata': {
                'service': 'Azure Document Intelligence',
                'model': self.model_id,
                'document_path': str(document_path),
                'analysis_date': time.time()
            }
        }

        return analysis_result

    def _store_raw_response(self, result: AnalyzeResult, document_path: Path) -> str:
        """Store the raw JSON response in blob storage."""
        try:
            # Convert result to dict for JSON serialization
            raw_data = result.as_dict() if hasattr(result, 'as_dict') else result.__dict__

            # Create blob path
            timestamp = int(time.time())
            filename = document_path.stem
            blob_path = f"ocr-responses/azure/{filename}_{timestamp}.json"

            # Upload to blob storage
            json_data = json.dumps(raw_data, default=str, ensure_ascii=False)
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
        result = analysis_result.get('raw_result')
        if not result:
            return ""

        text_content = []

        # Extract text from pages
        if hasattr(result, 'pages') and result.pages:
            for page in result.pages:
                if hasattr(page, 'lines') and page.lines:
                    for line in page.lines:
                        if hasattr(line, 'content'):
                            text_content.append(line.content)

        # Extract text from paragraphs if available
        if hasattr(result, 'paragraphs') and result.paragraphs:
            for paragraph in result.paragraphs:
                if hasattr(paragraph, 'content'):
                    text_content.append(paragraph.content)

        return '\n'.join(text_content)

    def extract_tables(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables from analysis results."""
        result = analysis_result.get('raw_result')
        if not result or not hasattr(result, 'tables'):
            return []

        tables = []
        for table in result.tables:
            table_data = {
                'row_count': getattr(table, 'row_count', 0),
                'column_count': getattr(table, 'column_count', 0),
                'cells': []
            }

            if hasattr(table, 'cells') and table.cells:
                for cell in table.cells:
                    cell_data = {
                        'row_index': getattr(cell, 'row_index', 0),
                        'column_index': getattr(cell, 'column_index', 0),
                        'content': getattr(cell, 'content', ''),
                        'confidence': getattr(cell, 'confidence', 0.0),
                        'bounding_regions': self._extract_bounding_regions(cell)
                    }
                    table_data['cells'].append(cell_data)

            tables.append(table_data)

        return tables

    def extract_key_value_pairs(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key-value pairs from analysis results."""
        result = analysis_result.get('raw_result')
        if not result or not hasattr(result, 'key_value_pairs'):
            return []

        kv_pairs = []
        for kv_pair in result.key_value_pairs:
            kv_data = {
                'key': {
                    'content': getattr(kv_pair.key, 'content', '') if kv_pair.key else '',
                    'confidence': getattr(kv_pair.key, 'confidence', 0.0) if kv_pair.key else 0.0,
                    'bounding_regions': self._extract_bounding_regions(kv_pair.key) if kv_pair.key else []
                },
                'value': {
                    'content': getattr(kv_pair.value, 'content', '') if kv_pair.value else '',
                    'confidence': getattr(kv_pair.value, 'confidence', 0.0) if kv_pair.value else 0.0,
                    'bounding_regions': self._extract_bounding_regions(kv_pair.value) if kv_pair.value else []
                }
            }
            kv_pairs.append(kv_data)

        return kv_pairs

    def _extract_pages(self, result: AnalyzeResult) -> List[Dict[str, Any]]:
        """Extract page information from analysis results."""
        if not hasattr(result, 'pages') or not result.pages:
            return []

        pages = []
        for page in result.pages:
            page_data = {
                'page_number': getattr(page, 'page_number', 0),
                'width': getattr(page, 'width', 0.0),
                'height': getattr(page, 'height', 0.0),
                'unit': getattr(page, 'unit', ''),
                'line_count': len(getattr(page, 'lines', [])),
                'word_count': len(getattr(page, 'words', [])),
                'table_count': len([t for t in getattr(result, 'tables', []) if self._table_on_page(t, page.page_number)])
            }
            pages.append(page_data)

        return pages

    def _table_on_page(self, table, page_number: int) -> bool:
        """Check if a table appears on a specific page."""
        if not hasattr(table, 'bounding_regions'):
            return False

        for region in table.bounding_regions:
            if getattr(region, 'page_number', 0) == page_number:
                return True
        return False

    def _extract_bounding_regions(self, element) -> List[Dict[str, Any]]:
        """Extract bounding regions from an element."""
        if not hasattr(element, 'bounding_regions') or not element.bounding_regions:
            return []

        regions = []
        for region in element.bounding_regions:
            region_data = {
                'page_number': getattr(region, 'page_number', 0),
                'polygon': getattr(region, 'polygon', [])
            }
            regions.append(region_data)

        return regions

    def calculate_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics from analysis results."""
        result = analysis_result.get('raw_result')
        if not result:
            return {}

        metrics = {
            'page_count': len(getattr(result, 'pages', [])),
            'table_count': len(getattr(result, 'tables', [])),
            'key_value_pair_count': len(getattr(result, 'key_value_pairs', [])),
            'word_count': 0,
            'line_count': 0,
            'average_confidence': 0.0,
            'total_confidence_sum': 0.0,
            'confidence_count': 0
        }

        # Calculate word and line counts, confidence scores
        if hasattr(result, 'pages') and result.pages:
            for page in result.pages:
                metrics['word_count'] += len(getattr(page, 'words', []))
                metrics['line_count'] += len(getattr(page, 'lines', []))

                # Sum confidence scores
                if hasattr(page, 'words') and page.words:
                    for word in page.words:
                        if hasattr(word, 'confidence'):
                            metrics['total_confidence_sum'] += word.confidence
                            metrics['confidence_count'] += 1

        # Calculate average confidence
        if metrics['confidence_count'] > 0:
            metrics['average_confidence'] = metrics['total_confidence_sum'] / metrics['confidence_count']

        return metrics

    def get_supported_features(self) -> List[str]:
        """Get list of supported features for Azure Document Intelligence."""
        return [
            'tables',
            'key_value_pairs',
            'languages',
            'barcodes',
            'formulas',
            'style_font',
            'ocr_high_resolution'
        ]

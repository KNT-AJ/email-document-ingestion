"""AWS Textract OCR service implementation."""

import os
import io
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import logging

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from textractor import Textractor
from textractor.data.constants import TextractFeatures
from textractor.exceptions import InvalidParameterError
from PIL import Image

from .interface import OCRServiceInterface, OCRError, OCRConfigurationError, OCRProcessingError
from ..blob_storage.service import BlobStorageService
from ...config.settings import settings


logger = logging.getLogger(__name__)


class TextractOCRService(OCRServiceInterface):
    """AWS Textract OCR service implementation."""
    
    SUPPORTED_FORMATS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}
    MAX_SYNC_FILE_SIZE = 5 * 1024 * 1024  # 5MB for synchronous processing
    
    def __init__(self, blob_storage: Optional[BlobStorageService] = None):
        """Initialize Textract OCR service.
        
        Args:
            blob_storage: Blob storage service for storing raw responses
        """
        self.blob_storage = blob_storage
        self._textractor = None
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """Validate AWS configuration."""
        try:
            # Test AWS credentials
            boto3.Session().get_credentials()
        except NoCredentialsError:
            raise OCRConfigurationError(
                "AWS credentials not found. Please configure AWS credentials.",
                service_name="textract"
            )
    
    @property
    def textractor(self) -> Textractor:
        """Get or create Textractor instance."""
        if self._textractor is None:
            kwargs = {}
            if settings.AWS_REGION:
                kwargs['region_name'] = settings.AWS_REGION
            
            self._textractor = Textractor(**kwargs)
        
        return self._textractor
    
    def analyze_document(self, document_path: Path, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a document using AWS Textract.
        
        Args:
            document_path: Path to the document file
            features: List of features to enable (e.g., ['tables', 'forms', 'layout'])
        
        Returns:
            Dictionary containing structured results
        
        Raises:
            OCRError: If document analysis fails
        """
        try:
            # Validate file format
            if document_path.suffix.lower() not in self.SUPPORTED_FORMATS:
                raise OCRProcessingError(
                    f"Unsupported file format: {document_path.suffix}. "
                    f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}",
                    service_name="textract"
                )
            
            # Convert features to Textract features
            textract_features = self._convert_features(features or [])
            
            # Determine if we need async processing
            file_size = document_path.stat().st_size
            use_async = file_size > self.MAX_SYNC_FILE_SIZE
            
            logger.info(
                f"Processing document {document_path} (size: {file_size} bytes) "
                f"with features: {textract_features}, async: {use_async}"
            )
            
            # Process document
            if use_async:
                document = self._process_async(document_path, textract_features)
            else:
                document = self._process_sync(document_path, textract_features)
            
            # Extract structured data
            result = self._extract_structured_data(document)
            
            # Store raw response if blob storage is available
            if self.blob_storage:
                try:
                    raw_response_key = self._store_raw_response(document, document_path)
                    result['raw_response_key'] = raw_response_key
                except Exception as e:
                    logger.warning(f"Failed to store raw response: {e}")
            
            return result
            
        except (InvalidParameterError, ClientError) as e:
            raise OCRProcessingError(
                f"Textract processing failed: {str(e)}",
                service_name="textract",
                original_error=e
            )
        except Exception as e:
            raise OCRError(
                f"Unexpected error during document analysis: {str(e)}",
                service_name="textract",
                original_error=e
            )
    
    def _convert_features(self, features: List[str]) -> List[TextractFeatures]:
        """Convert feature strings to Textract feature enums."""
        feature_mapping = {
            'tables': TextractFeatures.TABLES,
            'forms': TextractFeatures.FORMS,
            'layout': TextractFeatures.LAYOUT,
            'queries': TextractFeatures.QUERIES,
            'signatures': TextractFeatures.SIGNATURES
        }
        
        textract_features = []
        for feature in features:
            feature_lower = feature.lower()
            if feature_lower in feature_mapping:
                textract_features.append(feature_mapping[feature_lower])
            else:
                logger.warning(f"Unknown feature: {feature}")
        
        # Default to TABLES and FORMS if no features specified
        if not textract_features:
            textract_features = [TextractFeatures.TABLES, TextractFeatures.FORMS]
        
        return textract_features
    
    def _process_sync(self, document_path: Path, features: List[TextractFeatures]):
        """Process document synchronously."""
        return self.textractor.analyze_document(
            file_source=str(document_path),
            features=features,
            save_image=True
        )
    
    def _process_async(self, document_path: Path, features: List[TextractFeatures]):
        """Process document asynchronously."""
        if not settings.TEXTRACT_S3_BUCKET:
            raise OCRConfigurationError(
                "TEXTRACT_S3_BUCKET must be configured for async processing",
                service_name="textract"
            )
        
        s3_upload_path = f"s3://{settings.TEXTRACT_S3_BUCKET}/{settings.TEXTRACT_S3_PREFIX}"
        
        return self.textractor.start_document_analysis(
            file_source=str(document_path),
            features=features,
            s3_upload_path=s3_upload_path,
            save_image=True
        )
    
    def _extract_structured_data(self, document) -> Dict[str, Any]:
        """Extract structured data from Textract document."""
        result = {
            'text': document.text,
            'tables': [],
            'key_value_pairs': [],
            'pages': [],
            'raw_response': document.response
        }
        
        # Extract tables
        if hasattr(document, 'tables') and document.tables:
            for i, table in enumerate(document.tables):
                table_data = {
                    'table_id': i,
                    'row_count': len(table.rows) if hasattr(table, 'rows') else 0,
                    'column_count': len(table.rows[0].cells) if hasattr(table, 'rows') and table.rows else 0,
                    'cells': [],
                    'markdown': table.get_text() if hasattr(table, 'get_text') else None
                }
                
                # Extract cell data
                if hasattr(table, 'rows'):
                    for row_idx, row in enumerate(table.rows):
                        for col_idx, cell in enumerate(row.cells):
                            cell_data = {
                                'row': row_idx,
                                'column': col_idx,
                                'text': cell.text,
                                'confidence': getattr(cell, 'confidence', None)
                            }
                            table_data['cells'].append(cell_data)
                
                result['tables'].append(table_data)
        
        # Extract key-value pairs
        if hasattr(document, 'key_values') and document.key_values:
            for kv in document.key_values:
                kv_data = {
                    'key': kv.key.text if hasattr(kv.key, 'text') else str(kv.key),
                    'value': kv.value.text if hasattr(kv.value, 'text') else str(kv.value),
                    'key_confidence': getattr(kv.key, 'confidence', None),
                    'value_confidence': getattr(kv.value, 'confidence', None)
                }
                result['key_value_pairs'].append(kv_data)
        
        # Extract page information
        if hasattr(document, 'pages'):
            for i, page in enumerate(document.pages):
                page_data = {
                    'page_number': i + 1,
                    'width': getattr(page, 'width', None),
                    'height': getattr(page, 'height', None),
                    'word_count': len(page.words) if hasattr(page, 'words') else 0,
                    'line_count': len(page.lines) if hasattr(page, 'lines') else 0
                }
                result['pages'].append(page_data)
        
        return result
    
    def _store_raw_response(self, document, document_path: Path) -> str:
        """Store raw Textract response in blob storage."""
        response_json = json.dumps(document.response, indent=2)
        response_bytes = response_json.encode('utf-8')
        
        # Generate key for storage
        doc_name = document_path.stem
        key = f"textract/responses/{doc_name}_response.json"
        
        return self.blob_storage.store(
            key=key,
            data=response_bytes,
            content_type='application/json'
        )
    
    def extract_text(self, analysis_result: Dict[str, Any]) -> str:
        """Extract plain text from analysis results."""
        return analysis_result.get('text', '')
    
    def extract_tables(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables from analysis results."""
        return analysis_result.get('tables', [])
    
    def extract_key_value_pairs(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key-value pairs from analysis results."""
        return analysis_result.get('key_value_pairs', [])
    
    def calculate_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics from analysis results."""
        pages = analysis_result.get('pages', [])
        tables = analysis_result.get('tables', [])
        key_value_pairs = analysis_result.get('key_value_pairs', [])
        
        total_words = sum(page.get('word_count', 0) for page in pages)
        total_lines = sum(page.get('line_count', 0) for page in pages)
        
        # Calculate average confidence for key-value pairs
        confidences = []
        for kv in key_value_pairs:
            if kv.get('key_confidence'):
                confidences.append(kv['key_confidence'])
            if kv.get('value_confidence'):
                confidences.append(kv['value_confidence'])
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        
        return {
            'page_count': len(pages),
            'word_count': total_words,
            'line_count': total_lines,
            'table_count': len(tables),
            'key_value_pair_count': len(key_value_pairs),
            'average_confidence': avg_confidence
        }
    
    def get_supported_features(self) -> List[str]:
        """Get list of supported features for AWS Textract."""
        return ['tables', 'forms', 'layout', 'queries', 'signatures']


def create_textract_service(blob_storage: Optional[BlobStorageService] = None) -> TextractOCRService:
    """Factory function to create a configured Textract OCR service."""
    return TextractOCRService(blob_storage=blob_storage)

"""Tests for OCR workflow orchestration."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from services.ocr.workflow_config import (
    WorkflowConfig, EngineConfig, OCREngineType, QualityThresholds, OCRResult
)
from services.ocr.workflow_engine import create_ocr_engine, OCREngine
from workers.tasks.ocr_workflow import (
    process_primary_ocr,
    process_fallback_ocr,
    select_best_ocr_result,
    orchestrate_ocr_workflow
)


class MockOCRService:
    """Mock OCR service for testing."""
    
    def __init__(self, confidence=0.85, word_count=100, should_fail=False):
        self.confidence = confidence
        self.word_count = word_count
        self.should_fail = should_fail
        
    def analyze_document(self, document_path, features=None):
        if self.should_fail:
            raise Exception("Mock OCR processing failed")
            
        return {
            'text': 'This is mock extracted text from the document.',
            'confidence': self.confidence,
            'pages': [{'page_number': 1}],
            'tables': [],
            'key_value_pairs': []
        }
    
    def extract_text(self, analysis_result):
        return analysis_result['text']
    
    def extract_tables(self, analysis_result):
        return analysis_result['tables']
    
    def extract_key_value_pairs(self, analysis_result):
        return analysis_result['key_value_pairs']
    
    def calculate_metrics(self, analysis_result):
        return {
            'word_count': self.word_count,
            'page_count': 1,
            'table_count': 0,
            'average_confidence': self.confidence
        }
    
    def get_supported_features(self):
        return ['tables', 'key_value_pairs']


class MockOCREngine(OCREngine):
    """Mock OCR engine for testing."""
    
    def __init__(self, config, service=None):
        super().__init__(config)
        self._mock_service = service or MockOCRService()
    
    def _create_service(self):
        return self._mock_service


@pytest.fixture
def sample_document():
    """Create a sample document file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        f.write(b"Sample document content for OCR testing.")
        return Path(f.name)


@pytest.fixture
def azure_engine_config():
    """Sample Azure engine configuration."""
    return EngineConfig(
        engine_type=OCREngineType.AZURE,
        engine_name="Azure Document Intelligence",
        timeout_seconds=300
    )


@pytest.fixture
def google_engine_config():
    """Sample Google engine configuration."""
    return EngineConfig(
        engine_type=OCREngineType.GOOGLE,
        engine_name="Google Document AI",
        timeout_seconds=300
    )


@pytest.fixture
def workflow_config(azure_engine_config, google_engine_config):
    """Sample workflow configuration."""
    return WorkflowConfig(
        workflow_id="test_workflow",
        workflow_name="Test OCR Workflow",
        primary_engine=azure_engine_config,
        fallback_engines=[google_engine_config],
        stop_on_success=True
    )


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    with patch('workers.tasks.ocr_workflow.get_db_session') as mock_session:
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        yield mock_db


class TestOCREngineCreation:
    """Test OCR engine creation and configuration."""
    
    def test_create_ocr_engine_with_valid_config(self, azure_engine_config):
        """Test creating OCR engine with valid configuration."""
        with patch('services.ocr.workflow_engine.AzureOCREngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            
            engine = create_ocr_engine(azure_engine_config)
            
            mock_engine_class.assert_called_once_with(azure_engine_config)
            assert engine == mock_engine
    
    def test_create_ocr_engine_with_invalid_type(self):
        """Test creating OCR engine with invalid type."""
        invalid_config = EngineConfig(
            engine_type="invalid_type",
            engine_name="Invalid Engine"
        )
        
        with pytest.raises(ValueError, match="Unsupported engine type"):
            create_ocr_engine(invalid_config)


class TestOCRWorkflowConfiguration:
    """Test OCR workflow configuration validation."""
    
    def test_workflow_config_validation(self, azure_engine_config, google_engine_config):
        """Test workflow configuration validation."""
        config = WorkflowConfig(
            workflow_id="test",
            workflow_name="Test",
            primary_engine=azure_engine_config,
            fallback_engines=[google_engine_config]
        )
        
        assert config.workflow_id == "test"
        assert config.primary_engine.engine_type == OCREngineType.AZURE
        assert len(config.fallback_engines) == 1
        assert config.fallback_engines[0].engine_type == OCREngineType.GOOGLE
    
    def test_quality_thresholds_validation(self):
        """Test quality thresholds validation."""
        thresholds = QualityThresholds(
            min_confidence_score=0.8,
            min_word_recognition_rate=0.7,
            min_expected_fields_detected=0.6
        )
        
        assert thresholds.min_confidence_score == 0.8
        assert thresholds.min_word_recognition_rate == 0.7
        assert thresholds.min_expected_fields_detected == 0.6
    
    def test_quality_thresholds_out_of_range(self):
        """Test quality thresholds with out of range values."""
        with pytest.raises(ValueError):
            QualityThresholds(min_confidence_score=1.5)  # > 1.0
        
        with pytest.raises(ValueError):
            QualityThresholds(min_confidence_score=-0.1)  # < 0.0


class TestPrimaryOCRProcessing:
    """Test primary OCR processing task."""
    
    @patch('workers.tasks.ocr_workflow.create_ocr_engine')
    @patch('workers.tasks.ocr_workflow._store_ocr_result')
    def test_process_primary_ocr_success(
        self, 
        mock_store_result,
        mock_create_engine,
        sample_document,
        workflow_config,
        mock_db_session
    ):
        """Test successful primary OCR processing."""
        # Setup mocks
        mock_engine = MockOCREngine(workflow_config.primary_engine)
        mock_create_engine.return_value = mock_engine
        mock_store_result.return_value = 123
        
        # Execute task
        result = process_primary_ocr(
            document_id=1,
            document_path=str(sample_document),
            workflow_config_dict=workflow_config.dict(),
            execution_id="test-execution-id"
        )
        
        # Verify results
        assert result['success'] is True
        assert result['document_id'] == 1
        assert result['execution_id'] == "test-execution-id"
        assert result['ocr_run_id'] == 123
        assert result['engine_type'] == 'azure'
        assert 'ocr_result' in result
        assert 'evaluation_details' in result
        
        # Verify mocks were called
        mock_create_engine.assert_called_once()
        mock_store_result.assert_called_once()
    
    @patch('workers.tasks.ocr_workflow.create_ocr_engine')
    @patch('workers.tasks.ocr_workflow._store_ocr_error')
    def test_process_primary_ocr_failure(
        self,
        mock_store_error,
        mock_create_engine,
        sample_document,
        workflow_config,
        mock_db_session
    ):
        """Test primary OCR processing failure."""
        # Setup mocks to fail
        mock_service = MockOCRService(should_fail=True)
        mock_engine = MockOCREngine(workflow_config.primary_engine, mock_service)
        mock_create_engine.return_value = mock_engine
        mock_store_error.return_value = 456
        
        # Execute task
        result = process_primary_ocr(
            document_id=1,
            document_path=str(sample_document),
            workflow_config_dict=workflow_config.dict(),
            execution_id="test-execution-id"
        )
        
        # Verify results
        assert result['success'] is False
        assert result['document_id'] == 1
        assert 'error' in result
        assert result['engine_type'] == 'azure'
        
        # Verify error was stored
        mock_store_error.assert_called_once()


class TestFallbackOCRProcessing:
    """Test fallback OCR processing task."""
    
    @patch('workers.tasks.ocr_workflow.create_ocr_engine')
    @patch('workers.tasks.ocr_workflow._store_ocr_result')
    def test_process_fallback_ocr_success(
        self,
        mock_store_result,
        mock_create_engine,
        sample_document,
        google_engine_config,
        mock_db_session
    ):
        """Test successful fallback OCR processing."""
        # Setup mocks
        mock_engine = MockOCREngine(google_engine_config)
        mock_create_engine.return_value = mock_engine
        mock_store_result.return_value = 789
        
        # Execute task
        result = process_fallback_ocr(
            document_id=1,
            document_path=str(sample_document),
            engine_config_dict=google_engine_config.dict(),
            execution_id="test-execution-id"
        )
        
        # Verify results
        assert result['success'] is True
        assert result['document_id'] == 1
        assert result['execution_id'] == "test-execution-id"
        assert result['ocr_run_id'] == 789
        assert result['engine_type'] == 'google'
        
        # Verify mocks were called
        mock_create_engine.assert_called_once()
        mock_store_result.assert_called_once()


class TestResultSelection:
    """Test OCR result selection logic."""
    
    @patch('workers.tasks.ocr_workflow._update_document_with_best_result')
    def test_select_best_result_highest_confidence(self, mock_update_doc, workflow_config):
        """Test selecting result with highest confidence."""
        # Create mock results
        primary_result = {
            'success': True,
            'document_id': 1,
            'engine_name': 'Azure',
            'ocr_result': {
                'confidence_score': 0.85,
                'word_count': 100,
                'extracted_text': 'Primary text'
            }
        }
        
        fallback_results = [
            {
                'success': True,
                'document_id': 1,
                'engine_name': 'Google',
                'ocr_result': {
                    'confidence_score': 0.92,
                    'word_count': 95,
                    'extracted_text': 'Fallback text'
                }
            }
        ]
        
        # Execute task
        result = select_best_ocr_result(
            primary_result=primary_result,
            fallback_results=fallback_results,
            workflow_config_dict=workflow_config.dict(),
            execution_id="test-execution-id"
        )
        
        # Verify Google result was selected (higher confidence)
        assert result['selected_result']['engine_name'] == 'Google'
        assert result['selected_result']['ocr_result']['confidence_score'] == 0.92
        assert result['total_results'] == 2
        
        # Verify document was updated
        mock_update_doc.assert_called_once()
    
    @patch('workers.tasks.ocr_workflow._update_document_with_best_result')
    def test_select_best_result_no_successful_results(self, mock_update_doc, workflow_config):
        """Test result selection when no results are successful."""
        primary_result = {'success': False, 'error': 'Primary failed'}
        fallback_results = [{'success': False, 'error': 'Fallback failed'}]
        
        # Execute task - should raise exception
        with pytest.raises(Exception, match="No successful OCR results"):
            select_best_ocr_result(
                primary_result=primary_result,
                fallback_results=fallback_results,
                workflow_config_dict=workflow_config.dict(),
                execution_id="test-execution-id"
            )


class TestWorkflowOrchestration:
    """Test complete workflow orchestration."""
    
    @patch('workers.tasks.ocr_workflow.process_primary_ocr')
    @patch('workers.tasks.ocr_workflow._update_document_with_best_result')
    def test_orchestrate_workflow_primary_success_stop_on_success(
        self,
        mock_update_doc,
        mock_primary_task,
        sample_document,
        workflow_config
    ):
        """Test workflow orchestration when primary succeeds and stop_on_success is True."""
        # Setup mock primary result that meets quality
        mock_primary_result = {
            'success': True,
            'meets_quality': True,
            'document_id': 1,
            'engine_name': 'Azure',
            'ocr_result': {
                'confidence_score': 0.90,
                'word_count': 100,
                'extracted_text': 'Primary text',
                'engine_type': 'azure',
                'engine_name': 'Azure Document Intelligence',
                'processing_time_seconds': 15.5,
                'processed_at': datetime.utcnow().isoformat(),
                'page_count': 1,
                'extracted_tables': [],
                'extracted_key_value_pairs': [],
                'quality_metrics': {}
            }
        }
        
        # Mock the task execution
        mock_task_instance = Mock()
        mock_task_instance.apply.return_value.get.return_value = mock_primary_result
        mock_primary_task.s.return_value = mock_task_instance
        
        # Execute workflow
        result = orchestrate_ocr_workflow(
            document_id=1,
            document_path=str(sample_document),
            workflow_config_name="azure_primary"
        )
        
        # Verify workflow completed with primary result only
        assert result['status'] == 'completed'
        assert result['document_id'] == 1
        assert result['selected_result']['engine_name'] == 'Azure'
        assert result['fallback_results'] == []
        assert 'execution_id' in result
        assert 'total_processing_time' in result
        
        # Verify document was updated
        mock_update_doc.assert_called_once()
    
    @patch('workers.tasks.ocr_workflow.process_primary_ocr')
    @patch('workers.tasks.ocr_workflow.process_fallback_ocr')
    @patch('workers.tasks.ocr_workflow.select_best_ocr_result')
    def test_orchestrate_workflow_with_fallbacks(
        self,
        mock_select_task,
        mock_fallback_task,
        mock_primary_task,
        sample_document,
        workflow_config
    ):
        """Test workflow orchestration with fallback engines."""
        # Modify config to not stop on success
        workflow_config.stop_on_success = False
        
        # Setup mock results
        mock_primary_result = {
            'success': True,
            'meets_quality': False,  # Low quality to trigger fallbacks
            'document_id': 1,
            'engine_name': 'Azure',
            'ocr_result': {
                'confidence_score': 0.60,
                'word_count': 50,
                'extracted_text': 'Primary text',
                'engine_type': 'azure',
                'engine_name': 'Azure Document Intelligence',
                'processing_time_seconds': 15.5,
                'processed_at': datetime.utcnow().isoformat(),
                'page_count': 1,
                'extracted_tables': [],
                'extracted_key_value_pairs': [],
                'quality_metrics': {}
            }
        }
        
        mock_fallback_result = {
            'success': True,
            'meets_quality': True,
            'document_id': 1,
            'engine_name': 'Google',
            'ocr_result': {
                'confidence_score': 0.90,
                'word_count': 100,
                'extracted_text': 'Fallback text',
                'engine_type': 'google',
                'engine_name': 'Google Document AI',
                'processing_time_seconds': 12.3,
                'processed_at': datetime.utcnow().isoformat(),
                'page_count': 1,
                'extracted_tables': [],
                'extracted_key_value_pairs': [],
                'quality_metrics': {}
            }
        }
        
        mock_selection_result = {
            'selected_result': mock_fallback_result,
            'total_results': 2,
            'selection_strategy': 'highest_confidence'
        }
        
        # Mock task executions
        mock_primary_task_instance = Mock()
        mock_primary_task_instance.apply.return_value.get.return_value = mock_primary_result
        mock_primary_task.s.return_value = mock_primary_task_instance
        
        mock_fallback_task_instance = Mock()
        mock_fallback_task_instance.apply.return_value.get.return_value = mock_fallback_result
        mock_fallback_task.s.return_value = mock_fallback_task_instance
        
        mock_select_task_instance = Mock()
        mock_select_task_instance.apply.return_value.get.return_value = mock_selection_result
        mock_select_task.s.return_value = mock_select_task_instance
        
        # Execute workflow
        result = orchestrate_ocr_workflow(
            document_id=1,
            document_path=str(sample_document),
            workflow_config_overrides={'stop_on_success': False}
        )
        
        # Verify workflow completed with both results
        assert result['status'] == 'completed'
        assert result['document_id'] == 1
        assert len(result['fallback_results']) == 1
        assert result['selected_result']['engine_name'] == 'Google'
        
        # Verify all tasks were called
        mock_primary_task.s.assert_called_once()
        mock_fallback_task.s.assert_called_once()
        mock_select_task.s.assert_called_once()


class TestQualityEvaluation:
    """Test OCR quality evaluation logic."""
    
    def test_quality_evaluation_passes_all_thresholds(self, azure_engine_config):
        """Test quality evaluation when all thresholds are met."""
        engine = MockOCREngine(azure_engine_config)
        
        # Create a high-quality result
        result = OCRResult(
            engine_type=OCREngineType.AZURE,
            engine_name="Azure Document Intelligence",
            processing_time_seconds=15.5,
            processed_at=datetime.utcnow().isoformat(),
            confidence_score=0.92,
            word_count=150,
            page_count=1,
            extracted_text="High quality extracted text with good confidence.",
            extracted_tables=[],
            extracted_key_value_pairs=[]
        )
        
        thresholds = QualityThresholds(
            min_confidence_score=0.8,
            min_word_recognition_rate=0.7,
            max_processing_time_seconds=30
        )
        
        meets_quality, evaluation = engine.evaluate_quality(result, thresholds)
        
        assert meets_quality is True
        assert evaluation['overall_quality'] is True
        assert evaluation['confidence_check'] is True
        assert evaluation['word_count_check'] is True
        assert evaluation['processing_time_check'] is True
    
    def test_quality_evaluation_fails_confidence_threshold(self, azure_engine_config):
        """Test quality evaluation when confidence threshold is not met."""
        engine = MockOCREngine(azure_engine_config)
        
        # Create a low-confidence result
        result = OCRResult(
            engine_type=OCREngineType.AZURE,
            engine_name="Azure Document Intelligence",
            processing_time_seconds=15.5,
            processed_at=datetime.utcnow().isoformat(),
            confidence_score=0.55,  # Below threshold
            word_count=150,
            page_count=1,
            extracted_text="Low confidence extracted text.",
            extracted_tables=[],
            extracted_key_value_pairs=[]
        )
        
        thresholds = QualityThresholds(
            min_confidence_score=0.8,  # Higher than result
            min_word_recognition_rate=0.7,
            max_processing_time_seconds=30
        )
        
        meets_quality, evaluation = engine.evaluate_quality(result, thresholds)
        
        assert meets_quality is False
        assert evaluation['overall_quality'] is False
        assert evaluation['confidence_check'] is False
        assert evaluation['word_count_check'] is True
        assert evaluation['processing_time_check'] is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

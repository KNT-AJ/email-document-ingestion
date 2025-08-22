"""OCR workflow configuration models and schemas."""

from typing import List, Dict, Any, Optional, Union
from datetime import timedelta
from pydantic import BaseModel, Field, validator
from enum import Enum


class OCREngineType(str, Enum):
    """Supported OCR engine types."""
    AZURE = "azure"
    GOOGLE = "google"
    MISTRAL = "mistral"
    TESSERACT = "tesseract"
    PADDLE = "paddle"
    TEXTRACT = "textract"


class RetryPolicy(BaseModel):
    """Retry policy configuration for OCR operations."""
    
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum number of retries")
    backoff_factor: float = Field(default=2.0, ge=1.0, le=10.0, description="Exponential backoff factor")
    max_backoff_seconds: int = Field(default=300, ge=1, le=3600, description="Maximum backoff time in seconds")
    retry_exceptions: List[str] = Field(
        default=["ConnectionError", "TimeoutError", "OCRProcessingError"],
        description="Exception types to retry on"
    )


class QualityThresholds(BaseModel):
    """Quality thresholds for OCR result evaluation."""
    
    min_confidence_score: float = Field(
        default=0.7, ge=0.0, le=1.0, 
        description="Minimum average confidence score (0.0-1.0)"
    )
    min_word_recognition_rate: float = Field(
        default=0.8, ge=0.0, le=1.0,
        description="Minimum word recognition rate (0.0-1.0)"
    )
    min_expected_fields_detected: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Minimum ratio of expected fields detected (0.0-1.0)"
    )
    max_processing_time_seconds: int = Field(
        default=300, ge=1, le=3600,
        description="Maximum allowed processing time in seconds"
    )
    min_pages_processed: int = Field(
        default=1, ge=1,
        description="Minimum number of pages that must be processed"
    )
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True


class EngineConfig(BaseModel):
    """Configuration for a specific OCR engine."""
    
    engine_type: OCREngineType = Field(description="Type of OCR engine")
    engine_name: str = Field(description="Human-readable name for the engine")
    enabled: bool = Field(default=True, description="Whether this engine is enabled")
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Engine-specific timeout")
    
    # Engine-specific configuration
    config_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Engine-specific configuration parameters"
    )
    
    # Quality settings for this engine
    quality_thresholds: Optional[QualityThresholds] = Field(
        default=None,
        description="Engine-specific quality thresholds (overrides global)"
    )
    
    # Retry policy for this engine
    retry_policy: Optional[RetryPolicy] = Field(
        default=None,
        description="Engine-specific retry policy (overrides global)"
    )
    
    # Preprocessing options
    preprocessing_enabled: bool = Field(
        default=True,
        description="Whether to apply preprocessing before OCR"
    )
    preprocessing_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "grayscale": True,
            "adaptive_threshold": True,
            "noise_reduction": True,
            "skew_correction": True,
            "dpi_optimization": True
        },
        description="Preprocessing configuration options"
    )


class WorkflowConfig(BaseModel):
    """Complete OCR workflow configuration."""
    
    # Workflow identification
    workflow_id: str = Field(description="Unique identifier for this workflow configuration")
    workflow_name: str = Field(description="Human-readable name for the workflow")
    version: str = Field(default="1.0", description="Configuration version")
    
    # Engine chain configuration
    primary_engine: EngineConfig = Field(description="Primary OCR engine configuration")
    fallback_engines: List[EngineConfig] = Field(
        default_factory=list,
        description="Ordered list of fallback engines"
    )
    
    # Global quality thresholds
    global_quality_thresholds: QualityThresholds = Field(
        default_factory=QualityThresholds,
        description="Global quality thresholds for all engines"
    )
    
    # Global retry policy
    global_retry_policy: RetryPolicy = Field(
        default_factory=RetryPolicy,
        description="Global retry policy for all engines"
    )
    
    # Workflow behavior
    stop_on_success: bool = Field(
        default=True,
        description="Stop processing when quality thresholds are met"
    )
    parallel_fallbacks: bool = Field(
        default=False,
        description="Run fallback engines in parallel instead of sequence"
    )
    max_parallel_engines: int = Field(
        default=3, ge=1, le=10,
        description="Maximum number of engines to run in parallel"
    )
    
    # Result selection strategy
    result_selection_strategy: str = Field(
        default="highest_confidence",
        description="Strategy for selecting best result",
        regex="^(highest_confidence|consensus|weighted_average|first_success)$"
    )
    
    # Workflow timeouts
    total_workflow_timeout_seconds: int = Field(
        default=1800, ge=60, le=7200,
        description="Total timeout for the entire workflow"
    )
    
    # Circuit breaker configuration
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker to prevent infinite loops"
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5, ge=1, le=20,
        description="Number of failures before opening circuit breaker"
    )
    circuit_breaker_recovery_timeout_seconds: int = Field(
        default=300, ge=60, le=3600,
        description="Time to wait before attempting to close circuit breaker"
    )
    
    # Monitoring and logging
    detailed_logging: bool = Field(
        default=True,
        description="Enable detailed workflow logging"
    )
    store_intermediate_results: bool = Field(
        default=True,
        description="Store results from all engines for analysis"
    )
    performance_monitoring: bool = Field(
        default=True,
        description="Enable performance metrics collection"
    )
    
    @validator('fallback_engines')
    def validate_fallback_engines(cls, v, values):
        """Validate that fallback engines don't duplicate primary engine."""
        if 'primary_engine' in values:
            primary_type = values['primary_engine'].engine_type
            for engine in v:
                if engine.engine_type == primary_type:
                    raise ValueError(f"Fallback engine {engine.engine_type} cannot be the same as primary engine")
        return v
    
    @validator('max_parallel_engines')
    def validate_max_parallel_engines(cls, v, values):
        """Validate that max parallel engines doesn't exceed available fallbacks."""
        if 'fallback_engines' in values:
            available_engines = len(values['fallback_engines']) + 1  # +1 for primary
            if v > available_engines:
                return available_engines
        return v


class OCRResult(BaseModel):
    """Standardized OCR result format."""
    
    # Engine information
    engine_type: OCREngineType = Field(description="OCR engine that produced this result")
    engine_name: str = Field(description="Human-readable engine name")
    
    # Processing metadata
    processing_time_seconds: float = Field(description="Time taken to process the document")
    processed_at: str = Field(description="ISO timestamp when processing completed")
    
    # Quality metrics
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence score (0.0-1.0)"
    )
    word_count: int = Field(ge=0, description="Total number of words extracted")
    page_count: int = Field(ge=0, description="Number of pages processed")
    
    # Content
    extracted_text: str = Field(description="Full extracted text content")
    extracted_tables: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted tables data"
    )
    extracted_key_value_pairs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted key-value pairs"
    )
    
    # Additional metadata
    language_detected: Optional[str] = Field(
        default=None,
        description="Detected document language"
    )
    
    # Raw response storage path
    raw_response_path: Optional[str] = Field(
        default=None,
        description="Path to stored raw OCR engine response"
    )
    
    # Quality assessment
    quality_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed quality metrics for this result"
    )


class WorkflowStatus(BaseModel):
    """Workflow execution status tracking."""
    
    # Workflow identification
    workflow_id: str = Field(description="Workflow configuration ID")
    execution_id: str = Field(description="Unique execution instance ID")
    document_id: str = Field(description="Document being processed")
    
    # Status tracking
    status: str = Field(description="Current workflow status")
    started_at: str = Field(description="ISO timestamp when workflow started")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when workflow completed")
    
    # Progress tracking
    current_engine: Optional[str] = Field(default=None, description="Currently executing engine")
    engines_completed: List[str] = Field(default_factory=list, description="Engines that have completed")
    engines_failed: List[str] = Field(default_factory=list, description="Engines that failed")
    
    # Results
    primary_result: Optional[OCRResult] = Field(default=None, description="Primary engine result")
    fallback_results: List[OCRResult] = Field(default_factory=list, description="Fallback engine results")
    selected_result: Optional[OCRResult] = Field(default=None, description="Final selected result")
    
    # Error tracking
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Errors encountered during workflow")
    
    # Performance metrics
    total_processing_time_seconds: Optional[float] = Field(default=None, description="Total workflow processing time")
    
    
# Default workflow configurations
DEFAULT_AZURE_PRIMARY_CONFIG = WorkflowConfig(
    workflow_id="default_azure_primary",
    workflow_name="Azure Primary with Google Fallback",
    primary_engine=EngineConfig(
        engine_type=OCREngineType.AZURE,
        engine_name="Azure Document Intelligence",
        timeout_seconds=300
    ),
    fallback_engines=[
        EngineConfig(
            engine_type=OCREngineType.GOOGLE,
            engine_name="Google Document AI",
            timeout_seconds=300
        ),
        EngineConfig(
            engine_type=OCREngineType.TESSERACT,
            engine_name="Tesseract OCR",
            timeout_seconds=180
        )
    ]
)

DEFAULT_GOOGLE_PRIMARY_CONFIG = WorkflowConfig(
    workflow_id="default_google_primary",
    workflow_name="Google Primary with Azure Fallback",
    primary_engine=EngineConfig(
        engine_type=OCREngineType.GOOGLE,
        engine_name="Google Document AI",
        timeout_seconds=300
    ),
    fallback_engines=[
        EngineConfig(
            engine_type=OCREngineType.AZURE,
            engine_name="Azure Document Intelligence",
            timeout_seconds=300
        ),
        EngineConfig(
            engine_type=OCREngineType.TESSERACT,
            engine_name="Tesseract OCR",
            timeout_seconds=180
        )
    ]
)

DEFAULT_OPENSOURCE_CONFIG = WorkflowConfig(
    workflow_id="default_opensource",
    workflow_name="Open Source OCR Engines",
    primary_engine=EngineConfig(
        engine_type=OCREngineType.TESSERACT,
        engine_name="Tesseract OCR",
        timeout_seconds=300
    ),
    fallback_engines=[
        EngineConfig(
            engine_type=OCREngineType.PADDLE,
            engine_name="PaddleOCR",
            timeout_seconds=300
        )
    ]
)


def get_default_workflow_config(config_type: str = "azure_primary") -> WorkflowConfig:
    """Get a default workflow configuration.
    
    Args:
        config_type: Type of default config ("azure_primary", "google_primary", "opensource")
        
    Returns:
        Default workflow configuration
        
    Raises:
        ValueError: If config_type is not supported
    """
    configs = {
        "azure_primary": DEFAULT_AZURE_PRIMARY_CONFIG,
        "google_primary": DEFAULT_GOOGLE_PRIMARY_CONFIG,
        "opensource": DEFAULT_OPENSOURCE_CONFIG
    }
    
    if config_type not in configs:
        raise ValueError(f"Unsupported config type: {config_type}. Available: {list(configs.keys())}")
    
    return configs[config_type]

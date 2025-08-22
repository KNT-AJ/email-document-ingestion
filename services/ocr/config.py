"""Configuration for OCR services."""

from typing import Optional, List
from pydantic import BaseModel, Field

from config import get_settings


class OCRConfig(BaseModel):
    """Configuration for OCR services."""

    # Azure Document Intelligence settings
    azure_endpoint: Optional[str] = Field(None, env="AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    azure_api_key: Optional[str] = Field(None, env="AZURE_DOCUMENT_INTELLIGENCE_API_KEY")
    azure_model: str = Field("prebuilt-layout", env="AZURE_DOCUMENT_INTELLIGENCE_MODEL")

    # Mistral Document AI settings
    mistral_api_key: Optional[str] = Field(None, env="MISTRAL_API_KEY")
    mistral_base_url: str = Field("https://api.mistral.ai", env="MISTRAL_BASE_URL")
    mistral_model: str = Field("mistral-large-latest", env="MISTRAL_MODEL")

    # General OCR settings
    max_polling_time: int = Field(300, env="OCR_MAX_POLLING_TIME")  # 5 minutes default
    polling_interval: int = Field(2, env="OCR_POLLING_INTERVAL")  # 2 seconds default
    default_features: List[str] = Field(
        default=["tables", "key_value_pairs"],
        env="OCR_DEFAULT_FEATURES"
    )

    # Service type
    service_type: str = Field("azure", env="OCR_SERVICE_TYPE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_service_type(self) -> str:
        """Get the configured OCR service type."""
        return self.service_type

    def is_azure_configured(self) -> bool:
        """Check if Azure Document Intelligence is properly configured."""
        return bool(self.azure_endpoint and self.azure_api_key)

    def get_azure_config(self) -> dict:
        """Get Azure Document Intelligence configuration."""
        return {
            "endpoint": self.azure_endpoint,
            "api_key": self.azure_api_key,
            "model": self.azure_model
        }

    def is_mistral_configured(self) -> bool:
        """Check if Mistral Document AI is properly configured."""
        return bool(self.mistral_api_key)

    def get_mistral_config(self) -> dict:
        """Get Mistral Document AI configuration."""
        return {
            "api_key": self.mistral_api_key,
            "base_url": self.mistral_base_url,
            "model": self.mistral_model
        }


def get_config() -> OCRConfig:
    """Get the global OCR configuration."""
    return OCRConfig()


# Global configuration instance
_config: Optional[OCRConfig] = None


def get_ocr_config() -> OCRConfig:
    """Get the OCR configuration, using settings from the main config module."""
    global _config

    if _config is None:
        # Use the main settings to populate OCR config
        settings = get_settings()
        _config = OCRConfig(
            azure_endpoint=getattr(settings, 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT', None),
            azure_api_key=getattr(settings, 'AZURE_DOCUMENT_INTELLIGENCE_API_KEY', None),
            azure_model=getattr(settings, 'AZURE_DOCUMENT_INTELLIGENCE_MODEL', 'prebuilt-layout'),
            mistral_api_key=getattr(settings, 'MISTRAL_API_KEY', None),
            mistral_base_url=getattr(settings, 'MISTRAL_BASE_URL', 'https://api.mistral.ai'),
            mistral_model=getattr(settings, 'MISTRAL_MODEL', 'mistral-large-latest'),
            max_polling_time=getattr(settings, 'OCR_MAX_POLLING_TIME', 300),
            polling_interval=getattr(settings, 'OCR_POLLING_INTERVAL', 2),
            service_type=getattr(settings, 'OCR_SERVICE_TYPE', 'azure')
        )

    return _config

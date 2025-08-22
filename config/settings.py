"""Application settings using Pydantic BaseSettings."""

try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older Pydantic versions
    from pydantic import BaseSettings

from pydantic import Field, validator
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application settings
    APP_NAME: str = "Email & Document Ingestion System"
    VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    API_PREFIX: str = Field(default="/api", env="API_PREFIX")

    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")

    # Database settings
    DATABASE_URL: str = Field(
        default="postgresql://user:password@localhost:5432/email_ingest",
        env="DATABASE_URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")

    # Redis settings
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # Celery settings
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    CELERY_TASK_SERIALIZER: str = Field(default="json", env="CELERY_TASK_SERIALIZER")
    CELERY_ACCEPT_CONTENT: List[str] = Field(default=["json"], env="CELERY_ACCEPT_CONTENT")
    CELERY_RESULT_SERIALIZER: str = Field(default="json", env="CELERY_RESULT_SERIALIZER")
    CELERY_TIMEZONE: str = Field(default="UTC", env="CELERY_TIMEZONE")
    CELERY_ENABLE_UTC: bool = Field(default=True, env="CELERY_ENABLE_UTC")

    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    LOG_FILE_PATH: Optional[str] = Field(default=None, env="LOG_FILE_PATH")
    LOG_MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, env="LOG_MAX_FILE_SIZE")  # 10MB
    LOG_BACKUP_COUNT: int = Field(default=5, env="LOG_BACKUP_COUNT")
    ENABLE_FILE_LOGGING: bool = Field(default=False, env="ENABLE_FILE_LOGGING")

    # File storage settings
    STORAGE_TYPE: str = Field(default="local", env="STORAGE_TYPE")  # local, s3
    LOCAL_STORAGE_PATH: str = Field(default="./storage", env="LOCAL_STORAGE_PATH")

    # S3 settings
    S3_BUCKET_NAME: Optional[str] = Field(default=None, env="S3_BUCKET_NAME")
    S3_REGION: Optional[str] = Field(default=None, env="S3_REGION")
    S3_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="S3_SECRET_ACCESS_KEY")
    S3_ENDPOINT_URL: Optional[str] = Field(default=None, env="S3_ENDPOINT_URL")

    # Gmail API settings
    GMAIL_CLIENT_ID: Optional[str] = Field(default=None, env="GMAIL_CLIENT_ID")
    GMAIL_CLIENT_SECRET: Optional[str] = Field(default=None, env="GMAIL_CLIENT_SECRET")
    GMAIL_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/gmail/callback",
    env="GMAIL_REDIRECT_URI"
    )

    # Gmail Push Notification settings
    PUBSUB_AUDIENCE: str = Field(
        default="https://example.com/api/gmail/push",
        env="PUBSUB_AUDIENCE"
    )

    # OCR Engine settings
    OCR_ENGINE: str = Field(default="tesseract", env="OCR_ENGINE")  # tesseract, google, azure, textract, mistral

    # Google Document AI settings
    GOOGLE_DOCUMENT_AI_ENDPOINT: Optional[str] = Field(default=None, env="GOOGLE_DOCUMENT_AI_ENDPOINT")
    GOOGLE_CREDENTIALS_PATH: Optional[str] = Field(default=None, env="GOOGLE_CREDENTIALS_PATH")

    # Azure AI settings
    AZURE_AI_ENDPOINT: Optional[str] = Field(default=None, env="AZURE_AI_ENDPOINT")
    AZURE_AI_KEY: Optional[str] = Field(default=None, env="AZURE_AI_KEY")

    # AWS Textract settings
    AWS_REGION: Optional[str] = Field(default="us-east-1", env="AWS_REGION")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN: Optional[str] = Field(default=None, env="AWS_SESSION_TOKEN")
    TEXTRACT_S3_BUCKET: Optional[str] = Field(default=None, env="TEXTRACT_S3_BUCKET")
    TEXTRACT_S3_PREFIX: str = Field(default="textract/", env="TEXTRACT_S3_PREFIX")

    # Mistral AI settings
    MISTRAL_API_KEY: Optional[str] = Field(default=None, env="MISTRAL_API_KEY")

    # Security settings
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
    env="SECRET_KEY"
    )
    JWT_SECRET_KEY: str = Field(
        default="your-jwt-secret-key-change-in-production",
    env="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_HOURS: int = Field(default=24, env="JWT_EXPIRATION_HOURS")

    # CORS settings
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
    env="CORS_ORIGINS"
    )

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # Batch processing settings
    BATCH_SIZE: int = Field(default=10, env="BATCH_SIZE")
    MAX_CONCURRENT_TASKS: int = Field(default=4, env="MAX_CONCURRENT_TASKS")

class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Allow extra environment variables

@validator("DATABASE_URL")
def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("Database URL must be a valid PostgreSQL connection string")
        return v

@validator("REDIS_URL")
def validate_redis_url(cls, v):
        """Validate Redis URL format."""
        if not v.startswith("redis://"):
            raise ValueError("Redis URL must start with redis://")
        return v

@validator("LOG_LEVEL")
def validate_log_level(cls, v):
        """Validate log level."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v.upper()

@validator("STORAGE_TYPE")
def validate_storage_type(cls, v):
        """Validate storage type."""
        allowed_types = ["local", "s3"]
        if v.lower() not in allowed_types:
            raise ValueError(f"Storage type must be one of: {allowed_types}")
        return v.lower()

def get_environment(self) -> str:
        """Get current environment name."""
        return os.getenv("ENVIRONMENT", "development").lower()

def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.get_environment() == "development"

def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.get_environment() == "production"

def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.get_environment() == "testing"


# Global settings instance
settings = Settings()

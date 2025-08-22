"""Development environment settings."""

from ..settings import Settings


class DevelopmentSettings(Settings):
    """Settings for development environment."""

    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "console"

    # Development database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/email_ingest_dev"

    # Development Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Development Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Development storage
    STORAGE_TYPE: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"

    # Development CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5173",
    ]

    # Development rate limiting
    RATE_LIMIT_PER_MINUTE: int = 1000

    class Config:
        """Development configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra environment variables

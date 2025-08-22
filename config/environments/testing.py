"""Testing environment settings."""

from ..settings import Settings


class TestingSettings(Settings):
    """Settings for testing environment."""

    DEBUG: bool = True
    LOG_LEVEL: str = "WARNING"
    LOG_FORMAT: str = "console"

    # Test database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/email_ingest_test"

    # Test Redis
    REDIS_URL: str = "redis://localhost:6379/1"

    # Test Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Test storage
    STORAGE_TYPE: str = "local"
    LOCAL_STORAGE_PATH: str = "./test_storage"

    # Test settings
    SECRET_KEY: str = "test-secret-key"
    JWT_SECRET_KEY: str = "test-jwt-secret-key"

    # Test CORS - permissive for testing
    CORS_ORIGINS: list = ["*"]

    # Test rate limiting - no limits
    RATE_LIMIT_PER_MINUTE: int = 10000

    # Test batch settings
    BATCH_SIZE: int = 5
    MAX_CONCURRENT_TASKS: int = 2

    class Config:
        """Testing configuration."""
        env_file = ".env.test"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra environment variables

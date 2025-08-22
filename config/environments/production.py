"""Production environment settings."""

from ..settings import Settings


class ProductionSettings(Settings):
    """Settings for production environment."""

    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Production security
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION"
    JWT_SECRET_KEY: str = "CHANGE_THIS_JWT_SECRET_IN_PRODUCTION"

    # Production CORS - more restrictive
    CORS_ORIGINS: list = [
        "https://yourdomain.com",
        "https://www.yourdomain.com",
    ]

    # Production rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Production batch settings
    BATCH_SIZE: int = 50
    MAX_CONCURRENT_TASKS: int = 8

    class Config:
        """Production configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra environment variables

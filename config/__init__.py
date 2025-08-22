"""Configuration package for the email and document ingestion system."""

import os
from functools import lru_cache
from .settings import Settings
from .environments.development import DevelopmentSettings
from .environments.production import ProductionSettings
from .environments.testing import TestingSettings


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings based on environment."""
    environment = os.getenv("ENVIRONMENT", "development").lower()

    settings_map = {
        "development": DevelopmentSettings,
        "production": ProductionSettings,
        "testing": TestingSettings,
    }

    settings_class = settings_map.get(environment, DevelopmentSettings)
    return settings_class()

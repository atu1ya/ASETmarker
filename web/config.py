"""Application configuration for the ASET Marking System."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    SECRET_KEY: str = Field(
        default="dev-secret-key",
        description="Secret key used for session signing",
    )
    STAFF_PASSWORD: str = Field(
        default="everest2024", description="Shared staff password for authentication"
    )
    DEBUG: bool = Field(default=False, description="Enable FastAPI debug mode")
    SESSION_DURATION_HOURS: int = Field(default=8, ge=1, description="Session lifetime")
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, ge=1, description="Maximum upload size")
    ALLOWED_EXTENSIONS: list[str] = Field(default_factory=lambda: [".png"])
    CONFIG_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent / "config",
        description="Directory containing OMR configuration templates",
    )
    ASSETS_DIR: Path = Field(
        default=Path(__file__).resolve().parent.parent / "assets",
        description="Directory containing static assets such as fonts and logos",
    )

    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""
    return Settings()

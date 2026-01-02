"""Reusable FastAPI dependencies."""
from fastapi import Depends, HTTPException, Request, status

from web.auth import SESSION_COOKIE_NAME, validate_session
from web.config import Settings, get_settings as _get_settings
from web.session_store import MarkingConfiguration, config_store


def get_settings() -> Settings:
    """Return application settings (cached)."""
    return _get_settings()


def get_current_session(request: Request) -> str:
    """Ensure the request originates from an authenticated session."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not validate_session(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return token  # token is guaranteed to be non-empty when valid


def get_optional_session(request: Request) -> str | None:
    """Return session token if present and valid, otherwise None."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    if not validate_session(token):
        return None
    return token


def get_marking_config(session_token: str = Depends(get_current_session)) -> MarkingConfiguration:
    """Retrieve the marking configuration for the current session."""
    config = config_store.get(session_token)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marking configuration not found for this session.",
        )
    return config


def require_configuration(config: MarkingConfiguration = Depends(get_marking_config)) -> MarkingConfiguration:
    """Ensure the current session has completed configuration."""
    if not config.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marking configuration incomplete for this session.",
        )
    return config

"""Password-based authentication helpers for the ASET Marking System."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict

from web.config import get_settings


SESSION_COOKIE_NAME = "session_token"

_sessions: Dict[str, datetime] = {}
_sessions_lock = Lock()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# Exposed for tests
STAFF_PASSWORD_HASH = _hash_password(get_settings().STAFF_PASSWORD)


def verify_password(password: str) -> bool:
    """Return True if the supplied password matches the configured password."""
    if not password:
        return False
    expected_hash = _hash_password(get_settings().STAFF_PASSWORD)
    return secrets.compare_digest(expected_hash, _hash_password(password))


def create_session() -> str:
    """Create a new session token with an expiry timestamp."""
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    expiry = datetime.utcnow() + timedelta(hours=settings.SESSION_DURATION_HOURS)
    with _sessions_lock:
        _sessions[token] = expiry
    return token


def validate_session(token: str) -> bool:
    """Check whether the provided session token is valid and not expired."""
    if not token:
        return False
    now = datetime.utcnow()
    with _sessions_lock:
        expiry = _sessions.get(token)
        if not expiry:
            return False
        if expiry < now:
            _sessions.pop(token, None)
            return False
        return True


def invalidate_session(token: str) -> None:
    """Invalidate a session token immediately."""
    if not token:
        return
    with _sessions_lock:
        _sessions.pop(token, None)


def cleanup_expired_sessions() -> None:
    """Remove expired sessions from the in-memory store."""
    now = datetime.utcnow()
    with _sessions_lock:
        expired_tokens = [token for token, expiry in _sessions.items() if expiry < now]
        for token in expired_tokens:
            _sessions.pop(token, None)

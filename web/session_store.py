"""
In-memory storage for session-based marking configurations.
Each staff session can have its own answer keys and concept mapping.
Data is lost on server restart (by design - no persistent storage).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import threading


@dataclass
class MarkingConfiguration:
    """Stores uploaded marking configuration for a session."""

    reading_answers: list[str] = field(default_factory=list)
    qr_answers: list[str] = field(default_factory=list)
    ar_answers: list[str] = field(default_factory=list)
    concept_mapping: dict = field(default_factory=dict)
    uploaded_at: datetime = field(default_factory=datetime.now)

    @property
    def is_configured(self) -> bool:
        return bool(self.reading_answers or self.qr_answers or self.ar_answers)
    
    @property
    def has_concept_mapping(self) -> bool:
        return bool(self.concept_mapping)


class SessionConfigStore:
    """Thread-safe storage for session configurations."""

    def __init__(self):
        self._configs: dict[str, MarkingConfiguration] = {}
        self._lock = threading.Lock()

    def get(self, session_token: str) -> Optional[MarkingConfiguration]:
        with self._lock:
            return self._configs.get(session_token)

    def set(self, session_token: str, config: MarkingConfiguration) -> None:
        with self._lock:
            self._configs[session_token] = config

    def delete(self, session_token: str) -> None:
        with self._lock:
            self._configs.pop(session_token, None)

    def cleanup_expired(self, max_age_hours: int = 24) -> None:
        """Remove configurations older than max_age_hours."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        with self._lock:
            expired = [key for key, value in self._configs.items() if value.uploaded_at < cutoff]
            for key in expired:
                del self._configs[key]


# Global instance
config_store = SessionConfigStore()

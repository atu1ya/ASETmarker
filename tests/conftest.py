"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient

from web.app import app
from web.auth import create_session, STAFF_PASSWORD_HASH  # noqa: F401 - imported for completeness
from web.session_store import MarkingConfiguration, config_store


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    """Create authenticated test client."""
    client.post("/login", data={"password": "everest2024"})
    return client


@pytest.fixture
def configured_client(authenticated_client: TestClient) -> TestClient:
    """Create authenticated and configured test client."""
    session_token = authenticated_client.cookies.get("session_token")

    config = MarkingConfiguration(
        reading_answers=["A", "B", "C", "D"] * 8,
        qrar_answers=["A", "B", "C", "D", "E"] * 9,
        concept_mapping={
            "Reading": {"Area1": ["q1", "q2"], "Area2": ["q3", "q4"]},
            "Quantitative Reasoning": {"Area1": ["qr1", "qr2"]},
            "Abstract Reasoning": {"Area1": ["ar1", "ar2"]},
        },
    )
    config_store.set(session_token, config)

    return authenticated_client


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Create minimal valid PNG bytes for testing."""
    return bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,
            0x54,
            0x08,
            0xD7,
            0x63,
            0xF8,
            0xFF,
            0xFF,
            0x3F,
            0x00,
            0x05,
            0xFE,
            0x02,
            0xFE,
            0xDC,
            0xCC,
            0x59,
            0xE7,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )

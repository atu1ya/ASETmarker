"""Authentication tests."""
import pytest

from web.auth import create_session, invalidate_session, validate_session, verify_password


def test_verify_password_correct():
    """Test correct password verification."""
    assert verify_password("everest2024") is True


def test_verify_password_incorrect():
    """Test incorrect password rejection."""
    assert verify_password("wrongpassword") is False
    assert verify_password("") is False


def test_session_lifecycle():
    """Test session creation, validation, and invalidation."""
    token = create_session()

    assert token is not None
    assert len(token) > 20
    assert validate_session(token) is True

    invalidate_session(token)
    assert validate_session(token) is False


def test_invalid_session():
    """Test invalid session token."""
    assert validate_session("invalid-token") is False
    assert validate_session("") is False


def test_login_page_renders(client):
    """Test login page renders correctly."""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.content or b"login" in response.content


def test_login_success(client):
    """Test successful login."""
    response = client.post(
        "/login",
        data={"password": "everest2024"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "session_token" in response.cookies

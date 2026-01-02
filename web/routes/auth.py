"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from web.app import templates
from web.auth import (
    SESSION_COOKIE_NAME,
    cleanup_expired_sessions,
    create_session,
    invalidate_session,
    verify_password,
)
from web.config import Settings
from web.dependencies import get_optional_session, get_settings

router = APIRouter()


def _pop_flash_messages(request: Request) -> list[dict[str, str]]:
    messages = request.session.get("flash_messages", [])
    request.session["flash_messages"] = []
    return messages


def _add_flash_message(request: Request, message: str, category: str = "info") -> None:
    messages = request.session.get("flash_messages", [])
    messages.append({"message": message, "category": category})
    request.session["flash_messages"] = messages


@router.get("/login")
async def login_page(
    request: Request,
    session_token: str | None = Depends(get_optional_session),
    settings: Settings = Depends(get_settings),
):
    """Render the login page or redirect authenticated users."""
    cleanup_expired_sessions()
    if session_token:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        return response

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "page_title": "Login",
            "messages": _pop_flash_messages(request),
            "debug": settings.DEBUG,
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    password: str = Form(...),
    settings: Settings = Depends(get_settings),
):
    """Validate login credentials and create a session."""
    cleanup_expired_sessions()

    if not verify_password(password):
        _add_flash_message(request, "Invalid password. Please try again.", "error")
        response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        return response

    token = create_session()
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    max_age = settings.SESSION_DURATION_HOURS * 3600
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    _add_flash_message(request, "Successfully logged in.", "success")
    return response


@router.get("/logout")
async def logout(request: Request):
    """Invalidate the current session and redirect to login."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        invalidate_session(token)
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME)
    _add_flash_message(request, "You have been logged out.", "info")
    return response

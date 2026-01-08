"""FastAPI application entry point for the ASET Marking System."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from web.config import get_settings


logger = logging.getLogger("asetmarker.web")
logging.basicConfig(level=logging.INFO)

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="ASET Marking System", debug=settings.DEBUG)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="aset_session",
    https_only=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    """Log when the application starts."""
    logger.info("ASET Marking System starting up")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Custom HTTP exception responses."""
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # Check if request accepts HTML (browser request)
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Redirect to login page for browser requests
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        # Return JSON for API requests
        detail = exc.detail or "Authentication required."
        return JSONResponse({"detail": detail}, status_code=exc.status_code)
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        detail = exc.detail or "The requested resource was not found."
    else:
        detail = exc.detail or "An error occurred while processing the request."
    return JSONResponse({"detail": detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled errors."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        {"detail": "Internal server error. Please try again later."},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# Import routes after app, middleware, and templates are configured to avoid circular imports.
from web.routes import auth as auth_routes  # noqa: E402  pylint: disable=wrong-import-position
from web.routes import batch as batch_routes  # noqa: E402  pylint: disable=wrong-import-position
from web.routes import dashboard as dashboard_routes  # noqa: E402  pylint: disable=wrong-import-position
from web.routes import marking as marking_routes  # noqa: E402  pylint: disable=wrong-import-position

app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(marking_routes.router, prefix="/mark")
app.include_router(batch_routes.router, prefix="/batch")
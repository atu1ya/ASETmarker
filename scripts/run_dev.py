"""Run the FastAPI development server."""
from __future__ import annotations

import uvicorn

from web.config import get_settings


def main() -> None:
    """Launch uvicorn with settings-aware defaults."""
    settings = get_settings()
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )


if __name__ == "__main__":
    main()

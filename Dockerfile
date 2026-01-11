# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Environment
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps (OpenCV runtime)
# Note: On Debian slim, use libgl1 (not libgl1-mesa-glx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better caching)
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy app code
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# F1 plan: keep workers low to avoid memory pressure
# You can override WEB_CONCURRENCY in App Service settings if you upgrade plans later.
CMD ["sh","-c","gunicorn web.app:app \
  --workers ${WEB_CONCURRENCY:-1} \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout ${GUNICORN_TIMEOUT:-120} \
  --access-logfile - \
  --error-logfile -"]

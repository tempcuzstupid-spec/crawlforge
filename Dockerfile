# CrawlForge Dockerfile — compatible with Render + HuggingFace Spaces
# Defaults to port 7860 (HF Spaces standard), override with PORT env var

# syntax=docker/dockerfile:1.6
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_HEADLESS=true \
    PORT=7860

WORKDIR /app

# System deps for asyncpg + chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App
COPY app ./app

# Non-root user for safety
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

# Health check on PORT (HF/Render both check this)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",7860)}/health').read()" || exit 1

# Listen on $PORT (HF Spaces uses 7860, Render uses 10000, set via env)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --loop asyncio"]
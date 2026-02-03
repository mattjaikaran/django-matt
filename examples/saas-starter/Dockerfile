# =============================================================================
# SaaS Starter - Production Dockerfile with uv
# =============================================================================
#
# Multi-stage build for optimal image size and security.
#
# Build: docker build -t saas-starter .
# Run:   docker run -p 8000:8000 saas-starter
#
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (without dev dependencies)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# -----------------------------------------------------------------------------
# Stage 2: Runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=saas_project.settings \
    # Default to production settings
    DEBUG=false \
    # Path to virtual environment
    PATH="/app/.venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Collect static files (run as root temporarily)
RUN python manage.py collectstatic --no-input --clear 2>/dev/null || true

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Default command - Gunicorn with Uvicorn workers for ASGI support
CMD ["gunicorn", "saas_project.asgi:application", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--workers", "4", \
     "--threads", "2", \
     "--worker-tmp-dir", "/dev/shm", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--capture-output"]

# -----------------------------------------------------------------------------
# Stage 3: Development image (optional)
# -----------------------------------------------------------------------------
FROM runtime AS development

# Switch back to root to install dev dependencies
USER root

# Install uv for development
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dev dependencies
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Switch back to non-root user
USER appuser

# Development command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# -----------------------------------------------------------------------------
# Stage 4: Celery worker image
# -----------------------------------------------------------------------------
FROM runtime AS celery-worker

# Celery worker command
CMD ["celery", "-A", "saas_project", "worker", "-l", "INFO", "--concurrency", "4"]

# -----------------------------------------------------------------------------
# Stage 5: Celery beat image
# -----------------------------------------------------------------------------
FROM runtime AS celery-beat

# Celery beat command
CMD ["celery", "-A", "saas_project", "beat", "-l", "INFO", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"]

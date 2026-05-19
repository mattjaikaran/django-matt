# ── Stage 1: build the React frontend ──────────────────────────────────────
FROM oven/bun:1-alpine AS frontend-builder

WORKDIR /frontend
COPY examples/portfolio-frontend/package.json examples/portfolio-frontend/bun.lock* ./
RUN bun install --frozen-lockfile

COPY examples/portfolio-frontend/ .
# Embed the relative API base at build time so assets reference /api
ENV VITE_API_URL=/api
RUN bun run build
# output is /frontend/dist

# ── Stage 2: Django backend + WhiteNoise ────────────────────────────────────
FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Install django-matt from monorepo source
COPY pyproject.toml README.md ./
COPY django_matt/ ./django_matt/
RUN uv pip install --system -e .

# Install portfolio-api runtime deps
RUN uv pip install --system \
    "django>=5.2" \
    "whitenoise[brotli]>=6.0" \
    "psycopg[binary]>=3.1" \
    "python-dotenv>=1.0" \
    "gunicorn>=22.0" \
    "uvicorn[standard]>=0.30" \
    "resend>=2.0.0"

# Copy backend source
COPY examples/portfolio-api/ ./examples/portfolio-api/
WORKDIR /app/examples/portfolio-api

# Copy built frontend into the directory Django/WhiteNoise will serve from
COPY --from=frontend-builder /frontend/dist ./frontend_dist/

# Collect Django admin static files (CSS/JS for /admin/)
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# migrate → seed (idempotent) → serve
CMD ["sh", "-c", "\
    python manage.py migrate --noinput && \
    python scripts/seed.py && \
    exec gunicorn config.asgi:application \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --workers 2 \
        --timeout 60 \
    "]

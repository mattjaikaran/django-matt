FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

# Copy monorepo root so local django-matt path dep resolves
COPY pyproject.toml uv.lock README.md ./
COPY django_matt/ ./django_matt/
COPY examples/ecommerce-v2/ ./examples/ecommerce-v2/

WORKDIR /app/examples/ecommerce-v2

RUN uv sync --frozen --no-dev

RUN uv run python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["sh", "-c", "uv run python manage.py migrate --noinput && uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload --reload-dir /app/django_matt --reload-dir /app/examples/ecommerce-v2"]

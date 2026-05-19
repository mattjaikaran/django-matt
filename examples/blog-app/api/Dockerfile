FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

# Copy the full monorepo so the local django-matt path dep resolves
COPY pyproject.toml uv.lock README.md ./
COPY django_matt/ ./django_matt/
COPY examples/blog-app/api/ ./examples/blog-app/api/

WORKDIR /app/examples/blog-app/api

RUN uv sync --frozen --no-dev

RUN uv run python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "uv run python manage.py migrate --noinput && uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000"]

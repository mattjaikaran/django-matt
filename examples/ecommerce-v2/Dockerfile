FROM python:3.12-slim AS builder

RUN pip install uv

WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

FROM python:3.12-slim

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

WORKDIR /app

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "4"]

FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

# Install django-matt from monorepo source first
COPY pyproject.toml README.md ./
COPY django_matt/ ./django_matt/
RUN uv pip install --system -e .

# Install ecommerce-v2 deps (django-matt already installed above)
COPY examples/ecommerce-v2/ ./examples/ecommerce-v2/
WORKDIR /app/examples/ecommerce-v2
RUN uv pip install --system \
    "django>=5.2" \
    "django-cors-headers>=4.3.0" \
    "psycopg[binary]>=3.1.0" \
    "python-dotenv>=1.0.0" \
    "gunicorn>=22.0.0" \
    "uvicorn[standard]>=0.30.0" \
    "stripe>=8.0.0" \
    "celery>=5.3.0" \
    "redis>=5.0.0"

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload --reload-dir /app/django_matt --reload-dir /app/examples/ecommerce-v2"]

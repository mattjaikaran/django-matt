# Ecommerce V2

Multi-vendor marketplace built with django-matt. Supports multiple stores, product catalogs, shopping cart, orders, Stripe payments, reviews, and search.

## Stack
- Python 3.12+ / Django 5.2+ / django-matt / PostgreSQL / Redis
- Async-first, Pydantic schemas, JWT auth
- Stripe for payments, Celery for background tasks

## Run
```bash
make docker-up    # Start Postgres + Redis
make migrate      # Run migrations
make seed         # Seed sample data
make run          # Start dev server -> http://localhost:8000/api/docs
make celery       # Start Celery worker (separate terminal)
```

## Test
```bash
make test         # pytest with coverage
make lint         # ruff check
```

## Structure
- `apps/users/` — Custom user model, auth endpoints (register, login, me)
- `apps/stores/` — Vendor store profiles and management
- `apps/catalog/` — Products, categories, variants, inventory
- `apps/cart/` — Shopping cart with line items
- `apps/orders/` — Order placement, status tracking, fulfillment
- `apps/payments/` — Stripe checkout, webhooks, refunds
- `apps/reviews/` — Product reviews and ratings
- `apps/search/` — Product search and filtering
- `config/` — Django settings, URLs, ASGI, Celery

## Key Endpoints
- POST /api/auth/register, /api/auth/login, GET /api/auth/me
- CRUD /api/stores/
- CRUD /api/products/, GET /api/products/{id}
- POST /api/cart/items, GET /api/cart, DELETE /api/cart/items/{id}
- POST /api/orders/, GET /api/orders/, GET /api/orders/{id}
- POST /api/payments/checkout, POST /api/payments/webhook
- CRUD /api/reviews/
- GET /api/search/?q=keyword&category=electronics&min_price=10&max_price=100

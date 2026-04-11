# Ecommerce V2

Multi-vendor marketplace built with django-matt. Supports multiple stores, product catalogs, shopping cart, orders, Stripe payments, reviews, and search.

## Tech Stack

- **Python**: 3.12+ with [uv](https://docs.astral.sh/uv/) package manager
- **Django**: 5.2+
- **API Framework**: django-matt (async-first, Pydantic schemas, JWT auth)
- **Database**: PostgreSQL 16
- **Cache/Broker**: Redis 7
- **Payments**: Stripe
- **Background Tasks**: Celery

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose (for PostgreSQL + Redis)

## Quick Start

```bash
make install      # Install dependencies
make docker-up    # Start Postgres + Redis
make migrate      # Run migrations
make seed         # Seed sample data
make run          # Start dev server -> http://localhost:8000/api/docs
make celery       # Start Celery worker (separate terminal)
```

## Testing

```bash
make test         # pytest with coverage
make lint         # ruff check
make format       # ruff format
```

## Project Structure

```
apps/
├── users/        # Custom user model, auth endpoints (register, login, me)
├── stores/       # Vendor store profiles and management
├── catalog/      # Products, categories, variants, inventory
├── cart/         # Shopping cart with line items
├── orders/       # Order placement, status tracking, fulfillment
├── payments/     # Stripe checkout, webhooks, refunds
├── reviews/      # Product reviews and ratings
└── search/       # Product search and filtering
config/           # Django settings, URLs, ASGI, Celery
```

## API Endpoints

| Category | Endpoints |
|----------|-----------|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Stores | `CRUD /api/stores/` |
| Products | `CRUD /api/products/`, `GET /api/products/{id}` |
| Cart | `POST /api/cart/items`, `GET /api/cart`, `DELETE /api/cart/items/{id}` |
| Orders | `POST /api/orders/`, `GET /api/orders/`, `GET /api/orders/{id}` |
| Payments | `POST /api/payments/checkout`, `POST /api/payments/webhook` |
| Reviews | `CRUD /api/reviews/` |
| Search | `GET /api/search/?q=keyword&category=electronics&min_price=10&max_price=100` |

## Features Demonstrated

- JWT authentication with custom user model
- Multi-vendor architecture with store-level isolation
- Product catalog with categories, variants, and inventory tracking
- Shopping cart and order lifecycle management
- Stripe payment integration with webhook handling
- Product search with filtering (price range, category, keyword)
- Product reviews and ratings
- Background task processing with Celery

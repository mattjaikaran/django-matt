# Ecommerce V2

Full-stack multi-vendor marketplace built with django-matt + React/TypeScript.

## Stack
- **Backend**: Python 3.12+ / Django 5.2+ / django-matt / PostgreSQL / Redis
- **Frontend**: React 19 / TypeScript / TanStack Router + Query / Tailwind CSS / shadcn/ui
- Async-first, Pydantic schemas, JWT auth
- Stripe for payments, Celery for background tasks

## Run (Docker — everything together)
```bash
docker-compose up --build    # API on :8000, Frontend on :3001
```

## Run (Local dev)
```bash
# Backend
make migrate      # Run migrations
make seed         # Seed sample data
make run          # Django API -> http://localhost:8000/api/docs

# Frontend (separate terminal)
cd frontend
bun install
bun run dev       # React app -> http://localhost:3001
```

## Frontend Routes
- `/` — Home: hero, featured categories + products
- `/products` — Product listing with search/filter/pagination
- `/products/:productId` — Product detail, variants, reviews, add-to-cart
- `/cart` — Cart with quantity controls
- `/checkout` — Address + Stripe payment
- `/orders` — Order history with status filter
- `/orders/:orderId` — Order detail + cancel
- `/search` — Full-text search with price filters
- `/auth/login` + `/auth/register` — Auth
- `/profile` — Edit profile
- `/dashboard` — Vendor overview
- `/dashboard/store` — Create/edit store
- `/dashboard/products` — Product CRUD
- `/dashboard/orders` — Vendor order management

## Backend Structure
- `apps/users/` — Custom user model, auth endpoints (register, login, me)
- `apps/stores/` — Vendor store profiles and management
- `apps/catalog/` — Products, categories, variants, inventory
- `apps/cart/` — Shopping cart with line items
- `apps/orders/` — Order placement, status tracking, fulfillment
- `apps/payments/` — Stripe checkout, webhooks, refunds
- `apps/reviews/` — Product reviews and ratings
- `apps/search/` — Product search and filtering
- `config/` — Django settings, URLs, ASGI, Celery

## Key API Endpoints
- POST /api/auth/register, /api/auth/login, GET /api/auth/me
- CRUD /api/stores/
- CRUD /api/products/, GET /api/products/{id}
- POST /api/cart/items, GET /api/cart, DELETE /api/cart/items/{id}
- POST /api/orders/, GET /api/orders/, GET /api/orders/{id}
- POST /api/payments/create-intent, POST /api/payments/webhook
- CRUD /api/reviews/
- GET /api/search/?q=keyword&category=id&min_price=10&max_price=100

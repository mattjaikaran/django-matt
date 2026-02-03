# E-Commerce API

A production-quality e-commerce backend API built with **django-matt**, demonstrating advanced features including CRUD operations, full-text search, payments, caching, and background tasks.

## Features

- **Product Catalog**: Categories (hierarchical), products with variants, images, and inventory
- **Full-Text Search**: PostgreSQL-powered product search with ranking
- **Shopping Cart**: Session and user-based carts with coupon support
- **Checkout & Orders**: Complete checkout flow with address management
- **Payments**: Stripe integration with webhooks
- **Reviews & Ratings**: Product reviews with moderation
- **Wishlists**: User wishlists with sharing
- **Background Tasks**: Celery for async processing
- **Caching**: Redis caching for performance
- **Admin Dashboard**: Django Unfold admin integration

## Tech Stack

- **Framework**: Django 5.2+ with django-matt
- **Package Manager**: [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- **Database**: PostgreSQL 16 with full-text search
- **Cache**: Redis
- **Task Queue**: Celery with Redis broker
- **Payments**: Stripe
- **Admin**: Django Unfold
- **API Docs**: OpenAPI/Swagger

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker and Docker Compose (for containerized setup)
- PostgreSQL 16+ and Redis (for local development without Docker)

### Installing uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Quick Start

### Using Docker (Recommended)

```bash
# Clone and navigate to the example
cd examples/ecommerce-api

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web uv run python manage.py migrate

# Seed sample data
docker-compose exec web uv run python manage.py seed_data

# Create admin user
docker-compose exec web uv run python manage.py createsuperuser
```

Visit:
- API: http://localhost:8000/api/docs
- Admin: http://localhost:8000/admin

### Local Development

```bash
# Install dependencies with uv
uv sync

# Start PostgreSQL and Redis (or use Docker)
docker-compose up -d db redis

# Run migrations
uv run python manage.py migrate

# Seed data
uv run python manage.py seed_data

# Start server
uv run python manage.py runserver
```

Or use Make commands:

```bash
# Install dependencies
make install

# Run migrations
make migrate

# Seed data
make seed

# Start development server
make dev
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/refresh` | Refresh token |
| GET | `/api/auth/me` | Get current user |
| PUT | `/api/auth/me` | Update profile |

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products` | List products (with search, filter) |
| GET | `/api/products/{slug}` | Get product details |
| GET | `/api/products/featured` | Get featured products |
| GET | `/api/products/on-sale` | Get sale products |

**Query Parameters:**
- `q` - Search query (full-text)
- `category_id` / `category_slug` - Filter by category
- `min_price` / `max_price` - Price range
- `in_stock` - Filter by availability
- `is_featured` / `is_on_sale` - Filter flags
- `sort_by` - Sort field (name, price, created_at)
- `sort_order` - asc/desc

### Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/categories` | List categories |
| GET | `/api/categories/tree` | Get category tree |
| GET | `/api/categories/{slug}` | Get category |

### Cart

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cart` | Get current cart |
| POST | `/api/cart/items` | Add item to cart |
| PUT | `/api/cart/items/{id}` | Update item quantity |
| DELETE | `/api/cart/items/{id}` | Remove item |
| POST | `/api/cart/coupon` | Apply coupon |
| DELETE | `/api/cart/coupon` | Remove coupon |

### Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/orders/checkout` | Create order from cart |
| GET | `/api/orders` | List user orders |
| GET | `/api/orders/{id}` | Get order details |
| POST | `/api/orders/{id}/cancel` | Cancel order |

### Payments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/payments/create-intent` | Create payment intent |
| POST | `/api/payments/checkout-session` | Create Stripe checkout |
| GET | `/api/payments` | List payments |
| POST | `/api/payments/refund` | Request refund |

### Reviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reviews/product/{id}` | Get product reviews |
| POST | `/api/reviews` | Create review |
| PUT | `/api/reviews/{id}` | Update review |
| POST | `/api/reviews/{id}/vote` | Vote helpful/not |

### Wishlists

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/wishlists` | List wishlists |
| POST | `/api/wishlists` | Create wishlist |
| POST | `/api/wishlists/{id}/items` | Add item |
| DELETE | `/api/wishlists/{id}/items/{item_id}` | Remove item |

### Addresses

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/addresses` | List addresses |
| POST | `/api/addresses` | Create address |
| PUT | `/api/addresses/{id}` | Update address |
| DELETE | `/api/addresses/{id}` | Delete address |

## Project Structure

```
ecommerce-api/
├── config/                 # Django configuration
│   ├── settings.py         # Settings
│   ├── urls.py             # URL routing
│   ├── celery.py           # Celery config
│   └── asgi.py             # ASGI application
├── ecommerce/              # Application code
│   ├── api.py              # API configuration
│   ├── catalog/            # Products, categories, inventory
│   ├── cart/               # Shopping cart
│   ├── orders/             # Orders, coupons
│   ├── payments/           # Stripe integration
│   ├── reviews/            # Product reviews
│   └── users/              # Users, addresses, wishlists
├── templates/              # Email templates
├── docker-compose.yml      # Docker services
├── Dockerfile              # Container definition
├── Makefile                # Development commands
└── pyproject.toml          # Dependencies
```

## Configuration

### Environment Variables

```bash
# Django
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:pass@localhost:5432/ecommerce

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# JWT
JWT_SECRET_KEY=your-jwt-secret

# URLs
SITE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# Tax & Shipping
TAX_RATE_DEFAULT=0.0875
SHIPPING_FLAT_RATE=5.99
FREE_SHIPPING_THRESHOLD=50.00
```

### Stripe Setup

1. Create a Stripe account at https://stripe.com
2. Get your test API keys from the Dashboard
3. Set environment variables
4. For webhooks in development, use Stripe CLI:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe/
```

## Development

### Running Tests

```bash
# Run all tests
make test

# With coverage
make test-cov
```

### Code Quality

```bash
# Lint code
make lint

# Format code
make format
```

### Background Tasks

```bash
# Start Celery worker
make celery

# Start Celery beat (scheduled tasks)
make beat
```

### Database

```bash
# Run migrations
make migrate

# Create migrations
make makemigrations

# Seed sample data
make seed

# Clear and reseed
make seed-clear
```

## Deployment

### Production Checklist

1. Set `DEBUG=False`
2. Use strong `SECRET_KEY`
3. Configure proper `ALLOWED_HOSTS`
4. Use production database
5. Configure email backend
6. Set up Stripe live keys
7. Configure media storage (S3)
8. Enable HTTPS
9. Set up monitoring

### Docker Production

```bash
# Build production image (uses multi-stage build)
docker build --target production -t ecommerce-api .

# Run with production settings
docker run -e DEBUG=False -e SECRET_KEY=xxx ecommerce-api
```

## Sample Data

The seed command creates:
- 5 parent categories with 5 children each (25 total)
- 50 products with variants and inventory
- 5 discount coupons
- 3 sample users (customer@example.com, etc.)

Sample user credentials:
- Email: `customer@example.com`
- Password: `testpass123`

## License

MIT License

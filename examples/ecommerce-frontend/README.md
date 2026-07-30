# Ecommerce Frontend for django-matt

Minimal ecommerce frontend for django-matt's [ecommerce-api](../ecommerce-api/) backend. Batteries included: TanStack Router, React Query, Axios with JWT interceptor, Zustand auth + cart stores, Tailwind CSS.

## Stack

| Tool | Purpose |
|------|---------|
| [TanStack Router](https://tanstack.com/router) | Type-safe file-based routing |
| [React Query](https://tanstack.com/query) | Server state + caching |
| [Axios](https://axios-http.com) | HTTP client with JWT interceptor |
| [Zustand](https://zustand.dem0.dev) | Client state (auth, cart with localStorage persistence) |
| [Tailwind CSS](https://tailwindcss.com) | Utility-first styling |
| [Lucide](https://lucide.dev) | Icons |

## Quick Start

```bash
# Install dependencies
bun install

# Start dev server (proxies /api to localhost:8000)
bun run dev
```

Make sure your django-matt ecommerce API is running on port 8000:

```bash
cd ../ecommerce-api/
python manage.py runserver
```

## Project Structure

```
src/
├── routes/              # File-based routes (TanStack Router)
│   ├── __root.tsx       # Root layout with header, nav, footer
│   ├── index.tsx        # Landing page with hero + featured products
│   ├── login.tsx        # Login/Register page
│   ├── cart.tsx         # Shopping cart with quantity controls
│   ├── orders.tsx       # Order history table
│   └── products/
│       ├── index.tsx    # Product listing with search + category filters
│       └── $id.tsx      # Product detail with add-to-cart
├── hooks/
│   ├── useAuth.ts       # Auth store (Zustand + persist)
│   ├── useProducts.ts   # React Query hooks for products
│   └── useCart.ts       # Cart store (Zustand + localStorage)
├── lib/
│   ├── api.ts           # Axios instance with JWT interceptor
│   └── queryClient.ts   # React Query client config
├── types/
│   └── index.ts         # Product, CartItem, Order types
├── main.tsx             # App entry point
└── globals.css          # Tailwind imports
```

## Routes

| Route | Description |
|-------|-------------|
| `/` | Landing page with hero and featured products grid |
| `/products` | Product catalog with search bar and category filter chips |
| `/products/:id` | Product detail with image, description, price, and add-to-cart |
| `/cart` | Shopping cart with quantity +/- controls, total price, checkout button |
| `/orders` | Order history table with ID, date, status badges, total |
| `/login` | Login/Register form with JWT auth |

## Connecting to the API

1. Edit `vite.config.ts` — change the proxy target if your API runs on a different port
2. Edit `src/lib/api.ts` — update the base URL or add custom interceptors
3. Run `sync_types` from your django-matt ecommerce-api to generate TypeScript types:

```bash
cd ../ecommerce-api/
python manage.py sync_types --target typescript --apps products orders --output ../ecommerce-frontend/src/types/generated.ts
```

## Auth Flow

- JWT tokens stored in `localStorage` via Zustand persist middleware
- Axios interceptor attaches `Authorization: Bearer <token>` to every request
- On 401, token is cleared and user redirected to `/login`
- Auth endpoints: `POST /api/auth/login`, `POST /api/auth/register`

## Cart Persistence

Cart state persists to `localStorage` (key: `cart-storage`) and survives page refreshes and tab closes. The Zustand store provides:

- `addItem(item)` — add or increment quantity
- `removeItem(id)` — remove from cart
- `updateQuantity(id, qty)` — set exact quantity (0 removes)
- `clearCart()` — empty the cart
- `total` — computed getter for cart total

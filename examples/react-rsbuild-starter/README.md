# React + RSBuild Starter for django-matt

Minimal React frontend starter for django-matt APIs. Batteries included: TanStack Router, React Query, Axios with JWT interceptor, Zustand auth store, Tailwind CSS — all bundled with RSBuild (Rust-powered).

## Stack

| Tool | Purpose |
|------|---------|
| [RSBuild](https://rsbuild.rs) | Rust-powered build tool (Rspack bundler) |
| [TanStack Router](https://tanstack.com/router) | Type-safe file-based routing |
| [React Query](https://tanstack.com/query) | Server state + caching |
| [Axios](https://axios-http.com) | HTTP client with JWT interceptor |
| [Zustand](https://zustand.dem0.dev) | Client state (auth) |
| [Tailwind CSS](https://tailwindcss.com) | Utility-first styling |

## Quick Start

```bash
# Install dependencies
bun install

# Start dev server (proxies /api to localhost:8000)
bun run dev
```

Make sure your django-matt API is running on port 8000.

## Project Structure

```
src/
├── routes/           # File-based routes (TanStack Router)
│   ├── __root.tsx    # Root layout with nav
│   ├── index.tsx     # Home page
│   ├── login.tsx     # Login/Register page
│   └── items.tsx     # CRUD example page
├── hooks/
│   ├── useAuth.ts    # Auth store (Zustand + persist)
│   └── useItems.ts   # React Query hooks for items CRUD
├── lib/
│   ├── api.ts        # Axios instance with JWT interceptor
│   └── queryClient.ts # React Query client config
├── main.tsx          # App entry point
└── globals.css       # Tailwind imports
```

## Connecting to Your API

1. Copy `.env.example` to `.env` and set `PUBLIC_API_URL` to your API
2. Edit `src/lib/api.ts` to add custom interceptors if needed
3. Run `sync_types` from your django-matt project to generate TypeScript types:

```bash
cd your-api/
python manage.py sync_types --target typescript --apps your_app --output ../frontend/src/types/generated.ts
```

4. Replace `src/hooks/useItems.ts` with your own resource hooks

## Auth Flow

- JWT tokens stored in `localStorage` via Zustand persist middleware
- Axios interceptor attaches `Authorization: Bearer <token>` to every request
- On 401, token is cleared and user redirected to `/login`
- Auth endpoints: `POST /api/auth/login`, `POST /api/auth/register`

## RSBuild-Specific Notes

### Environment Variables

RSBuild automatically exposes all `PUBLIC_`-prefixed environment variables to client-side code. Access them via `process.env.PUBLIC_API_URL` (not `import.meta.env` like Vite).

### Dev Proxy

The dev server proxies `/api` requests to `http://localhost:8000`. Edit the `server.proxy` option in `rsbuild.config.ts` to change the target.

### CORS Setup

When running RSBuild's dev server separately from django-matt, add to `settings.py`:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # RSBuild dev server
]
```

Or for development only:

```python
CORS_ALLOW_ALL_ORIGINS = True
```

### Why RSBuild over Vite?

- **Dev/prod parity** — Same Rspack bundler in dev and prod (Vite uses ESM in dev, Rollup in prod)
- **SWC everywhere** — Single compiler for JSX, TypeScript, and minification
- **Webpack compatibility** — Use existing webpack plugins and loaders
- **Module Federation** — First-class support for micro-frontends

## Scripts

| Command | Description |
|---------|-------------|
| `bun run dev` | Start dev server on port 3000 |
| `bun run build` | Production build |
| `bun run preview` | Preview production build |
| `bun run typecheck` | TypeScript type checking |
| `bun run test` | Run tests |

## License

MIT

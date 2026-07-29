# React + RSBuild Starter for django-matt

Minimal React frontend starter for django-matt APIs using RSBuild (Rust-powered bundler). Same stack as the Vite starter but with faster builds.

## Stack

| Tool | Purpose |
|------|---------|
| [RSBuild](https://rsbuild.dev) | Rust-powered bundler (Rspack-based) |
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

1. Edit `rsbuild.config.ts` — change the proxy target if your API runs on a different port
2. Run `sync_types` from your django-matt project to generate TypeScript types:

```bash
cd your-api/
python manage.py sync_types --target typescript --apps your_app --output ../frontend/src/types/generated.ts
```

3. Replace `src/hooks/useItems.ts` with your own resource hooks

## Auth Flow

- JWT tokens stored in `localStorage` via Zustand persist middleware
- Axios interceptor attaches `Authorization: Bearer <token>` to every request
- On 401, token is cleared and user redirected to `/login`
- Auth endpoints: `POST /api/auth/login`, `POST /api/auth/register`

## Vite vs RSBuild

| | Vite | RSBuild |
|---|---|---|
| Bundler | Rollup (JS) | Rspack (Rust) |
| Cold start | ~1s | ~0.5s |
| HMR | Fast | Fast |
| Config | `vite.config.ts` | `rsbuild.config.ts` |
| Proxy | `server.proxy` | `server.proxy` |
| Plugins | `@vitejs/plugin-react` | `@rsbuild/plugin-react` |

Choose Vite for broader ecosystem compatibility. Choose RSBuild for faster cold builds in large projects.

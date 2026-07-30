# React + Vite Starter for django-matt

A production-ready React frontend starter for [django-matt](https://github.com/django-matt) APIs. Batteries included: TanStack Router, React Query, Zustand auth, Axios with JWT refresh, and Tailwind CSS.

## Stack

| Tool | Purpose |
|------|---------|
| [Vite](https://vitejs.dev) | Build tool with fast HMR |
| [React 19](https://react.dev) | UI library |
| [TanStack Router](https://tanstack.com/router) | Type-safe file-based routing with code splitting |
| [TanStack Query](https://tanstack.com/query) | Server state management and caching |
| [Axios](https://axios-http.com) | HTTP client with JWT interception and auto-refresh |
| [Zustand](https://zustand.dem0.dev) | Client state (auth store with persist) |
| [Tailwind CSS](https://tailwindcss.com) | Utility-first styling |
| [Sonner](https://sonner.emilkowal.ski) | Toast notifications |

## Quick Start

```bash
# Install dependencies
bun install

# Copy environment file
cp .env.example .env

# Start dev server (proxies /api to localhost:8000)
bun run dev
```

Make sure your django-matt API is running on port 8000.

## Project Structure

```
src/
├── stores/
│   └── auth.ts          # Zustand auth store (JWT + refresh token)
├── routes/
│   ├── __root.tsx        # Root layout with nav
│   ├── index.tsx         # Home page
│   ├── login.tsx         # Login / inline register
│   ├── register.tsx      # Full registration form
│   ├── dashboard.tsx     # Protected user dashboard
│   └── items.tsx         # CRUD example (protected)
├── hooks/
│   ├── useAuth.ts        # Re-exports auth store
│   └── useItems.ts       # React Query hooks for items CRUD
├── components/
│   └── ProtectedRoute.tsx # Auth guard wrapper
├── lib/
│   ├── api.ts            # Axios instance with JWT interceptor
│   └── queryClient.ts    # React Query client config
├── main.tsx              # App entry point
└── globals.css           # Tailwind imports
```

## Connecting to Your API

### 1. API Base URL

Edit `.env` (or set `VITE_API_BASE_URL` in your environment) to point at your django-matt API:

```bash
VITE_API_BASE_URL=http://localhost:8000/api
```

The Axios client in `src/lib/api.ts` reads from this variable, falling back to `/api` for production when served behind a reverse proxy.

### 2. Dev Proxy

`vite.config.ts` proxies `/api` to `http://localhost:8000` during development. If your API runs on a different port, update:

```ts
// vite.config.ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',  // change port here
  },
},
```

### 3. CORS Configuration

django-matt needs to allow requests from your frontend origin. Add to your django-matt settings:

```python
# settings.py — django-matt CORS setup

# 1. Install django-cors-headers
# pip install django-cors-headers

INSTALLED_APPS = [
    # ...
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    # ... other middleware
]

# 2. Allow your frontend origin
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',      # Vite dev server
    'http://localhost:5173',      # Alt Vite port
    'https://your-production-domain.com',
]

# 3. Allow credentials (needed for cookies if using session auth)
CORS_ALLOW_CREDENTIALS = True

# 4. Expose auth headers
CORS_EXPOSE_HEADERS = ['Authorization']
```

For production, use django-matt's built-in CORS support:

```python
# settings.py — django-matt native CORS
MATT = {
    'CORS_ORIGINS': ['http://localhost:3000', 'https://yourdomain.com'],
}
```

The default port is `3000`. If you change the Vite dev server port (in `vite.config.ts`), update the CORS origin accordingly.

### 4. Type Generation with sync_types

django-matt's `sync_types` command generates TypeScript types from your API schemas. This gives you end-to-end type safety from database to frontend.

```bash
# From your django-matt project root:
python manage.py sync_types \
  --target typescript \
  --apps your_app another_app \
  --output ../frontend/src/types/generated.ts
```

**Options:**

| Flag | Description |
|------|-------------|
| `--target` | Output language: `typescript` or `openapi` |
| `--apps` | Comma-separated list of django-matt apps to generate types for |
| `--output` | Path to write the generated file |
| `--watch` | Watch for changes and regenerate automatically |

**Integration pattern:**

```ts
// src/hooks/useItems.ts — with generated types
import type { Item, ItemCreate } from '@/types/generated';

export function useItems() {
  return useQuery({
    queryKey: ['items'],
    queryFn: async () => {
      const { data } = await api.get<Item[]>('/items/');
      return data;
    },
  });
}

export function useCreateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (item: ItemCreate) => {  // typed from generated types
      const { data } = await api.post<Item>('/items/', item);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['items'] }),
  });
}
```

Create a `src/types/` directory and add the generated file there. Import types directly — they stay in sync with your API schemas.

### 5. Replace Sample Resources

The starter ships with a sample `/items` CRUD to demonstrate the pattern. To connect your own resources:

1. Run `sync_types` to generate types for your app
2. Replace `src/hooks/useItems.ts` with hooks for your resources
3. Replace `src/routes/items.tsx` with pages for your resources
4. Update `src/routes/__root.tsx` nav links

## Auth Flow

### JWT Authentication

The starter uses JWT access + refresh tokens:

1. **Login/Register** — `POST /auth/login/` or `POST /auth/register/` returns `{ access, refresh, user }`
2. **Access token** — Stored in `localStorage` and Zustand persist; attached as `Authorization: Bearer <token>` to every request
3. **Auto-refresh** — On 401, the Axios interceptor calls `POST /auth/refresh/` with the refresh token to get a new access token, then retries the failed request
4. **Queueing** — Concurrent 401s are queued so only one refresh request fires
5. **Logout** — Clears both tokens from localStorage and Zustand state

### Expected API Endpoints

Your django-matt API should provide:

```
POST   /api/auth/login/     { email, password }          → { access, refresh, user }
POST   /api/auth/register/  { email, username, password } → { access, refresh, user }
POST   /api/auth/refresh/   { refresh }                   → { access }
GET    /api/items/           → Item[]
POST   /api/items/          { name, description }         → Item
DELETE /api/items/:id        → 204
```

### Protected Routes

Wrap any page component with `<ProtectedRoute>` to require authentication:

```tsx
import { ProtectedRoute } from '@/components/ProtectedRoute';

export const Route = createFileRoute('/dashboard')({
  component: () => (
    <ProtectedRoute>
      <DashboardPage />
    </ProtectedRoute>
  ),
});
```

Unauthenticated users are redirected to `/login`. The component handles Zustand hydration to avoid flash-of-redirect.

## Scripts

| Command | Description |
|---------|-------------|
| `bun run dev` | Start dev server on port 3000 |
| `bun run build` | Production build (`tsc -b && vite build`) |
| `bun run preview` | Preview production build |
| `bun run lint` | ESLint check |
| `bun run type-check` | TypeScript type checking |

## Production Deployment

```bash
# Build
bun run build

# Output is in dist/ — serve with any static file server
# Or use the built-in preview:
bun run preview
```

For production behind nginx:

```nginx
server {
    listen 80;
    server_name example.com;
    root /path/to/dist;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API to django-matt
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Customization

### Change the Dev Server Port

```ts
// vite.config.ts
server: { port: 5173 }
```

Then update the CORS origin in your django-matt settings to match.

### Add shadcn/ui Components

Copy components from [shadcn/ui](https://ui.shadcn.com) into `src/components/ui/`. The starter already includes `tailwindcss-animate` for animation support.

### Dark Mode

Add `next-themes` for dark mode, or use Tailwind's `dark:` variant with a manual toggle.

## License

MIT

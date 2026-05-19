# Frontend Integration

CORS setup, `sync_types` TypeScript codegen, React Query hooks, Zod schemas, and dev proxy.

---

## CORS

```python
# settings.py
INSTALLED_APPS = [
    ...
    "corsheaders",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",   # must be before CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    ...
]

# Development — allow Vite dev server
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Production — explicit origins only
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
]

CORS_ALLOW_CREDENTIALS = True   # required if you use cookies/auth headers
```

---

## Vite Dev Proxy

Proxy `/api/*` to Django so the frontend and backend share the same origin in development (avoids CORS entirely):

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

With this proxy in place you can set `CORS_ALLOWED_ORIGINS = []` in development and call `/api/users/` directly.

---

## TypeScript Codegen (`sync_types`)

Generate TypeScript interfaces from your Pydantic schemas:

```bash
# TypeScript interfaces
python manage.py sync_types \
  --target typescript \
  --modules myapp.schemas \
  --output frontend/src/types/api.ts \
  --camel-case

# Zod validation schemas
python manage.py sync_types \
  --target zod \
  --modules myapp.schemas \
  --output frontend/src/schemas/api.ts \
  --camel-case

# Typed API client
python manage.py sync_types \
  --target api-client \
  --from-openapi \
  --output frontend/src/lib/api.ts \
  --include-react-query

# Watch mode (auto-regenerate on schema file changes)
python manage.py sync_types \
  --target typescript \
  --output frontend/src/types/api.ts \
  --watch
```

### Key flags

| Flag | Description |
|------|-------------|
| `--target typescript` | TypeScript interfaces |
| `--target zod` | Zod validation schemas |
| `--target api-client` | Typed HTTP client |
| `--target swift` | Swift Codable structs (iOS) |
| `--modules` | Comma-separated module paths |
| `--apps` | Comma-separated Django app labels |
| `--output` | Output file path |
| `--camel-case` | Convert snake_case → camelCase |
| `--from-openapi` | Introspect project OpenAPI schema |
| `--include-react-query` | Generate React Query hooks |
| `--include-swr` | Generate SWR hooks |
| `--watch` | Re-run on file changes |

### Programmatic generation

```python
from django_matt.typegen import TypeScriptGenerator, ZodGenerator
from myapp.schemas import UserSchema, PostSchema

ts = TypeScriptGenerator(use_interface=True, camel_case=True)
print(ts.generate([UserSchema, PostSchema]))

zod = ZodGenerator(camel_case=True)
print(zod.generate([UserSchema, PostSchema]))
```

---

## Generated TypeScript Types

Given:

```python
# myapp/schemas.py
class UserSchema(BaseModel):
    id: int
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    roles: list[str] = []
```

`sync_types --target typescript --camel-case` produces:

```typescript
// frontend/src/types/api.ts
export interface UserSchema {
  id: number;
  email: string;
  displayName: string;
  isActive: boolean;
  createdAt: string;
  roles: string[];
}
```

`sync_types --target zod --camel-case` produces:

```typescript
// frontend/src/schemas/api.ts
import { z } from "zod";

export const userSchema = z.object({
  id: z.number(),
  email: z.string(),
  displayName: z.string(),
  isActive: z.boolean(),
  createdAt: z.string(),
  roles: z.array(z.string()).default([]),
});

export type UserSchema = z.infer<typeof userSchema>;
```

---

## Auth Flow (React)

### Axios interceptor (JWT + auto-refresh)

```typescript
// src/lib/api.ts
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// Attach token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem("refresh_token");
      if (!refresh) {
        window.location.href = "/login";
        return Promise.reject(error);
      }
      const { data } = await axios.post("/api/auth/refresh", { refresh_token: refresh });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      original.headers.Authorization = `Bearer ${data.access_token}`;
      return api(original);
    }
    return Promise.reject(error);
  }
);

export default api;
```

### Login

```typescript
async function login(email: string, password: string) {
  const { data } = await api.post("/auth/login", { email, password });
  localStorage.setItem("access_token", data.tokens.access_token);
  localStorage.setItem("refresh_token", data.tokens.refresh_token);
  return data.user;
}
```

### Logout

```typescript
async function logout() {
  await api.post("/auth/logout");
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}
```

---

## React Query Setup

```typescript
// src/main.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 1000 * 60 * 5 }, // 5 min
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
```

### Query hooks

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { UserSchema } from "@/types/api";

// List
export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<{ items: UserSchema[] }>("/users/").then((r) => r.data),
  });
}

// Single item
export function useUser(id: number) {
  return useQuery({
    queryKey: ["users", id],
    queryFn: () => api.get<UserSchema>(`/users/${id}/`).then((r) => r.data),
  });
}

// Mutation
export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<UserSchema>) =>
      api.post<UserSchema>("/users/", payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}
```

---

## Zod Validation (Forms)

```typescript
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type LoginForm = z.infer<typeof loginSchema>;

function LoginPage() {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    await login(data.email, data.password);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register("email")} />
      {errors.email && <span>{errors.email.message}</span>}
      <input type="password" {...register("password")} />
      <button type="submit">Login</button>
    </form>
  );
}
```

---

## Production: Separate Domains

When frontend (`app.example.com`) and backend (`api.example.com`) are on different domains:

```python
# settings.py
CORS_ALLOWED_ORIGINS = ["https://app.example.com"]
CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
```

```typescript
// src/lib/api.ts
const api = axios.create({
  baseURL: "https://api.example.com",
  withCredentials: true,
});
```

---

## Production: Monorepo (Nginx)

Serve both from the same domain using a reverse proxy:

```nginx
server {
    server_name app.example.com;

    location /api/ {
        proxy_pass http://django:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        root /srv/frontend/dist;
        try_files $uri /index.html;
    }
}
```

No CORS headers needed — same origin.

---

## npm Scripts

Add to `package.json` to keep types fresh:

```json
{
  "scripts": {
    "types": "cd .. && python manage.py sync_types --target typescript --from-openapi --output frontend/src/types/api.ts --camel-case",
    "types:zod": "cd .. && python manage.py sync_types --target zod --from-openapi --output frontend/src/schemas/api.ts --camel-case",
    "types:watch": "cd .. && python manage.py sync_types --target typescript --output frontend/src/types/api.ts --watch"
  }
}
```

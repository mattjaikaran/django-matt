# Blog Frontend

React+Vite frontend for the `blog-api` django-matt example.

## Stack
- TanStack Router (file-based routing)
- TanStack Query (data fetching)
- Zustand (auth state)
- Axios (HTTP client with JWT interceptor)
- shadcn/ui + Tailwind CSS
- TypeScript strict mode

## Setup

1. Start blog-api: `cd ../blog-api && make run`
2. `cp .env.example .env`
3. `bun install`
4. `bun dev`

## Features
- Post listing with tag/category/featured filters
- Post detail with comment thread
- Full-text search
- Tag and category browse pages
- Author dashboard: create/edit/delete posts
- JWT auth (login/register/refresh)
- Dark mode
- Generated TypeScript types via `sync_types`

## Generated Types

The `src/types/blog.ts` file was generated from the blog-api schema using:

```bash
cd ../blog-api && python manage.py sync_types --target typescript --output ../../blog-frontend/src/types/generated.ts
```

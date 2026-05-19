# React Server Components (RSC) - Optional Enhancement

This folder contains utilities for React Server Components patterns. Note that full RSC support requires a framework like Next.js App Router.

## What's Included

- **Type definitions** for server/client component patterns
- **Utility functions** for environment detection (`isServer`, `isClient`)
- **Cache function** for memoizing server-side data fetching
- **Preload patterns** for data prefetching

## When to Use

These utilities are useful when:

- Migrating to Next.js App Router
- Building isomorphic utilities that work on both server and client
- Preparing your codebase for RSC adoption

## Usage Example

```tsx
import { isServer, cache, serverOnly } from '@/optional/rsc';

// Environment detection
if (isServer) {
  // Server-only code
}

// Cached data fetching (for server components)
const getData = cache(async (id: string) => {
  const response = await fetch(`/api/items/${id}`);
  return response.json();
});

// Server-only function
const secretData = serverOnly(() => {
  return process.env.SECRET_KEY;
});
```

## Migration to Next.js

If you decide to migrate to Next.js for full RSC support:

1. Create a Next.js project with App Router
2. Copy your components to the `app/` directory
3. Mark client components with `'use client'` directive
4. Use these utilities for server components

## Security Note

When using RSC in production, ensure you're using patched versions:

- React >= 19.0.1
- react-server-dom-webpack >= 19.0.1
- Next.js >= 15.0.5

See CVE-2025-55182 for details.

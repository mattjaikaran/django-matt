# Server-Side Rendering (SSR) - Optional Enhancement

This folder contains optional SSR setup files. By default, the boilerplate runs as a standard Vite SPA (Single Page Application) which is faster to develop with and simpler to deploy.

## When to Use SSR

Consider SSR if you need:

- Better SEO for public-facing pages
- Faster initial page load for content-heavy pages
- Social media link previews (Open Graph)

## Setup Instructions

### 1. Install SSR Dependencies

```bash
# With bun
bun add express compression sirv
bun add -d @types/express @types/compression tsx
```

### 2. Copy Files to Root

```bash
# Copy server and config files
cp src/optional/ssr/server.ts ./
cp src/optional/ssr/vite.config.ssr.ts ./
cp src/optional/ssr/entry-server.tsx src/
cp src/optional/ssr/entry-client.tsx src/
```

### 3. Update index.html

Add the SSR outlet placeholder:

```html
<div id="root"><!--ssr-outlet--></div>
```

### 4. Add SSR Scripts to package.json

```json
{
  "scripts": {
    "dev:ssr": "tsx server.ts",
    "build:ssr": "bun run build:client && bun run build:server",
    "build:client": "vite build --outDir dist/client",
    "build:server": "vite build --outDir dist/server --ssr src/entry-server.tsx --config vite.config.ssr.ts",
    "preview:ssr": "NODE_ENV=production tsx server.ts"
  }
}
```

### 5. Run in SSR Mode

```bash
# Development
bun run dev:ssr

# Production
bun run build:ssr
bun run preview:ssr
```

## File Overview

- `server.ts` - Express server for SSR
- `entry-server.tsx` - Server-side render function
- `entry-client.tsx` - Client-side hydration
- `vite.config.ssr.ts` - Vite config for SSR build

## Notes

- SSR uses Express for the server
- In production, static files are served with compression
- The router creates a memory history for server rendering
- Client hydrates the server-rendered HTML

/**
 * SSR Server
 * Express server for Server-Side Rendering with Vite
 *
 * Usage:
 *   Development: npm run dev:ssr
 *   Production:  npm run build:ssr && npm run serve:ssr
 */

import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ViteDevServer } from 'vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isProduction = process.env.NODE_ENV === 'production';
const port = process.env.PORT || 3000;

async function createServer() {
  const app = express();

  let vite: ViteDevServer | undefined;

  if (!isProduction) {
    // Development mode - use Vite's dev server middleware
    const { createServer: createViteServer } = await import('vite');
    vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'custom',
    });
    app.use(vite.middlewares);
  } else {
    // Production mode - serve static files
    const compression = (await import('compression')).default;
    const sirv = (await import('sirv')).default;

    app.use(compression());
    app.use(
      sirv(path.resolve(__dirname, 'dist/client'), {
        gzip: true,
      })
    );
  }

  // Handle all routes with SSR
  app.use('*', async (req, res) => {
    try {
      const url = req.originalUrl;

      let template: string;
      let render: (options: { url: string }) => Promise<{
        html: string;
        statusCode: number;
      }>;

      if (!isProduction && vite) {
        // Development - read template and transform
        template = fs.readFileSync(
          path.resolve(__dirname, 'index.html'),
          'utf-8'
        );
        template = await vite.transformIndexHtml(url, template);

        // Load server entry through Vite for HMR
        const module = await vite.ssrLoadModule('/src/entry-server.tsx');
        render = module.render;
      } else {
        // Production - use built files
        template = fs.readFileSync(
          path.resolve(__dirname, 'dist/client/index.html'),
          'utf-8'
        );

        // @ts-ignore - Production build
        const module = await import('./dist/server/entry-server.js');
        render = module.render;
      }

      // Render the app
      const { html: appHtml, statusCode } = await render({ url });

      // Inject the rendered HTML into the template
      const html = template.replace('<!--ssr-outlet-->', appHtml);

      res.status(statusCode).set({ 'Content-Type': 'text/html' }).end(html);
    } catch (e) {
      // Handle errors
      if (!isProduction && vite) {
        vite.ssrFixStacktrace(e as Error);
      }
      console.error(e);
      res.status(500).end((e as Error).message);
    }
  });

  app.listen(port, () => {
    console.log(`🚀 SSR Server running at http://localhost:${port}`);
    console.log(`   Mode: ${isProduction ? 'production' : 'development'}`);
  });
}

createServer();

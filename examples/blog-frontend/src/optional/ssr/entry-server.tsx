/**
 * Server Entry Point for SSR
 * This file exports the render function used by the SSR server
 */

import { AppProviders } from '@/components/providers';
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from '@tanstack/react-router';
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import { routeTree } from './routeTree.gen';

// Note: Router type registration is handled in main.tsx

export interface RenderOptions {
  url: string;
}

export interface RenderResult {
  html: string;
  head?: string;
  statusCode: number;
}

/**
 * Render the app to HTML string for SSR
 */
export async function render(options: RenderOptions): Promise<RenderResult> {
  const { url } = options;

  // Create memory history for SSR
  const memoryHistory = createMemoryHistory({
    initialEntries: [url],
  });

  // Create router with memory history
  const router = createRouter({
    routeTree,
    history: memoryHistory,
  });

  // Wait for router to be ready
  await router.load();

  // Render the app
  const html = ReactDOMServer.renderToString(
    <React.StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </React.StrictMode>
  );

  // Determine status code based on route match
  const statusCode = router.state.matches.some(
    match => match.status === 'notFound'
  )
    ? 404
    : 200;

  return {
    html,
    statusCode,
  };
}

/**
 * Render to a readable stream for streaming SSR
 */
export async function renderToStream(options: RenderOptions) {
  const { url } = options;

  const memoryHistory = createMemoryHistory({
    initialEntries: [url],
  });

  const router = createRouter({
    routeTree,
    history: memoryHistory,
  });

  await router.load();

  const stream = ReactDOMServer.renderToPipeableStream(
    <React.StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </React.StrictMode>
  );

  return stream;
}

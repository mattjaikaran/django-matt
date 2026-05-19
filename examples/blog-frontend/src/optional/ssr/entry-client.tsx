/**
 * Client Entry Point for SSR
 * This file is the entry point for the client-side bundle in SSR mode
 */

import { AppProviders } from '@/components/providers';
import { initializeStore } from '@/lib/store';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import React from 'react';
import ReactDOM from 'react-dom/client';
import './globals.css';
import { routeTree } from './routeTree.gen';

// Create a new router instance
const router = createRouter({ routeTree });

// Register the router instance for type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

// Initialize the store
initializeStore();

// Hydrate the app if SSR, otherwise render
const rootElement = document.getElementById('root')!;

if (rootElement.innerHTML) {
  // SSR mode - hydrate existing markup
  ReactDOM.hydrateRoot(
    rootElement,
    <React.StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </React.StrictMode>
  );
} else {
  // CSR mode - render fresh
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </React.StrictMode>
  );
}

import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { Toaster } from 'sonner';
import './globals.css';
import { StripeProvider } from './components/checkout/StripeProvider';
import { queryClient } from './lib/queryClient';
import { routeTree } from './routeTree.gen';

const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <StripeProvider>
        <RouterProvider router={router} />
      </StripeProvider>
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  </React.StrictMode>
);

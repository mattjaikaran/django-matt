import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';

interface QueryProviderProps {
  children: React.ReactNode;
}

interface ApiErrorWithResponse {
  response?: {
    status?: number;
  };
}

function isApiError(error: unknown): error is ApiErrorWithResponse {
  return typeof error === 'object' && error !== null && 'response' in error;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // With SSR, we usually want to set some default staleTime
            // above 0 to avoid refetching immediately on the client
            staleTime: 60 * 1000, // 1 minute
            retry: (failureCount, error: unknown) => {
              // Don't retry on 4xx errors except 408, 429
              if (isApiError(error)) {
                const status = error.response?.status;
                if (status && status >= 400 && status < 500) {
                  if (status === 408 || status === 429) {
                    return failureCount < 2;
                  }
                  return false;
                }
              }
              // Retry up to 3 times for other errors
              return failureCount < 3;
            },
            retryDelay: attemptIndex =>
              Math.min(1000 * 2 ** attemptIndex, 30000),
          },
          mutations: {
            retry: (failureCount, error: unknown) => {
              // Don't retry mutations on client errors
              if (isApiError(error)) {
                const status = error.response?.status;
                if (status && status >= 400 && status < 500) {
                  return false;
                }
              }
              // Retry up to 2 times for server errors
              return failureCount < 2;
            },
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

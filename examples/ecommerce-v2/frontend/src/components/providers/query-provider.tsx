import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () => new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000,
          retry: (failureCount, error: unknown) => {
            if (typeof error === 'object' && error !== null && 'response' in error) {
              const status = (error as { response?: { status?: number } }).response?.status;
              if (status && status >= 400 && status < 500) return false;
            }
            return failureCount < 3;
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

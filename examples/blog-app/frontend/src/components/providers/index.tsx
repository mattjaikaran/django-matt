import { QueryProvider } from './query-provider';

interface AppProvidersProps {
  children: React.ReactNode;
}

/**
 * App Providers
 *
 * Minimal provider setup - only React Query is needed.
 * Theme and config are managed via Zustand store for better performance.
 *
 * @see src/lib/store for state management
 */
export function AppProviders({ children }: AppProvidersProps) {
  return <QueryProvider>{children}</QueryProvider>;
}

export { QueryProvider };

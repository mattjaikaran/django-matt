/**
 * React Server Components Configuration
 *
 * IMPORTANT: React Server Components (RSC) are primarily designed for
 * frameworks like Next.js App Router. This module provides utilities
 * and configuration for potential RSC integration.
 *
 * For Vite projects, full RSC support requires additional framework-level
 * implementation. This module provides:
 * - Type definitions for server/client component patterns
 * - Utilities for data fetching patterns similar to RSC
 * - Configuration for when migrating to an RSC-capable framework
 *
 * Security Note (CVE-2025-55182):
 * - Vulnerable packages: react-server-dom-webpack, react-server-dom-parcel,
 *   react-server-dom-turbopack versions 19.0.0, 19.1.0, 19.1.1, 19.2.0
 * - Safe versions: 19.0.1, 19.1.2, 19.2.1+
 * - Always verify your React version is patched
 */

/**
 * Server component marker type
 * Used to denote components that should only run on the server
 */
export type ServerComponent<P = {}> = (props: P) => Promise<React.JSX.Element>;

/**
 * Client component marker type
 * Used to denote components that require client-side interactivity
 */
export type ClientComponent<P = {}> = (props: P) => React.JSX.Element;

/**
 * Check if code is running on the server
 */
export const isServer = typeof window === 'undefined';

/**
 * Check if code is running on the client
 */
export const isClient = typeof window !== 'undefined';

/**
 * Server-only utility - throws if called on client
 */
export function serverOnly<T>(fn: () => T): T {
  if (isClient) {
    throw new Error(
      'This function can only be called on the server. ' +
        'Ensure this code is not included in the client bundle.'
    );
  }
  return fn();
}

/**
 * Client-only utility - throws if called on server
 */
export function clientOnly<T>(fn: () => T): T {
  if (isServer) {
    throw new Error(
      'This function can only be called on the client. ' +
        'Ensure this code is not called during SSR.'
    );
  }
  return fn();
}

/**
 * Cache function for server components
 * Memoizes async function calls during a request
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function cache<T extends (...args: any[]) => Promise<unknown>>(fn: T): T {
  const cacheMap = new Map<string, unknown>();

  return (async (...args: Parameters<T>) => {
    const key = JSON.stringify(args);

    if (cacheMap.has(key)) {
      return cacheMap.get(key);
    }

    const result = await fn(...args);
    cacheMap.set(key, result);
    return result;
  }) as T;
}

/**
 * Preload data for components
 * Can be used to start fetching data before it's needed
 */
export function preload<T>(fn: () => Promise<T>, key: string): void {
  // In a real RSC implementation, this would integrate with
  // the framework's preloading mechanism
  if (isServer) {
    // Server-side: start fetch immediately
    fn();
  } else {
    // Client-side: could use react-query prefetch
    console.debug(`Preloading: ${key}`);
  }
}

/**
 * RSC-style data fetching pattern
 * Use this pattern for components that fetch their own data
 */
export async function fetchData<T>(
  fetcher: () => Promise<T>,
  _options?: {
    revalidate?: number;
    tags?: string[];
  }
): Promise<T> {
  // In Vite, this is a simple wrapper
  // In Next.js RSC, this would use their caching infrastructure
  return fetcher();
}

/**
 * Configuration for RSC-ready migration
 */
export const rscConfig = {
  // Supported frameworks for RSC
  supportedFrameworks: ['next.js'] as const,

  // Current status
  isEnabled: false,

  // Version requirements for secure RSC
  secureVersions: {
    react: '>=19.0.1',
    'react-server-dom-webpack': '>=19.0.1',
    'react-server-dom-parcel': '>=19.0.1',
    'react-server-dom-turbopack': '>=19.0.1',
    next: '>=15.0.5',
  },

  // Vulnerability info
  cve: 'CVE-2025-55182',
  vulnerability: 'React2Shell',
};

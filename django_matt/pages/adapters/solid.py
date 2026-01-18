"""
SolidJS client adapter generator.

Generates the @django-matt/solid adapter code that handles:
- Page mounting and hydration
- SPA navigation with X-Page header
- Solid signals/stores for page state
- Form submission
"""


def generate_solid_adapter() -> str:
    """
    Generate the SolidJS adapter TypeScript code.

    This can be written to a file and used in SolidJS projects.
    """
    return '''/**
 * Django Matt Pages - SolidJS Adapter
 *
 * Auto-generated client-side adapter for Django Matt Pages.
 * Uses Solid signals and stores for reactive page state.
 *
 * Usage:
 *   import { usePage, useShared, navigate, Link } from './page-adapter';
 *
 *   function UserList() {
 *     const page = usePage<{ users: User[] }>();
 *     return <For each={page().users}>{user => <li>{user.name}</li>}</For>;
 *   }
 */

import {
  createSignal,
  createContext,
  useContext,
  createEffect,
  onMount,
  onCleanup,
  type JSX,
  type Component,
  type Accessor,
} from 'solid-js';
import { createStore, produce } from 'solid-js/store';

// Types

export interface PageData<T = Record<string, unknown>> {
  component: string;
  props: T;
  url: string;
  version: string;
  shared: Record<string, unknown>;
  errors?: Record<string, string[]>;
  flash?: FlashMessage[];
  title?: string;
  meta?: Record<string, string>;
  preserveScroll?: boolean;
  clearHistory?: boolean;
  replaceState?: boolean;
}

export interface FlashMessage {
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  [key: string]: unknown;
}

export interface NavigateOptions {
  replace?: boolean;
  preserveScroll?: boolean;
  data?: Record<string, unknown>;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
}

interface PageContextValue {
  page: Accessor<PageData>;
  isNavigating: Accessor<boolean>;
  navigate: (url: string, options?: NavigateOptions) => Promise<void>;
  reload: () => Promise<void>;
}

// Context

const PageContext = createContext<PageContextValue>();

// Store

const [pageStore, setPageStore] = createStore<{
  page: PageData;
  isNavigating: boolean;
  flash: FlashMessage[];
}>({
  page: {
    component: '',
    props: {},
    url: '',
    version: '',
    shared: {},
  },
  isNavigating: false,
  flash: [],
});

let currentVersion = '';

// Navigation

async function navigateInternal(
  url: string,
  options: NavigateOptions = {}
): Promise<void> {
  setPageStore('isNavigating', true);

  try {
    const headers: Record<string, string> = {
      'X-Page': 'true',
      'Accept': 'application/json',
    };

    if (currentVersion) {
      headers['X-Page-Version'] = currentVersion;
    }

    const fetchOptions: RequestInit = {
      method: options.method || 'GET',
      headers,
      credentials: 'same-origin',
    };

    if (options.data && options.method !== 'GET') {
      headers['Content-Type'] = 'application/json';
      fetchOptions.body = JSON.stringify(options.data);
    }

    const response = await fetch(url, fetchOptions);

    // Handle version mismatch
    if (response.status === 409) {
      const location = response.headers.get('X-Page-Location');
      window.location.href = location || url;
      return;
    }

    // Handle redirects
    if (response.status === 303) {
      const location = response.headers.get('X-Page-Location');
      if (location) {
        return navigateInternal(location, { replace: true });
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch page: ${response.status}`);
    }

    const newPage: PageData = await response.json();
    currentVersion = newPage.version;

    // Update store
    setPageStore(
      produce((s) => {
        s.page = newPage;
        if (newPage.flash) {
          s.flash = newPage.flash;
        }
      })
    );

    // Update browser history
    if (options.replace || newPage.replaceState) {
      window.history.replaceState({ page: newPage }, '', newPage.url);
    } else {
      window.history.pushState({ page: newPage }, '', newPage.url);
    }

    // Update document title
    if (newPage.title) {
      document.title = newPage.title;
    }

    // Scroll handling
    if (!options.preserveScroll && !newPage.preserveScroll) {
      window.scrollTo(0, 0);
    }
  } catch (error) {
    console.error('Navigation failed:', error);
    throw error;
  } finally {
    setPageStore('isNavigating', false);
  }
}

/**
 * Navigate to a new page.
 */
export async function navigate(
  url: string,
  options: NavigateOptions = {}
): Promise<void> {
  return navigateInternal(url, options);
}

/**
 * Reload the current page.
 */
export async function reload(): Promise<void> {
  if (pageStore.page.url) {
    await navigate(pageStore.page.url, { replace: true });
  }
}

// Hooks

/**
 * Access the current page props.
 *
 * @example
 * function UserList() {
 *   const page = usePage<{ users: User[] }>();
 *   return <For each={page().users}>{u => <li>{u.name}</li>}</For>;
 * }
 */
export function usePage<T = Record<string, unknown>>(): Accessor<T> {
  return () => pageStore.page.props as T;
}

/**
 * Access shared data.
 */
export function useShared<T = Record<string, unknown>>(): Accessor<T> {
  return () => pageStore.page.shared as T;
}

/**
 * Access validation errors.
 */
export function usePageErrors(): Accessor<Record<string, string[]>> {
  return () => pageStore.page.errors || {};
}

/**
 * Access flash messages.
 */
export function useFlash(): Accessor<FlashMessage[]> {
  return () => pageStore.flash;
}

/**
 * Check if currently navigating.
 */
export function useIsNavigating(): Accessor<boolean> {
  return () => pageStore.isNavigating;
}

/**
 * Clear flash messages.
 */
export function clearFlash(): void {
  setPageStore('flash', []);
}

// Components

interface LinkProps extends JSX.AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string;
  replace?: boolean;
  preserveScroll?: boolean;
}

/**
 * Link component for SPA navigation.
 */
export function Link(props: LinkProps): JSX.Element {
  const handleClick = (e: MouseEvent) => {
    // Let browser handle if modified click
    if (
      e.defaultPrevented ||
      e.button !== 0 ||
      e.metaKey ||
      e.ctrlKey ||
      e.shiftKey ||
      e.altKey ||
      props.target ||
      props.download
    ) {
      return;
    }

    // Check same origin
    try {
      const url = new URL(props.href, window.location.origin);
      if (url.origin !== window.location.origin) {
        return;
      }
    } catch {
      return;
    }

    e.preventDefault();
    navigate(props.href, {
      replace: props.replace,
      preserveScroll: props.preserveScroll,
    });
  };

  return (
    <a {...props} onClick={handleClick}>
      {props.children}
    </a>
  );
}

// Provider

interface PageProviderProps {
  children: JSX.Element;
}

/**
 * Page provider component.
 * Wrap your app with this to enable page features.
 *
 * @example
 * render(() => (
 *   <PageProvider>
 *     <App />
 *   </PageProvider>
 * ), document.getElementById('app'));
 */
export function PageProvider(props: PageProviderProps): JSX.Element {
  onMount(() => {
    // Get initial page data
    const script = document.getElementById('page-data');
    if (script) {
      try {
        const initialPage = JSON.parse(script.textContent || '');
        currentVersion = initialPage.version;

        setPageStore(
          produce((s) => {
            s.page = initialPage;
            if (initialPage.flash) {
              s.flash = initialPage.flash;
            }
          })
        );

        // Store in history state
        window.history.replaceState({ page: initialPage }, '', initialPage.url);
      } catch (error) {
        console.error('Failed to parse page data:', error);
      }
    }

    // Handle browser back/forward
    const handlePopState = (event: PopStateEvent) => {
      if (event.state?.page) {
        setPageStore(
          produce((s) => {
            s.page = event.state.page;
            if (event.state.page.flash) {
              s.flash = event.state.page.flash;
            }
          })
        );
      } else {
        navigate(window.location.pathname + window.location.search, {
          replace: true,
        });
      }
    };

    window.addEventListener('popstate', handlePopState);

    onCleanup(() => {
      window.removeEventListener('popstate', handlePopState);
    });
  });

  const contextValue: PageContextValue = {
    page: () => pageStore.page,
    isNavigating: () => pageStore.isNavigating,
    navigate,
    reload,
  };

  return (
    <PageContext.Provider value={contextValue}>
      {props.children}
    </PageContext.Provider>
  );
}

export default {
  usePage,
  useShared,
  usePageErrors,
  useFlash,
  useIsNavigating,
  navigate,
  reload,
  clearFlash,
  Link,
  PageProvider,
};
'''


__all__ = [
    "generate_solid_adapter",
]

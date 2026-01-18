"""
React client adapter generator.

Generates the @django-matt/react adapter code that handles:
- Page mounting and hydration
- SPA navigation with X-Page header
- Shared data access
- Form submission
- Flash messages
"""


def generate_react_adapter() -> str:
    """
    Generate the React adapter TypeScript code.

    This can be written to a file and used in React projects.

    Usage:
        from django_matt.pages.adapters import generate_react_adapter

        adapter_code = generate_react_adapter()
        with open("src/lib/page-adapter.tsx", "w") as f:
            f.write(adapter_code)
    """
    return """/**
 * Django Matt Pages - React Adapter
 *
 * Auto-generated client-side adapter for Django Matt Pages.
 * Handles page mounting, SPA navigation, and state management.
 *
 * Usage:
 *   import { createPageApp, usePage, Link } from './page-adapter';
 *
 *   const app = createPageApp({
 *     resolve: (name) => import(`./pages/${name}.tsx`),
 *   });
 *
 *   app.mount(document.getElementById('app'));
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useTransition,
  type ReactNode,
  type ComponentType,
  type MouseEvent,
} from 'react';

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

export interface PageAppConfig {
  resolve: (name: string) => Promise<{ default: ComponentType<unknown> }>;
  layout?: ComponentType<{ children: ReactNode; shared: Record<string, unknown> }>;
  onNavigate?: (page: PageData) => void;
  onError?: (error: Error) => void;
}

// Context

interface PageContextValue {
  page: PageData;
  shared: Record<string, unknown>;
  errors: Record<string, string[]>;
  flash: FlashMessage[];
  isNavigating: boolean;
  navigate: (url: string, options?: NavigateOptions) => Promise<void>;
  reload: () => Promise<void>;
}

const PageContext = createContext<PageContextValue | null>(null);

// Hooks

/**
 * Access the current page data and props.
 *
 * @example
 * function UserList() {
 *   const { users } = usePage<{ users: User[] }>();
 *   return <ul>{users.map(u => <li key={u.id}>{u.name}</li>)}</ul>;
 * }
 */
export function usePage<T = Record<string, unknown>>(): T {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('usePage must be used within a PageProvider');
  }
  return context.page.props as T;
}

/**
 * Access shared data (auth, etc.).
 *
 * @example
 * function Header() {
 *   const { user, isAuthenticated } = useShared<AuthShared>();
 *   return isAuthenticated ? <span>{user.name}</span> : <a href="/login">Login</a>;
 * }
 */
export function useShared<T = Record<string, unknown>>(): T {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('useShared must be used within a PageProvider');
  }
  return context.shared as T;
}

/**
 * Access validation errors.
 *
 * @example
 * function UserForm() {
 *   const errors = usePageErrors();
 *   return (
 *     <form>
 *       <input name="email" />
 *       {errors.email && <span className="error">{errors.email[0]}</span>}
 *     </form>
 *   );
 * }
 */
export function usePageErrors(): Record<string, string[]> {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('usePageErrors must be used within a PageProvider');
  }
  return context.errors;
}

/**
 * Access flash messages.
 *
 * @example
 * function Notifications() {
 *   const flash = useFlash();
 *   return (
 *     <div>
 *       {flash.map((msg, i) => (
 *         <div key={i} className={`alert alert-${msg.type}`}>{msg.message}</div>
 *       ))}
 *     </div>
 *   );
 * }
 */
export function useFlash(): FlashMessage[] {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('useFlash must be used within a PageProvider');
  }
  return context.flash;
}

/**
 * Get navigation function.
 *
 * @example
 * function LogoutButton() {
 *   const navigate = usePageNavigate();
 *   const handleLogout = async () => {
 *     await fetch('/logout', { method: 'POST' });
 *     await navigate('/');
 *   };
 *   return <button onClick={handleLogout}>Logout</button>;
 * }
 */
export function usePageNavigate() {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('usePageNavigate must be used within a PageProvider');
  }
  return context.navigate;
}

/**
 * Check if currently navigating.
 */
export function useIsNavigating(): boolean {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('useIsNavigating must be used within a PageProvider');
  }
  return context.isNavigating;
}

interface NavigateOptions {
  replace?: boolean;
  preserveScroll?: boolean;
  data?: Record<string, unknown>;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
}

/**
 * Hook for form submission that handles page responses.
 *
 * @example
 * function UserForm() {
 *   const { submit, isSubmitting } = usePageForm();
 *
 *   const handleSubmit = (e: FormEvent) => {
 *     e.preventDefault();
 *     submit('/users', { data: formData });
 *   };
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       ...
 *       <button disabled={isSubmitting}>Submit</button>
 *     </form>
 *   );
 * }
 */
export function usePageForm() {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('usePageForm must be used within a PageProvider');
  }

  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = useCallback(
    async (url: string, options: NavigateOptions = {}) => {
      setIsSubmitting(true);
      try {
        await context.navigate(url, {
          method: 'POST',
          ...options,
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    [context.navigate]
  );

  return { submit, isSubmitting };
}

// Components

interface LinkProps extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
  href: string;
  replace?: boolean;
  preserveScroll?: boolean;
  prefetch?: boolean;
  children: ReactNode;
}

/**
 * Link component for SPA navigation.
 *
 * @example
 * <Link href="/users">Users</Link>
 * <Link href="/users/1" replace>View User</Link>
 */
export function Link({
  href,
  replace = false,
  preserveScroll = false,
  prefetch = false,
  children,
  onClick,
  ...props
}: LinkProps) {
  const context = useContext(PageContext);

  const handleClick = useCallback(
    (e: MouseEvent<HTMLAnchorElement>) => {
      // Let the browser handle if:
      // - Modified click (ctrl, meta, shift)
      // - Different origin
      // - Download link
      // - Target specified
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
        onClick?.(e);
        return;
      }

      // Check if same origin
      try {
        const url = new URL(href, window.location.origin);
        if (url.origin !== window.location.origin) {
          onClick?.(e);
          return;
        }
      } catch {
        onClick?.(e);
        return;
      }

      e.preventDefault();
      onClick?.(e);

      context?.navigate(href, { replace, preserveScroll });
    },
    [href, replace, preserveScroll, onClick, context, props.target, props.download]
  );

  return (
    <a href={href} onClick={handleClick} {...props}>
      {children}
    </a>
  );
}

// Page App

interface PageAppInstance {
  mount: (element: HTMLElement) => void;
  unmount: () => void;
}

/**
 * Create a page app instance.
 *
 * @example
 * const app = createPageApp({
 *   resolve: (name) => import(`./pages/${name}.tsx`),
 *   layout: AppLayout,
 * });
 *
 * app.mount(document.getElementById('app')!);
 */
export function createPageApp(config: PageAppConfig): PageAppInstance {
  let root: ReturnType<typeof import('react-dom/client').createRoot> | null = null;
  let currentPage: PageData | null = null;

  // Get initial page data from script tag
  function getInitialPageData(): PageData | null {
    const script = document.getElementById('page-data');
    if (script) {
      try {
        return JSON.parse(script.textContent || '');
      } catch {
        console.error('Failed to parse page data');
      }
    }
    return null;
  }

  // Fetch page data via XHR
  async function fetchPage(
    url: string,
    options: NavigateOptions = {}
  ): Promise<PageData> {
    const headers: Record<string, string> = {
      'X-Page': 'true',
      'Accept': 'application/json',
    };

    if (currentPage?.version) {
      headers['X-Page-Version'] = currentPage.version;
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

    // Handle version mismatch (full reload needed)
    if (response.status === 409) {
      const location = response.headers.get('X-Page-Location');
      window.location.href = location || url;
      throw new Error('Version mismatch, reloading page');
    }

    // Handle redirects
    if (response.status === 303) {
      const location = response.headers.get('X-Page-Location');
      if (location) {
        return fetchPage(location, { replace: true });
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch page: ${response.status}`);
    }

    return response.json();
  }

  // Page Provider Component
  function PageProvider({ children }: { children: ReactNode }) {
    const [page, setPage] = useState<PageData | null>(currentPage);
    const [isNavigating, startTransition] = useTransition();
    const [Component, setComponent] = useState<ComponentType<unknown> | null>(null);

    // Load component when page changes
    useEffect(() => {
      if (!page) return;

      config.resolve(page.component).then((module) => {
        setComponent(() => module.default);
      }).catch((error) => {
        console.error(`Failed to load component: ${page.component}`, error);
        config.onError?.(error);
      });
    }, [page?.component]);

    // Update document title
    useEffect(() => {
      if (page?.title) {
        document.title = page.title;
      }
    }, [page?.title]);

    // Navigate function
    const navigate = useCallback(
      async (url: string, options: NavigateOptions = {}) => {
        startTransition(async () => {
          try {
            const newPage = await fetchPage(url, options);
            currentPage = newPage;
            setPage(newPage);

            // Update browser history
            if (options.replace || newPage.replaceState) {
              window.history.replaceState({ page: newPage }, '', newPage.url);
            } else {
              window.history.pushState({ page: newPage }, '', newPage.url);
            }

            // Scroll handling
            if (!options.preserveScroll && !newPage.preserveScroll) {
              window.scrollTo(0, 0);
            }

            config.onNavigate?.(newPage);
          } catch (error) {
            console.error('Navigation failed:', error);
            config.onError?.(error as Error);
          }
        });
      },
      []
    );

    // Reload current page
    const reload = useCallback(async () => {
      if (page) {
        await navigate(page.url, { replace: true });
      }
    }, [page, navigate]);

    // Handle browser back/forward
    useEffect(() => {
      const handlePopState = (event: PopStateEvent) => {
        if (event.state?.page) {
          currentPage = event.state.page;
          setPage(event.state.page);
        } else {
          // Fallback: fetch the page
          navigate(window.location.pathname + window.location.search, {
            replace: true,
          });
        }
      };

      window.addEventListener('popstate', handlePopState);
      return () => window.removeEventListener('popstate', handlePopState);
    }, [navigate]);

    if (!page || !Component) {
      return null; // Loading state
    }

    const contextValue: PageContextValue = {
      page,
      shared: page.shared,
      errors: page.errors || {},
      flash: page.flash || [],
      isNavigating,
      navigate,
      reload,
    };

    const content = <Component {...page.props} />;

    return (
      <PageContext.Provider value={contextValue}>
        {config.layout ? (
          <config.layout shared={page.shared}>{content}</config.layout>
        ) : (
          content
        )}
      </PageContext.Provider>
    );
  }

  return {
    mount(element: HTMLElement) {
      // Get initial page data
      currentPage = getInitialPageData();

      if (!currentPage) {
        console.error('No page data found');
        return;
      }

      // Store in history state
      window.history.replaceState({ page: currentPage }, '', currentPage.url);

      // Mount React
      import('react-dom/client').then(({ createRoot }) => {
        root = createRoot(element);
        root.render(
          <React.StrictMode>
            <PageProvider>{null}</PageProvider>
          </React.StrictMode>
        );
      });
    },

    unmount() {
      root?.unmount();
      root = null;
    },
  };
}

export default {
  createPageApp,
  usePage,
  useShared,
  usePageErrors,
  useFlash,
  usePageNavigate,
  useIsNavigating,
  usePageForm,
  Link,
};
"""


__all__ = [
    "generate_react_adapter",
]

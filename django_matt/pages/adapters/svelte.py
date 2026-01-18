"""
Svelte client adapter generator.

Generates the @django-matt/svelte adapter code that handles:
- Page mounting and hydration
- SPA navigation with X-Page header
- Svelte stores for page state
- Form submission
"""


def generate_svelte_adapter() -> str:
    """
    Generate the Svelte adapter TypeScript code.

    This can be written to a file and used in Svelte/SvelteKit projects.
    """
    return """/**
 * Django Matt Pages - Svelte Adapter
 *
 * Auto-generated client-side adapter for Django Matt Pages.
 * Uses Svelte stores for reactive page state.
 *
 * Usage:
 *   import { page, shared, navigate, Link } from './page-adapter';
 *
 *   $: users = $page.props.users;
 *   $: user = $shared.auth?.user;
 */

import { writable, derived, get, type Writable, type Readable } from 'svelte/store';

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

// Stores

/** Current page data */
export const page: Writable<PageData> = writable({
  component: '',
  props: {},
  url: '',
  version: '',
  shared: {},
});

/** Shared data (auth, etc.) */
export const shared: Readable<Record<string, unknown>> = derived(
  page,
  ($page) => $page.shared
);

/** Page props */
export const props: Readable<Record<string, unknown>> = derived(
  page,
  ($page) => $page.props
);

/** Validation errors */
export const errors: Readable<Record<string, string[]>> = derived(
  page,
  ($page) => $page.errors || {}
);

/** Flash messages */
export const flash: Writable<FlashMessage[]> = writable([]);

/** Navigation in progress */
export const isNavigating: Writable<boolean> = writable(false);

// Navigation

let currentVersion = '';

/**
 * Navigate to a new page.
 *
 * @example
 * import { navigate } from './page-adapter';
 *
 * function handleClick() {
 *   navigate('/users/1');
 * }
 *
 * // Form submission
 * async function handleSubmit() {
 *   await navigate('/users', {
 *     method: 'POST',
 *     data: formData,
 *   });
 * }
 */
export async function navigate(
  url: string,
  options: NavigateOptions = {}
): Promise<void> {
  isNavigating.set(true);

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
        return navigate(location, { replace: true });
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch page: ${response.status}`);
    }

    const newPage: PageData = await response.json();
    currentVersion = newPage.version;

    // Update stores
    page.set(newPage);

    if (newPage.flash) {
      flash.set(newPage.flash);
    }

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
    isNavigating.set(false);
  }
}

/**
 * Reload the current page.
 */
export async function reload(): Promise<void> {
  const currentPage = get(page);
  if (currentPage.url) {
    await navigate(currentPage.url, { replace: true });
  }
}

// Initialize

/**
 * Initialize the page adapter.
 * Call this in your root layout or app entry.
 *
 * @example
 * // +layout.svelte
 * <script>
 *   import { initPage } from './page-adapter';
 *   import { onMount } from 'svelte';
 *
 *   onMount(() => {
 *     initPage();
 *   });
 * </script>
 */
export function initPage(): void {
  // Get initial page data from script tag
  const script = document.getElementById('page-data');
  if (script) {
    try {
      const initialPage = JSON.parse(script.textContent || '');
      currentVersion = initialPage.version;
      page.set(initialPage);

      if (initialPage.flash) {
        flash.set(initialPage.flash);
      }

      // Store in history state
      window.history.replaceState({ page: initialPage }, '', initialPage.url);
    } catch (error) {
      console.error('Failed to parse page data:', error);
    }
  }

  // Handle browser back/forward
  window.addEventListener('popstate', (event) => {
    if (event.state?.page) {
      page.set(event.state.page);
      if (event.state.page.flash) {
        flash.set(event.state.page.flash);
      }
    } else {
      // Fallback: fetch the page
      navigate(window.location.pathname + window.location.search, {
        replace: true,
      });
    }
  });
}

// Clear flash messages
export function clearFlash(): void {
  flash.set([]);
}

export default {
  page,
  shared,
  props,
  errors,
  flash,
  isNavigating,
  navigate,
  reload,
  initPage,
  clearFlash,
};
"""


__all__ = [
    "generate_svelte_adapter",
]

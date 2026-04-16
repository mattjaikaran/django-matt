"""
Vue client adapter generator.

Generates the @django-matt/vue adapter code that handles:
- Page mounting and hydration with Vue 3 Composition API
- SPA navigation with X-Page header
- Reactive page state via composables
- Form submission
- Flash messages
"""


def generate_vue_adapter() -> str:
    """
    Generate the Vue adapter TypeScript code.

    This can be written to a file and used in Vue 3 projects.

    Usage:
        from django_matt.pages.adapters import generate_vue_adapter

        adapter_code = generate_vue_adapter()
        with open("src/lib/page-adapter.ts", "w") as f:
            f.write(adapter_code)
    """
    return """/**
 * Django Matt Pages - Vue 3 Adapter
 *
 * Auto-generated client-side adapter for Django Matt Pages.
 * Uses Vue 3 Composition API with reactive page state.
 *
 * Usage:
 *   import { createPageApp, usePage, useShared, Link } from './page-adapter';
 *
 *   const app = createPageApp({
 *     resolve: (name) => import(`./pages/${name}.vue`),
 *   });
 *
 *   app.mount('#app');
 */

import {
  createApp,
  defineComponent,
  ref,
  computed,
  reactive,
  provide,
  inject,
  onMounted,
  watch,
  h,
  type App,
  type Component,
  type InjectionKey,
  type Ref,
} from 'vue';

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
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}

export interface PageAppOptions {
  resolve: (name: string) => Promise<{ default: Component }>;
  setup?: (app: App) => void;
  initialPage?: PageData;
}

// Injection keys
const PAGE_KEY: InjectionKey<Ref<PageData>> = Symbol('page');
const SHARED_KEY: InjectionKey<Ref<Record<string, unknown>>> = Symbol('shared');
const NAVIGATE_KEY: InjectionKey<typeof navigate> = Symbol('navigate');

// Internal state
let currentPage = ref<PageData>({
  component: '',
  props: {},
  url: window.location.pathname,
  version: '',
  shared: {},
});

let resolveComponent: PageAppOptions['resolve'];
let currentComponent = ref<Component | null>(null);

// Navigation

export async function navigate(
  url: string,
  options: {
    method?: string;
    data?: Record<string, unknown> | FormData;
    replace?: boolean;
    preserveScroll?: boolean;
    headers?: Record<string, string>;
  } = {},
): Promise<void> {
  const {
    method = 'GET',
    data,
    replace = false,
    preserveScroll = false,
    headers: extraHeaders = {},
  } = options;

  const headers: Record<string, string> = {
    'X-Page': 'true',
    'X-Page-Version': currentPage.value.version,
    Accept: 'application/json',
    ...extraHeaders,
  };

  // Partial reloads
  const fetchOptions: RequestInit = {
    method,
    headers,
    credentials: 'same-origin',
  };

  if (data) {
    if (data instanceof FormData) {
      fetchOptions.body = data;
    } else {
      headers['Content-Type'] = 'application/json';
      fetchOptions.body = JSON.stringify(data);
    }
  }

  const response = await fetch(url, fetchOptions);

  // Version mismatch — full page reload
  if (response.status === 409) {
    window.location.href = url;
    return;
  }

  if (!response.ok) {
    throw new Error(`Navigation failed: ${response.status}`);
  }

  const pageData: PageData = await response.json();

  // Update state
  currentPage.value = pageData;

  // Resolve and set component
  if (resolveComponent) {
    const module = await resolveComponent(pageData.component);
    currentComponent.value = module.default;
  }

  // Update URL
  if (replace) {
    window.history.replaceState({}, '', pageData.url || url);
  } else {
    window.history.pushState({}, '', pageData.url || url);
  }

  // Update title
  if (pageData.title) {
    document.title = pageData.title;
  }

  // Scroll
  if (!preserveScroll && !pageData.preserveScroll) {
    window.scrollTo(0, 0);
  }
}

// Composables

export function usePage<T = Record<string, unknown>>() {
  const page = inject(PAGE_KEY);
  if (!page) {
    throw new Error('usePage() must be used within a PageApp');
  }
  return computed(() => page.value as PageData<T>);
}

export function useShared<T = Record<string, unknown>>() {
  const shared = inject(SHARED_KEY);
  if (!shared) {
    throw new Error('useShared() must be used within a PageApp');
  }
  return computed(() => shared.value as T);
}

export function usePageProps<T = Record<string, unknown>>() {
  const page = usePage<T>();
  return computed(() => page.value.props);
}

export function useErrors() {
  const page = usePage();
  return computed(() => page.value.errors || {});
}

export function useFlash() {
  const page = usePage();
  return computed(() => page.value.flash || []);
}

export function useForm<T extends Record<string, unknown>>(initial: T) {
  const data = reactive({ ...initial }) as T;
  const errors = ref<Record<string, string[]>>({});
  const processing = ref(false);

  async function submit(
    method: string,
    url: string,
    options: { preserveScroll?: boolean; replace?: boolean } = {},
  ) {
    processing.value = true;
    errors.value = {};

    try {
      await navigate(url, {
        method,
        data: data as Record<string, unknown>,
        ...options,
      });

      // Check for validation errors
      const pageErrors = currentPage.value.errors;
      if (pageErrors) {
        errors.value = pageErrors;
      }
    } finally {
      processing.value = false;
    }
  }

  function reset(...fields: (keyof T)[]) {
    if (fields.length === 0) {
      Object.assign(data, initial);
    } else {
      for (const field of fields) {
        (data as any)[field] = initial[field];
      }
    }
  }

  return reactive({
    data,
    errors,
    processing,
    submit,
    reset,
    post: (url: string, opts?: any) => submit('POST', url, opts),
    put: (url: string, opts?: any) => submit('PUT', url, opts),
    patch: (url: string, opts?: any) => submit('PATCH', url, opts),
    delete: (url: string, opts?: any) => submit('DELETE', url, opts),
  });
}

// Link component

export const Link = defineComponent({
  name: 'PageLink',
  props: {
    href: { type: String, required: true },
    method: { type: String, default: 'GET' },
    replace: { type: Boolean, default: false },
    preserveScroll: { type: Boolean, default: false },
    as: { type: String, default: 'a' },
  },
  emits: ['navigate'],
  setup(props, { slots, emit }) {
    async function handleClick(e: MouseEvent) {
      e.preventDefault();

      // Allow cmd/ctrl+click for new tab
      if (e.metaKey || e.ctrlKey) {
        window.open(props.href, '_blank');
        return;
      }

      emit('navigate', props.href);
      await navigate(props.href, {
        method: props.method,
        replace: props.replace,
        preserveScroll: props.preserveScroll,
      });
    }

    return () =>
      h(
        props.as,
        {
          href: props.href,
          onClick: handleClick,
        },
        slots.default?.(),
      );
  },
});

// App wrapper component

const PageWrapper = defineComponent({
  name: 'PageWrapper',
  setup() {
    provide(PAGE_KEY, currentPage);
    provide(SHARED_KEY, computed(() => currentPage.value.shared));
    provide(NAVIGATE_KEY, navigate);

    return () => {
      if (currentComponent.value) {
        return h(currentComponent.value, currentPage.value.props);
      }
      return null;
    };
  },
});

// App factory

export function createPageApp(options: PageAppOptions) {
  resolveComponent = options.resolve;

  const app = createApp(PageWrapper);

  // Run user setup
  if (options.setup) {
    options.setup(app);
  }

  // Register Link component globally
  app.component('PageLink', Link);

  // Handle browser back/forward
  window.addEventListener('popstate', async () => {
    await navigate(window.location.pathname + window.location.search, {
      replace: true,
      preserveScroll: true,
    });
  });

  // Load initial page data
  const initialEl = document.getElementById('page-data');
  if (initialEl?.textContent) {
    try {
      const initialData = JSON.parse(initialEl.textContent);
      currentPage.value = initialData;

      resolveComponent(initialData.component).then((module) => {
        currentComponent.value = module.default;
      });
    } catch {
      // Fall back to current URL
    }
  }

  return app;
}

// Re-exports
export { navigate as router };
export type { PageData, FlashMessage, PageAppOptions };
"""


__all__ = [
    "generate_vue_adapter",
]
"""

/**
 * Environment detection hooks
 * Uses Zustand store for config state
 */

import {
  useEnvConfig,
  useIsDjangoSPA as useIsDjangoSPAStore,
  useIsStandalone as useIsStandaloneStore,
} from '@/lib/store';
import { useSyncExternalStore } from 'react';

export function useEnvironment() {
  return useEnvConfig();
}

export function useIsDjangoSPA() {
  return useIsDjangoSPAStore();
}

export function useIsStandalone() {
  return useIsStandaloneStore();
}

export function useIsDevelopment() {
  const env = useEnvironment();
  return env.isDevelopment;
}

export function useIsProduction() {
  const env = useEnvironment();
  return env.isProduction;
}

// Using useSyncExternalStore for optimal performance (no useEffect)
const subscribeToOnline = (callback: () => void) => {
  window.addEventListener('online', callback);
  window.addEventListener('offline', callback);
  return () => {
    window.removeEventListener('online', callback);
    window.removeEventListener('offline', callback);
  };
};

const getOnlineSnapshot = () => navigator.onLine;
const getOnlineServerSnapshot = () => true;

export function useNetworkStatus() {
  return useSyncExternalStore(
    subscribeToOnline,
    getOnlineSnapshot,
    getOnlineServerSnapshot
  );
}

// Viewport size with useSyncExternalStore
const subscribeToResize = (callback: () => void) => {
  window.addEventListener('resize', callback);
  return () => window.removeEventListener('resize', callback);
};

const getViewportSnapshot = () => ({
  width: window.innerWidth,
  height: window.innerHeight,
});

const getViewportServerSnapshot = () => ({ width: 1024, height: 768 });

// Cache for viewport to avoid object recreation
let cachedViewport = { width: 0, height: 0 };
const getMemoizedViewportSnapshot = () => {
  const current = getViewportSnapshot();
  if (
    current.width !== cachedViewport.width ||
    current.height !== cachedViewport.height
  ) {
    cachedViewport = current;
  }
  return cachedViewport;
};

export function useViewportSize() {
  return useSyncExternalStore(
    subscribeToResize,
    getMemoizedViewportSnapshot,
    getViewportServerSnapshot
  );
}

// Media query with useSyncExternalStore
export function useMediaQuery(query: string) {
  const subscribe = (callback: () => void) => {
    const mediaQuery = window.matchMedia(query);
    mediaQuery.addEventListener('change', callback);
    return () => mediaQuery.removeEventListener('change', callback);
  };

  const getSnapshot = () => window.matchMedia(query).matches;
  const getServerSnapshot = () => false;

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function useIsMobile() {
  return useMediaQuery('(max-width: 768px)');
}

export function useIsTablet() {
  return useMediaQuery('(min-width: 769px) and (max-width: 1024px)');
}

export function useIsDesktop() {
  return useMediaQuery('(min-width: 1025px)');
}

export function usePrefersReducedMotion() {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

export function usePrefersDarkMode() {
  return useMediaQuery('(prefers-color-scheme: dark)');
}

/**
 * Hooks Exports
 * Central export point for all React hooks
 */

// ============================================
// API Hooks - Generic API operations
// ============================================
export {
  useApiDelete,
  useApiDeleteById,
  // Query hooks
  useApiGet,
  useApiInfinite,
  useApiPatch,
  // Mutation hooks
  useApiPost,
  useApiPut,
  useApiQuery,
  useInvalidate,
  // Optimistic updates
  useOptimisticAdd,
  useOptimisticMutation,
  useOptimisticRemove,
  useOptimisticUpdate,
  usePrefetch,
} from './api';

// ============================================
// Domain Hooks - Auth
// ============================================
export {
  useChangePassword,
  useLogin,
  useLogout,
  useMagicLink,
  useProfile,
  useRegister,
  useUpdateProfile,
} from './use-auth';

// ============================================
// Domain Hooks - Todos
// ============================================
export {
  useCreateTodo,
  useDeleteTodo,
  useTodo,
  useTodos,
  useTodoStats,
  useToggleTodo,
  useUpdateTodo,
} from './use-todo';

// ============================================
// Utility Hooks - Common utilities
// ============================================
export {
  useBreakpoint,
  // Debounce
  useDebounce,
  useDebouncedCallback,
  useDebounceWithLoading,
  useIsDesktop,
  useIsLargeDesktop,
  useIsMobile,
  useIsTablet,
  // Storage
  useLocalStorage,
  // Media queries
  useMediaQuery,
  usePrefersDarkMode,
  usePrefersReducedMotion,
  useSessionStorage,
} from './utils';

// ============================================
// Store Hooks - Config and Theme (Zustand)
// ============================================
export {
  useApiConfig,
  useAppConfig,
  useAuth,
  useAuthConfig,
  useDjangoConfig,
  useEnvConfig,
  useFeatureEnabled,
  useIsDjangoSPA,
  useIsStandalone,
  useSetTheme,
  useTheme,
  useTodos as useTodosStore,
  useToggleTheme,
  useUI,
} from '@/lib/store';

// ============================================
// Legacy exports for backwards compatibility
// ============================================
export * from './use-environment';

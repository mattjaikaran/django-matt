import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { createAuthSlice, type AuthSlice } from './slices/authSlice';
import { createConfigSlice, type ConfigSlice } from './slices/configSlice';
import { createTodoSlice, type TodoSlice } from './slices/todoSlice';
import { createUISlice, type UISlice } from './slices/uiSlice';

// Combined store type
export type AppStore = AuthSlice & TodoSlice & UISlice & ConfigSlice;

// Create the store with all slices
export const useStore = create<AppStore>()(
  devtools(
    persist(
      (...args) => ({
        ...createAuthSlice(...args),
        ...createTodoSlice(...args),
        ...createUISlice(...args),
        ...createConfigSlice(...args),
      }),
      {
        name: 'app-store',
        partialize: state => ({
          // Only persist UI theme
          theme: state.theme,
          // Don't persist auth state as it's handled separately in localStorage
          // Don't persist todos as they should be fetched fresh
          // Don't persist config as it comes from env
        }),
      }
    ),
    {
      name: 'app-store',
    }
  )
);

// Selector hooks for better performance
export const useAuth = () =>
  useStore(state => ({
    user: state.user,
    tokens: state.tokens,
    isAuthenticated: state.isAuthenticated,
    isLoading: state.isLoading,
    error: state.error,
    login: state.login,
    register: state.register,
    magicLink: state.magicLink,
    logout: state.logout,
    refreshToken: state.refreshToken,
    setUser: state.setUser,
    setTokens: state.setTokens,
    setLoading: state.setLoading,
    setError: state.setError,
    clearError: state.clearError,
    initializeAuth: state.initializeAuth,
  }));

export const useTodos = () =>
  useStore(state => ({
    todos: state.todos,
    isLoading: state.isLoading,
    error: state.error,
    filters: state.filters,
    fetchTodos: state.fetchTodos,
    createTodo: state.createTodo,
    updateTodo: state.updateTodo,
    deleteTodo: state.deleteTodo,
    toggleTodo: state.toggleTodo,
    setFilters: state.setFilters,
    clearFilters: state.clearFilters,
    setLoading: state.setLoading,
    setError: state.setError,
    clearError: state.clearError,
  }));

export const useUI = () =>
  useStore(state => ({
    theme: state.theme,
    sidebarOpen: state.sidebarOpen,
    notifications: state.notifications,
    setTheme: state.setTheme,
    toggleTheme: state.toggleTheme,
    setSidebarOpen: state.setSidebarOpen,
    toggleSidebar: state.toggleSidebar,
    addNotification: state.addNotification,
    removeNotification: state.removeNotification,
    clearNotifications: state.clearNotifications,
  }));

export const useAppConfig = () =>
  useStore(state => ({
    config: state.config,
    isDjangoSPA: state.isDjangoSPA,
    isStandalone: state.isStandalone,
    updateConfig: state.updateConfig,
    isFeatureEnabled: state.isFeatureEnabled,
    setFeature: state.setFeature,
  }));

// Granular selectors for minimal re-renders
export const useTheme = () => useStore(state => state.theme);
export const useSetTheme = () => useStore(state => state.setTheme);
export const useToggleTheme = () => useStore(state => state.toggleTheme);
export const useIsDjangoSPA = () => useStore(state => state.isDjangoSPA);
export const useIsStandalone = () => useStore(state => state.isStandalone);
export const useFeatureEnabled = (
  feature: keyof AppStore['config']['features']
) => useStore(state => state.config.features[feature]);
export const useApiConfig = () => useStore(state => state.config.api);
export const useAuthConfig = () => useStore(state => state.config.auth);
export const useDjangoConfig = () => useStore(state => state.config.django);
export const useEnvConfig = () => useStore(state => state.config.env);

// Initialize store on app start
export const initializeStore = () => {
  const { initializeAuth, setTheme, theme } = useStore.getState();
  initializeAuth();

  // Apply initial theme to DOM (no useEffect needed)
  const savedTheme = localStorage.getItem('theme');
  if (
    savedTheme &&
    (savedTheme === 'light' || savedTheme === 'dark' || savedTheme === 'system')
  ) {
    setTheme(savedTheme);
  } else {
    // Apply current theme to DOM
    setTheme(theme);
  }
};

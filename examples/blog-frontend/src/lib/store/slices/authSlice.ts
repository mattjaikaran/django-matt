import { authApi } from '@/api/auth';
import { config } from '@/config';
import type {
  AuthState,
  AuthTokens,
  LoginCredentials,
  MagicLinkRequest,
  RegisterCredentials,
  User,
} from '@/types';
import { StateCreator } from 'zustand';

export interface AuthSlice extends AuthState {
  // Actions
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  magicLink: (request: MagicLinkRequest) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  setUser: (user: User) => void;
  setTokens: (tokens: AuthTokens) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
  initializeAuth: () => void;
}

const initialState: AuthState = {
  user: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
};

const { tokenKey, refreshTokenKey } = config.auth;

export const createAuthSlice: StateCreator<AuthSlice> = (set, get) => ({
  ...initialState,

  login: async (credentials: LoginCredentials) => {
    set({ isLoading: true, error: null });

    try {
      const { user, tokens } = await authApi.login(credentials);

      localStorage.setItem(tokenKey, tokens.accessToken);
      localStorage.setItem(refreshTokenKey, tokens.refreshToken);
      localStorage.setItem('user', JSON.stringify(user));

      set({
        user,
        tokens,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Login failed',
      });
    }
  },

  register: async (credentials: RegisterCredentials) => {
    set({ isLoading: true, error: null });

    try {
      const { user, tokens } = await authApi.register(credentials);

      localStorage.setItem(tokenKey, tokens.accessToken);
      localStorage.setItem(refreshTokenKey, tokens.refreshToken);
      localStorage.setItem('user', JSON.stringify(user));

      set({
        user,
        tokens,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Registration failed',
      });
    }
  },

  magicLink: async (request: MagicLinkRequest) => {
    set({ isLoading: true, error: null });

    try {
      await authApi.magicLink(request);

      set({
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Magic link failed',
      });
    }
  },

  logout: () => {
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(refreshTokenKey);
    localStorage.removeItem('user');

    set({
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  },

  refreshToken: async () => {
    const { tokens } = get();
    if (!tokens?.refreshToken) return;

    set({ isLoading: true });

    try {
      const { accessToken } = await authApi.refreshToken(tokens.refreshToken);

      localStorage.setItem(tokenKey, accessToken);

      set({
        tokens: { ...tokens, accessToken },
        isLoading: false,
      });
    } catch {
      get().logout();
    }
  },

  setUser: (user: User) => {
    set({ user });
    localStorage.setItem('user', JSON.stringify(user));
  },

  setTokens: (tokens: AuthTokens) => {
    set({ tokens });
    localStorage.setItem(tokenKey, tokens.accessToken);
    localStorage.setItem(refreshTokenKey, tokens.refreshToken);
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  setError: (error: string | null) => {
    set({ error });
  },

  clearError: () => {
    set({ error: null });
  },

  initializeAuth: () => {
    try {
      const token = localStorage.getItem(tokenKey);
      const refreshToken = localStorage.getItem(refreshTokenKey);
      const userStr = localStorage.getItem('user');

      if (token && refreshToken && userStr) {
        const user = JSON.parse(userStr);
        set({
          user,
          tokens: { accessToken: token, refreshToken },
          isAuthenticated: true,
        });
      }
    } catch (error) {
      console.error('Failed to initialize auth:', error);
      localStorage.removeItem(tokenKey);
      localStorage.removeItem(refreshTokenKey);
      localStorage.removeItem('user');
    }
  },
});

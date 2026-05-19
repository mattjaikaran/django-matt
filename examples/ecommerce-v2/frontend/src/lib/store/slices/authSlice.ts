import { authApi } from '@/api/auth';
import { config } from '@/config';
import type { AuthTokens, LoginCredentials, RegisterCredentials, User } from '@/types';
import { StateCreator } from 'zustand';

export interface AuthSlice {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  initializeAuth: () => void;
}

const { tokenKey, refreshTokenKey } = config.auth;

export const createAuthSlice: StateCreator<AuthSlice> = (set) => ({
  user: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: false,

  login: async (credentials) => {
    set({ isLoading: true });
    try {
      const { user, tokens } = await authApi.login(credentials);
      localStorage.setItem(tokenKey, tokens.accessToken);
      localStorage.setItem(refreshTokenKey, tokens.refreshToken);
      localStorage.setItem('user', JSON.stringify(user));
      set({ user, tokens, isAuthenticated: true, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  register: async (credentials) => {
    set({ isLoading: true });
    try {
      const { user, tokens } = await authApi.register(credentials);
      if (tokens.accessToken) {
        localStorage.setItem(tokenKey, tokens.accessToken);
        localStorage.setItem(refreshTokenKey, tokens.refreshToken);
      }
      localStorage.setItem('user', JSON.stringify(user));
      set({ user, tokens: tokens.accessToken ? tokens : null, isAuthenticated: !!tokens.accessToken, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: () => {
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(refreshTokenKey);
    localStorage.removeItem('user');
    set({ user: null, tokens: null, isAuthenticated: false });
  },

  setUser: (user) => set({ user }),

  initializeAuth: () => {
    const token = localStorage.getItem(tokenKey);
    const userStr = localStorage.getItem('user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as User;
        set({ user, isAuthenticated: true });
      } catch {
        localStorage.removeItem('user');
      }
    }
  },
});

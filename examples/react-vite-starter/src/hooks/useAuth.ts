import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '@/lib/api';

export interface User {
  id: string;
  email: string;
  username: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      login: async (email, password) => {
        const { data } = await api.post('/auth/login', { email, password });
        localStorage.setItem('access_token', data.access);
        set({ user: data.user, token: data.access });
      },
      register: async (email, username, password) => {
        const { data } = await api.post('/auth/register', { email, username, password });
        localStorage.setItem('access_token', data.access);
        set({ user: data.user, token: data.access });
      },
      logout: () => {
        localStorage.removeItem('access_token');
        set({ user: null, token: null });
      },
    }),
    { name: 'auth-storage', partialize: (state) => ({ user: state.user, token: state.token }) }
  )
);

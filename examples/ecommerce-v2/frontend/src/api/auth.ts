import type { AuthResponse, AuthTokens, LoginCredentials, RegisterCredentials, User } from '@/types';
import { api } from './client';

export const authApi = {
  register: async (data: RegisterCredentials): Promise<AuthResponse> => {
    const res = await api.post<User>('/auth/register', data);
    return { user: res.data, tokens: { accessToken: '', refreshToken: '', tokenType: 'bearer' } };
  },

  login: async (data: LoginCredentials): Promise<AuthResponse> => {
    const res = await api.post<AuthTokens>('/auth/login', data);
    const tokens = res.data;
    const profileRes = await api.get<User>('/auth/me');
    return { user: profileRes.data, tokens };
  },

  refresh: async (refreshToken: string): Promise<AuthTokens> => {
    const res = await api.post<AuthTokens>('/auth/refresh', { refreshToken });
    return res.data;
  },

  getProfile: async (): Promise<User> => {
    const res = await api.get<User>('/auth/me');
    return res.data;
  },

  updateProfile: async (data: Partial<User>): Promise<User> => {
    const res = await api.patch<User>('/auth/me', data);
    return res.data;
  },

  changePassword: async (data: { currentPassword: string; newPassword: string }): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>('/auth/change-password', data);
    return res.data;
  },

  logout: async (): Promise<void> => {},
};

import { apiClient, handleApiResponse } from '@/lib/api';
import type {
  AuthResponse,
  DjangoAuthResponse,
  LoginCredentials,
  MagicLinkRequest,
  RegisterCredentials,
  User,
} from '@/types';
import { normalizeAuthResponse } from '@/types/auth';

/**
 * Determine auth endpoint paths based on backend configuration
 * Django Ninja JWT typically uses /token/pair for login
 */
const getAuthPaths = () => {
  return {
    login: '/auth/login',
    register: '/auth/signup',
    refresh: '/auth/token/refresh',
    profile: '/auth/me',
    magicLink: '/auth/passwordless/login/request',
    verifyMagicLink: '/auth/passwordless/login/verify',
    logout: '/auth/logout',
    changePassword: '/auth/change-password',
    requestPasswordReset: '/otp/password-reset/request',
    resetPassword: '/otp/password-reset/confirm',
  };
};

export const authApi = {
  /**
   * Login with email and password
   * Handles both standard and Django Ninja JWT formats
   */
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const paths = getAuthPaths();

    const response = await apiClient.post<AuthResponse | DjangoAuthResponse>(
      paths.login,
      { email: credentials.email, password: credentials.password }
    );
    const data = handleApiResponse(response);
    return normalizeAuthResponse(data);
  },

  /**
   * Register new user
   * Converts to Django snake_case format when needed
   */
  register: async (credentials: RegisterCredentials): Promise<AuthResponse> => {
    const paths = getAuthPaths();

    const response = await apiClient.post<AuthResponse | DjangoAuthResponse>(
      paths.register,
      {
        email: credentials.email,
        password: credentials.password,
        firstName: credentials.firstName,
        lastName: credentials.lastName,
        passwordConfirm: credentials.confirmPassword,
      }
    );
    const data = handleApiResponse(response);
    return normalizeAuthResponse(data);
  },

  /**
   * Send magic link for passwordless login
   */
  magicLink: async (
    request: MagicLinkRequest
  ): Promise<{ message: string }> => {
    const paths = getAuthPaths();
    const response = await apiClient.post<{ message: string }>(
      paths.magicLink,
      request
    );
    return handleApiResponse(response);
  },

  /**
   * Verify magic link token
   */
  verifyMagicLink: async (token: string): Promise<AuthResponse> => {
    const paths = getAuthPaths();
    const response = await apiClient.post<AuthResponse | DjangoAuthResponse>(
      paths.verifyMagicLink,
      { token }
    );
    const data = handleApiResponse(response);
    return normalizeAuthResponse(data);
  },

  /**
   * Refresh access token
   * Handles both standard and Django Ninja JWT formats
   */
  refreshToken: async (
    refreshToken: string
  ): Promise<{ accessToken: string }> => {
    const paths = getAuthPaths();

    const response = await apiClient.post<
      { accessToken: string } | { token: string }
    >(paths.refresh, { refresh: refreshToken });
    const data = handleApiResponse(response);

    if ('token' in data) {
      return { accessToken: data.token };
    }
    return data;
  },

  /**
   * Logout and invalidate tokens
   */
  logout: async (): Promise<{ message: string }> => {
    const paths = getAuthPaths();
    try {
      const response = await apiClient.post<{ message: string }>(paths.logout);
      return handleApiResponse(response);
    } catch {
      // Many Django setups don't have a logout endpoint - just return success
      return { message: 'Logged out successfully' };
    }
  },

  /**
   * Get current user profile
   * Normalizes Django snake_case response to camelCase
   */
  getProfile: async (): Promise<User> => {
    const paths = getAuthPaths();
    const response = await apiClient.get<User>(paths.profile);
    return handleApiResponse(response);
  },

  /**
   * Update user profile
   */
  updateProfile: async (updates: Partial<User>): Promise<User> => {
    const paths = getAuthPaths();

    const response = await apiClient.patch<User>(
      paths.profile,
      {
        firstName: updates.firstName,
        lastName: updates.lastName,
        email: updates.email,
      }
    );
    return handleApiResponse(response);
  },

  /**
   * Change password
   */
  changePassword: async (data: {
    currentPassword: string;
    newPassword: string;
  }): Promise<{ message: string }> => {
    const paths = getAuthPaths();

    const response = await apiClient.post<{ message: string }>(
      paths.changePassword,
      {
        oldPassword: data.currentPassword,
        newPassword: data.newPassword,
      }
    );
    return handleApiResponse(response);
  },

  /**
   * Request password reset email
   */
  requestPasswordReset: async (email: string): Promise<{ message: string }> => {
    const paths = getAuthPaths();
    const response = await apiClient.post<{ message: string }>(
      paths.requestPasswordReset,
      { email }
    );
    return handleApiResponse(response);
  },

  /**
   * Reset password with token
   */
  resetPassword: async (data: {
    token: string;
    newPassword: string;
  }): Promise<{ message: string }> => {
    const paths = getAuthPaths();

    const response = await apiClient.post<{ message: string }>(
      paths.resetPassword,
      { token: data.token, newPassword: data.newPassword }
    );
    return handleApiResponse(response);
  },
};

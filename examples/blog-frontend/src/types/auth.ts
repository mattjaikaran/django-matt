/**
 * Authentication-related types
 * Compatible with Django Ninja JWT
 */

import type { User } from './user';

/**
 * Auth tokens - supports both camelCase and snake_case formats
 */
export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

/**
 * Django Ninja JWT token format
 * Backend TokenSchema returns { token, refresh, user }
 */
export interface DjangoJWTTokens {
  token: string;
  refresh: string;
}

/**
 * Normalize tokens from either format
 */
export function normalizeTokens(
  tokens: AuthTokens | DjangoJWTTokens
): AuthTokens {
  if ('token' in tokens) {
    return {
      accessToken: tokens.token,
      refreshToken: tokens.refresh,
    };
  }
  return tokens;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

/**
 * Django Ninja JWT uses 'username' by default, but email is common
 */
export interface DjangoLoginCredentials {
  username?: string;
  email?: string;
  password: string;
}

export interface RegisterCredentials extends LoginCredentials {
  firstName: string;
  lastName: string;
  confirmPassword: string;
}

/**
 * Django Ninja registration format (snake_case)
 */
export interface DjangoRegisterCredentials {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  password_confirm?: string;
}

/**
 * Convert register credentials to Django format
 */
export function toDjangoRegisterCredentials(
  credentials: RegisterCredentials
): DjangoRegisterCredentials {
  return {
    email: credentials.email,
    password: credentials.password,
    first_name: credentials.firstName,
    last_name: credentials.lastName,
    password_confirm: credentials.confirmPassword,
  };
}

export interface MagicLinkRequest {
  email: string;
}

/**
 * Standard auth response with user and tokens
 */
export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

/**
 * Django Ninja JWT auth response format
 * Backend returns { token, refresh, user } from TokenSchema
 */
export interface DjangoAuthResponse {
  token: string;
  refresh: string;
  user?: DjangoUserResponse;
}

/**
 * Django user response format (snake_case)
 */
export interface DjangoUserResponse {
  id: number | string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  date_joined?: string;
  last_login?: string;
}

/**
 * Normalize Django user response to User format
 */
export function normalizeUser(djangoUser: DjangoUserResponse): User {
  return {
    id: String(djangoUser.id),
    email: djangoUser.email,
    firstName: djangoUser.first_name,
    lastName: djangoUser.last_name,
    isActive: djangoUser.is_active,
    lastLogin: djangoUser.last_login,
    createdAt: djangoUser.date_joined || new Date().toISOString(),
    updatedAt: djangoUser.last_login || new Date().toISOString(),
  };
}

/**
 * Normalize auth response from Django Ninja JWT format
 */
export function normalizeAuthResponse(
  response: DjangoAuthResponse | AuthResponse
): AuthResponse {
  // Already in normalized format
  if ('tokens' in response && 'user' in response) {
    return response;
  }

  // Django format - convert
  const djangoResponse = response as DjangoAuthResponse;
  return {
    tokens: {
      accessToken: djangoResponse.token,
      refreshToken: djangoResponse.refresh,
    },
    user: djangoResponse.user
      ? normalizeUser(djangoResponse.user)
      : ({} as User), // User will be fetched separately if not included
  };
}

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

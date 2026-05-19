/**
 * Django integration utilities for SPA mode
 */

import { config, isDjangoSPA } from '@/config';

/**
 * Django user data type
 */
export interface DjangoUser {
  id: number | string;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
}

/**
 * Django settings type
 */
export interface DjangoSettings {
  DEBUG?: boolean;
  LANGUAGE_CODE?: string;
  TIME_ZONE?: string;
  [key: string]: unknown;
}

/**
 * Django message type
 */
export interface DjangoMessage {
  level: string;
  message: string;
  tags: string;
}

// Extend Window interface for Django globals
declare global {
  interface Window {
    __DJANGO_USER__?: DjangoUser;
    __DJANGO_SETTINGS__?: DjangoSettings;
    __DJANGO_URLS__?: Record<string, string>;
    __DJANGO_MESSAGES__?: DjangoMessage[];
  }
}

/**
 * Get CSRF token from Django
 */
export function getCSRFToken(): string | null {
  if (!isDjangoSPA()) return null;

  // Try to get from meta tag first
  const metaTag = document.querySelector(
    'meta[name="csrf-token"]'
  ) as HTMLMetaElement;
  if (metaTag) {
    return metaTag.content;
  }

  // Try to get from cookie
  const cookieName = config.django?.csrfTokenName || 'csrftoken';
  const cookies = document.cookie.split(';');

  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === cookieName) {
      return decodeURIComponent(value);
    }
  }

  return null;
}

/**
 * Get Django user data from window object or DOM
 */
export function getDjangoUser(): DjangoUser | null {
  if (!isDjangoSPA()) return null;

  // Check if Django user data is available in window
  const windowUser = window.__DJANGO_USER__;
  if (windowUser) {
    return windowUser;
  }

  // Try to get from JSON script tag
  const userScript = document.getElementById('django-user-data');
  if (userScript) {
    try {
      return JSON.parse(userScript.textContent || '{}') as DjangoUser;
    } catch (error) {
      console.warn('Failed to parse Django user data:', error);
    }
  }

  return null;
}

/**
 * Get Django settings/config from window object
 */
export function getDjangoSettings(): DjangoSettings {
  if (!isDjangoSPA()) return {};

  return window.__DJANGO_SETTINGS__ || {};
}

/**
 * Build URL with Django static/media prefix
 */
export function buildDjangoUrl(
  path: string,
  type: 'static' | 'media' = 'static'
): string {
  if (!isDjangoSPA()) return path;

  const prefix =
    type === 'static'
      ? config.django?.staticUrl || '/static/'
      : config.django?.mediaUrl || '/media/';

  return `${prefix.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
}

/**
 * Initialize Django SPA integration
 */
export function initializeDjangoSPA(): void {
  if (!isDjangoSPA()) return;

  // Warm CSRF token and user data caches
  getCSRFToken();
  getDjangoUser();

  // Set up Django-specific error handling
  window.addEventListener('unhandledrejection', event => {
    if (event.reason?.response?.status === 403) {
      console.warn('🔒 CSRF token may be invalid, attempting to refresh...');
      // Could implement CSRF token refresh logic here
    }
  });
}

/**
 * Form data value types
 */
type FormDataValue = string | number | boolean | File | (string | number)[];

/**
 * Django form helpers
 */
export class DjangoFormHelper {
  static addCSRFToken(formData: FormData): FormData {
    if (!isDjangoSPA()) return formData;

    const csrfToken = getCSRFToken();
    if (csrfToken) {
      formData.append('csrfmiddlewaretoken', csrfToken);
    }

    return formData;
  }

  static createFormData(data: Record<string, FormDataValue>): FormData {
    const formData = new FormData();

    Object.entries(data).forEach(([key, value]) => {
      if (value instanceof File) {
        formData.append(key, value);
      } else if (Array.isArray(value)) {
        value.forEach((item, index) => {
          formData.append(`${key}[${index}]`, String(item));
        });
      } else if (value !== null && value !== undefined) {
        formData.append(key, String(value));
      }
    });

    return this.addCSRFToken(formData);
  }
}

/**
 * Django URL helpers
 */
export class DjangoUrlHelper {
  static reverse(
    viewName: string,
    args: Record<string, string | number> = {}
  ): string {
    if (!isDjangoSPA()) return viewName;

    // Check if Django URL reverse function is available
    const djangoUrls = window.__DJANGO_URLS__;
    if (djangoUrls && djangoUrls[viewName]) {
      let url = djangoUrls[viewName];

      // Replace URL parameters
      Object.entries(args).forEach(([key, value]) => {
        url = url.replace(new RegExp(`<${key}>`, 'g'), String(value));
      });

      return url;
    }

    return viewName;
  }

  static buildApiUrl(endpoint: string): string {
    const apiPrefix = config.django?.apiPrefix || '/api';
    return `${apiPrefix}/${endpoint.replace(/^\//, '')}`;
  }
}

/**
 * Django message framework integration
 */
export class DjangoMessages {
  static getMessages(): DjangoMessage[] {
    if (!isDjangoSPA()) return [];

    return window.__DJANGO_MESSAGES__ || [];
  }

  static clearMessages(): void {
    if (typeof window !== 'undefined') {
      window.__DJANGO_MESSAGES__ = [];
    }
  }
}

// Auto-initialize if in Django SPA mode
if (typeof window !== 'undefined') {
  // Wait for DOM to be ready
  const initIfDjango = () => {
    if (isDjangoSPA()) {
      initializeDjangoSPA();
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initIfDjango);
  } else {
    initIfDjango();
  }
}

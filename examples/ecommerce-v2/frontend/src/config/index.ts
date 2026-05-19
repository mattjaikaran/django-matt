const getEnvVar = (key: string, defaultValue = ''): string =>
  import.meta.env[key] || defaultValue;

export const config = {
  api: {
    baseUrl: getEnvVar('VITE_API_BASE_URL', 'http://localhost:8000/api'),
    timeout: 10000,
  },
  auth: {
    tokenKey: 'access_token',
    refreshTokenKey: 'refresh_token',
  },
  stripe: {
    publishableKey: getEnvVar('VITE_STRIPE_PUBLISHABLE_KEY', ''),
  },
} as const;

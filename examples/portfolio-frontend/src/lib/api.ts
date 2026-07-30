import axios from 'axios';

const TOKEN_KEY = import.meta.env.VITE_AUTH_TOKEN_KEY || 'access_token';
const REFRESH_KEY = import.meta.env.VITE_AUTH_REFRESH_TOKEN_KEY || 'refresh_token';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Track refresh promise to avoid concurrent refresh calls
let refreshPromise: Promise<string | null> | null = null;

/** Attach access token to every outgoing request */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** On 401, attempt token refresh once before failing */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only handle 401s that haven't been retried yet
    if (
      error.response?.status !== 401 ||
      originalRequest._retry ||
      !localStorage.getItem(REFRESH_KEY)
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      // Share a single refresh promise across concurrent 401s
      if (!refreshPromise) {
        refreshPromise = (async () => {
          const refreshToken = localStorage.getItem(REFRESH_KEY);
          if (!refreshToken) return null;

          const { data } = await axios.post(
            `${import.meta.env.VITE_API_URL || '/api'}/auth/refresh`,
            { refresh: refreshToken }
          );

          // TokenSchema returns { access_token, refresh_token }
          const newAccess = data.access_token || data.access;
          const newRefresh = data.refresh_token || data.refresh;

          if (newAccess) {
            localStorage.setItem(TOKEN_KEY, newAccess);
            if (newRefresh) localStorage.setItem(REFRESH_KEY, newRefresh);
            return newAccess;
          }
          return null;
        })();
      }

      const accessToken = await refreshPromise;

      if (accessToken) {
        originalRequest.headers.Authorization = `Bearer ${accessToken}`;
        return api(originalRequest);
      }
    } catch {
      // Refresh failed — clear tokens, will redirect to login
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
    } finally {
      refreshPromise = null;
    }

    return Promise.reject(error);
  }
);

/** Clear auth tokens (for logout) */
export function clearAuthTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

/** Store auth tokens */
export function setAuthTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export default api;

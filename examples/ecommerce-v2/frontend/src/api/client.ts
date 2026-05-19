import { config } from '@/config';
import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';

function snakeToCamelStr(s: string): string {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function camelToSnakeStr(s: string): string {
  return s.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function snakeToCamel(data: any): any {
  if (Array.isArray(data)) return data.map(snakeToCamel);
  if (data !== null && typeof data === 'object' && !(data instanceof File)) {
    return Object.fromEntries(
      Object.entries(data).map(([k, v]) => [snakeToCamelStr(k), snakeToCamel(v)])
    );
  }
  return data;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function camelToSnake(data: any): any {
  if (Array.isArray(data)) return data.map(camelToSnake);
  if (data !== null && typeof data === 'object' && !(data instanceof File)) {
    return Object.fromEntries(
      Object.entries(data).map(([k, v]) => [camelToSnakeStr(k), camelToSnake(v)])
    );
  }
  return data;
}

interface ExtendedAxiosRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

interface DjangoErrorResponse {
  detail?: string | { msg: string; loc: string[] }[];
  message?: string;
  code?: string;
}

const createApiInstance = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: config.api.baseUrl,
    timeout: config.api.timeout,
    headers: { 'Content-Type': 'application/json' },
  });

  instance.interceptors.request.use((requestConfig: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(config.auth.tokenKey);
    if (token) requestConfig.headers.Authorization = `Bearer ${token}`;

    if (requestConfig.data && typeof requestConfig.data === 'object') {
      requestConfig.data = camelToSnake(requestConfig.data);
    }
    return requestConfig;
  });

  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      if (response.data) response.data = snakeToCamel(response.data);
      return response;
    },
    async (error: AxiosError<DjangoErrorResponse>) => {
      const originalRequest = error.config as ExtendedAxiosRequestConfig | undefined;

      if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
        originalRequest._retry = true;
        try {
          const refreshToken = localStorage.getItem(config.auth.refreshTokenKey);
          if (refreshToken) {
            const response = await instance.post<{ accessToken: string; refreshToken: string }>(
              '/auth/refresh',
              { refreshToken }
            );
            const { accessToken } = response.data;
            localStorage.setItem(config.auth.tokenKey, accessToken);
            originalRequest.headers.Authorization = `Bearer ${accessToken}`;
            return instance(originalRequest);
          }
        } catch {
          localStorage.removeItem(config.auth.tokenKey);
          localStorage.removeItem(config.auth.refreshTokenKey);
          localStorage.removeItem('user');
          window.location.href = '/auth/login';
        }
      }

      let errorMessage = 'An error occurred';
      const responseData = error.response?.data;
      if (responseData) {
        if (typeof responseData.detail === 'string') errorMessage = responseData.detail;
        else if (Array.isArray(responseData.detail)) errorMessage = responseData.detail.map(d => d.msg).join(', ');
        else if (responseData.message) errorMessage = responseData.message;
      } else if (error.message) {
        errorMessage = error.message;
      }

      return Promise.reject(new Error(errorMessage));
    }
  );

  return instance;
};

export const api = createApiInstance();

export const apiClient = {
  get: <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    api.get(url, config),
  post: <T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    api.post(url, data, config),
  put: <T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    api.put(url, data, config),
  patch: <T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    api.patch(url, data, config),
  delete: <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    api.delete(url, config),
};

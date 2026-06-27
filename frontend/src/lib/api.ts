import axios from 'axios';
import {
  getToken,
  clearToken,
  getRefreshToken,
  saveToken,
  saveRefreshToken,
  clearRefreshToken,
  clearAllTenantTokens,
  decodeToken,
  isTokenExpired,
  ACTIVE_TENANT_KEY,
} from './auth';

const IMPERSONATION_TOKEN_KEY = 'zealsync_impersonation_token';

export class RateLimitedError extends Error {
  constructor(message = 'Too many attempts, try again shortly') {
    super(message);
    this.name = 'RateLimitedError';
  }
}

/**
 * Impersonation sessions use sessionStorage (per-tab, cleared on tab close).
 * Regular tenant sessions use tenant-scoped localStorage keys.
 */
function getRequestToken(): string | null {
  const impersonationToken = sessionStorage.getItem(IMPERSONATION_TOKEN_KEY);
  if (impersonationToken) {
    return impersonationToken;
  }
  const token = getToken();
  if (token && isTokenExpired(token)) {
    return null;
  }
  return token;
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = getRequestToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 429) {
      return Promise.reject(new RateLimitedError());
    }

    // Impersonation tabs do not refresh — redirect to login on expiry
    if (sessionStorage.getItem(IMPERSONATION_TOKEN_KEY)) {
      if (error.response?.status === 401) {
        sessionStorage.removeItem(IMPERSONATION_TOKEN_KEY);
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearToken();
        clearRefreshToken();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }

      try {
        const baseURL = api.defaults.baseURL || import.meta.env.VITE_API_BASE_URL;
        const response = await axios.post(`${baseURL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token: newRefreshToken } = response.data;
        const decoded = decodeToken(access_token);
        const tenantId = decoded?.tenant_id;
        if (tenantId) {
          saveToken(access_token, tenantId);
          saveRefreshToken(newRefreshToken, tenantId);
        }

        api.defaults.headers.common.Authorization = `Bearer ${access_token}`;
        originalRequest.headers.Authorization = `Bearer ${access_token}`;

        processQueue(null, access_token);
        isRefreshing = false;

        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;
        clearAllTenantTokens();
        localStorage.removeItem(ACTIVE_TENANT_KEY);
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

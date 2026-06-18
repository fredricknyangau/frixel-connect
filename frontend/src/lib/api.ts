import axios from 'axios';
import { getToken, clearToken, getRefreshToken, saveToken, saveRefreshToken, clearRefreshToken } from './auth';

export class RateLimitedError extends Error {
  constructor(message = 'Too many attempts, try again shortly') {
    super(message);
    this.name = 'RateLimitedError';
  }
}

/**
 * Configure our Axios instance.
 * The baseURL is loaded from our environment variables.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * REQUEST INTERCEPTOR
 * Runs before every request automatically.
 */
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// CONCURRENCY QUEUE CONTROL FOR REFRESH TOKENS
// If multiple requests get a 401 simultaneously, we hold a single in-flight promise.
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

/**
 * RESPONSE INTERCEPTOR
 * Runs when the response returns.
 * If we get a 401 Unauthorized, we attempt to silently refresh the tokens.
 * Handles 429 specifically with a RateLimitedError.
 */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle Rate Limiting (429)
    if (error.response?.status === 429) {
      return Promise.reject(new RateLimitedError());
    }

    // Handle 401 Unauthorized and prevent infinite loops via _retry flag
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
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
        saveToken(access_token);
        saveRefreshToken(newRefreshToken);

        api.defaults.headers.common.Authorization = `Bearer ${access_token}`;
        originalRequest.headers.Authorization = `Bearer ${access_token}`;

        processQueue(null, access_token);
        isRefreshing = false;

        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;
        clearToken();
        clearRefreshToken();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

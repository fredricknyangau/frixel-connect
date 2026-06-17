import axios from 'axios';
import { getToken, clearToken } from './auth';

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
 * Backend analogy: this is like the `require_role` dependency in FastAPI 
 * that runs before every protected endpoint to extract and validate the token.
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

/**
 * RESPONSE INTERCEPTOR
 * Runs when the response returns.
 * If we get a 401 Unauthorized, we clear the token and redirect to login.
 * Other errors are re-thrown so TanStack Query can catch them.
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token is invalid or expired
      clearToken();
      // We must force redirect. Since we are outside the React Router tree,
      // window.location.href is the simplest guaranteed way.
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

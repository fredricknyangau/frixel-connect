/**
 * superAdminApi.ts
 * A dedicated Axios instance for super admin API calls.
 *
 * WHY A SEPARATE INSTANCE?
 * ─────────────────────────
 * The tenant portal's `api` instance reads tenant-scoped localStorage keys
 * (zealsync_token_{tenant_id}). If both portals shared one Axios instance:
 *   1. A super admin who opens an impersonation tab would contaminate tokens.
 *   2. A 401 from a tenant-scoped endpoint would log out the super admin.
 *   3. Token refresh logic in `api.ts` would fire for super admin 401s incorrectly.
 *
 * IMPERSONATION ISOLATION:
 * Impersonation tokens live in sessionStorage (zealsync_impersonation_token), read
 * by the tenant portal's `api.ts` when that tab is opened from the super admin UI.
 * sessionStorage is per-tab and cleared on tab close — never written to localStorage.
 * The super admin's own JWT stays in localStorage under zealsync_super_admin_token.
 */

import axios from 'axios';

// ─── Token Storage Key ────────────────────────────────────────────────────────

/**
 * Intentionally different from the tenant portal's 'zealsync_access_token'.
 * This prevents the tenant Axios interceptor from accidentally reading or
 * clearing the super admin token.
 */
const SUPER_ADMIN_TOKEN_KEY = 'zealsync_super_admin_token';

export function getSuperAdminToken(): string | null {
  return localStorage.getItem(SUPER_ADMIN_TOKEN_KEY);
}

export function saveSuperAdminToken(token: string): void {
  localStorage.setItem(SUPER_ADMIN_TOKEN_KEY, token);
}

export function clearSuperAdminToken(): void {
  localStorage.removeItem(SUPER_ADMIN_TOKEN_KEY);
}

// ─── Axios Instance ───────────────────────────────────────────────────────────

/**
 * Uses the same backend base URL as the tenant portal but without the /api/v1 suffix,
 * since the backend super admin endpoints are configured directly at /super-admin/*.
 */
const getBaseURL = () => {
  const url = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
  return url.replace(/\/api\/v1\/?$/, '');
};

export const superAdminApi = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Request Interceptor ──────────────────────────────────────────────────────

/**
 * Attaches the super admin Bearer token to every outgoing request.
 * The pre-auth token (Step 1 of login) is NOT stored here-it lives
 * in memory inside SuperAdminAuthContext and is passed explicitly
 * to the TOTP verify endpoint.
 */
superAdminApi.interceptors.request.use(
  (config) => {
    const token = getSuperAdminToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ─── Response Interceptor ─────────────────────────────────────────────────────

/**
 * On 401 Unauthorized:
 *   1. Clear the super admin token from localStorage.
 *   2. Redirect to /super-admin/login (NOT /login-that's the tenant portal).
 *
 * There is no token refresh for super admin sessions by design:
 * the access token lifetime is 15 minutes. When it expires the super admin
 * must re-authenticate (email + password + TOTP). The shorter window reduces
 * the blast radius of a stolen token to 15 minutes.
 */
superAdminApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearSuperAdminToken();
      // Only redirect if not already on the login page to avoid redirect loops.
      if (window.location.pathname !== '/super-admin/login') {
        window.location.href = '/super-admin/login';
      }
    }
    return Promise.reject(error);
  }
);

import { DecodedToken, UserRole } from '../types/auth';

const TOKEN_KEY = (tenantId: string) => `Frixel Connect_token_${tenantId}`;
const REFRESH_KEY = (tenantId: string) => `Frixel Connect_refresh_${tenantId}`;
export const ACTIVE_TENANT_KEY = 'Frixel Connect_active_tenant';

// SECURITY: localStorage is vulnerable to XSS. An injected script can read tokens.
// v2: switch to httpOnly cookies set by the backend.
//
// SECURITY: localStorage is shared across all tabs of the same origin.
// Writing ACTIVE_TENANT_KEY on login means a second tab opening after login
// reads the new tenant's token. v2: use sessionStorage per-tab for full T6 isolation.
// Super admin impersonation uses sessionStorage (see api.ts) — correct for that flow.

export function saveToken(token: string, tenantId: string): void {
  localStorage.setItem(TOKEN_KEY(tenantId), token);
  localStorage.setItem(ACTIVE_TENANT_KEY, tenantId);
}

export function getToken(): string | null {
  const tenantId = localStorage.getItem(ACTIVE_TENANT_KEY);
  if (!tenantId) return null;
  return localStorage.getItem(TOKEN_KEY(tenantId));
}

export function getTokenForTenant(tenantId: string): string | null {
  return localStorage.getItem(TOKEN_KEY(tenantId));
}

export function clearToken(): void {
  const tenantId = localStorage.getItem(ACTIVE_TENANT_KEY);
  if (tenantId) {
    localStorage.removeItem(TOKEN_KEY(tenantId));
    localStorage.removeItem(REFRESH_KEY(tenantId));
  }
  localStorage.removeItem(ACTIVE_TENANT_KEY);
}

export function clearAllTenantTokens(): void {
  Object.keys(localStorage)
    .filter((k) => k.startsWith('Frixel Connect_token_'))
    .forEach((k) => localStorage.removeItem(k));
  Object.keys(localStorage)
    .filter((k) => k.startsWith('Frixel Connect_refresh_'))
    .forEach((k) => localStorage.removeItem(k));
  localStorage.removeItem(ACTIVE_TENANT_KEY);
}

export function saveRefreshToken(token: string, tenantId: string): void {
  localStorage.setItem(REFRESH_KEY(tenantId), token);
}

export function getRefreshToken(): string | null {
  const tenantId = localStorage.getItem(ACTIVE_TENANT_KEY);
  if (!tenantId) return null;
  return localStorage.getItem(REFRESH_KEY(tenantId));
}

export function clearRefreshToken(): void {
  const tenantId = localStorage.getItem(ACTIVE_TENANT_KEY);
  if (tenantId) {
    localStorage.removeItem(REFRESH_KEY(tenantId));
  }
}

export function decodeToken(token: string): DecodedToken | null {
  try {
    const base64Url = token.split('.')[1];
    if (!base64Url) return null;
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window.atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload) as DecodedToken;
  } catch (error) {
    console.error('Failed to decode token', error);
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const decoded = decodeToken(token);
  if (!decoded) return true;
  return decoded.exp < Date.now() / 1000;
}

export function getUserRole(): UserRole | null {
  const token = getToken();
  if (!token) return null;
  const decoded = decodeToken(token);
  return decoded?.role || null;
}

export function getUserId(): string | null {
  const token = getToken();
  if (!token) return null;
  const decoded = decodeToken(token);
  return decoded?.sub || null;
}

import { DecodedToken, UserRole } from '../types/auth';

const TOKEN_KEY = 'zealsync_access_token';
const REFRESH_TOKEN_KEY = 'zealsync_refresh_token';

// SECURITY: localStorage is vulnerable to XSS. An injected
// script can read this token. In v1 we accept this risk for
// simplicity. In v2, switch to httpOnly cookies set by the backend
// so JavaScript cannot access the token at all. 
// See v2 cookie migration plan.
export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

// SECURITY: see v2 cookie migration plan
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

// SECURITY: see v2 cookie migration plan
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function saveRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearRefreshToken(): void {
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/**
 * Decodes the JWT payload without needing an external library.
 * Explain JWT structure: header.payload.signature
 * We read only the payload (the middle part).
 */
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
  // exp is in seconds, Date.now() is in milliseconds
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

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { getSuperAdminToken, saveSuperAdminToken, clearSuperAdminToken } from '../lib/superAdminApi';

interface SuperAdminUser {
  id: string;
  full_name: string;
}

export type SuperAdminLoginStep = 'idle' | 'password' | 'totp_setup' | 'totp_verify' | 'done';

interface SuperAdminAuthContextType {
  superAdmin: SuperAdminUser | null;
  isAuthenticated: boolean;
  loginStep: SuperAdminLoginStep;
  preAuthToken: string | null;
  isLoading: boolean;
  setLoginStep: (step: SuperAdminLoginStep) => void;
  setPreAuthToken: (token: string | null) => void;
  login: (token: string, profile: { id: string; full_name: string }) => void;
  logout: () => void;
}

const SuperAdminAuthContext = createContext<SuperAdminAuthContextType | undefined>(undefined);

// CACHE ISOLATION: The impersonation tab is a separate browser tab.
// TanStack Query's in-memory cache is per-JavaScript-process — the impersonation
// tab starts with an empty cache and its data never contaminates the super admin's
// main session cache. No cache clearing is needed on impersonation start or end.

// Helper to decode JWT payload safely
function decodeSuperAdminToken(token: string): { sub: string; full_name?: string; exp: number } | null {
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
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('Failed to decode super admin token', error);
    return null;
  }
}

// Helper to check if token is expired
function isTokenExpired(token: string): boolean {
  const decoded = decodeSuperAdminToken(token);
  if (!decoded) return true;
  // exp is in seconds, Date.now() is in milliseconds
  return decoded.exp < Date.now() / 1000;
}

export function SuperAdminAuthProvider({ children }: { children: ReactNode }) {
  const [superAdmin, setSuperAdmin] = useState<SuperAdminUser | null>(null);
  const [loginStep, setLoginStep] = useState<SuperAdminLoginStep>('idle');
  const [preAuthToken, setPreAuthToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getSuperAdminToken();
    if (token) {
      if (!isTokenExpired(token)) {
        const decoded = decodeSuperAdminToken(token);
        if (decoded) {
          // Look for name claim or default to Super Admin
          setSuperAdmin({
            id: decoded.sub,
            full_name: decoded.full_name || 'Super Admin',
          });
          setLoginStep('done');
        } else {
          clearSuperAdminToken();
        }
      } else {
        clearSuperAdminToken();
      }
    }
    setIsLoading(false);
  }, []);

  const login = (token: string, profile: { id: string; full_name: string }) => {
    saveSuperAdminToken(token);
    setSuperAdmin(profile);
    setLoginStep('done');
  };

  const logout = () => {
    clearSuperAdminToken();
    setSuperAdmin(null);
    setLoginStep('idle');
    setPreAuthToken(null);
    window.location.href = '/super-admin/login';
  };

  return (
    <SuperAdminAuthContext.Provider
      value={{
        superAdmin,
        isAuthenticated: !!superAdmin,
        loginStep,
        preAuthToken,
        isLoading,
        setLoginStep,
        setPreAuthToken,
        login,
        logout,
      }}
    >
      {children}
    </SuperAdminAuthContext.Provider>
  );
}

export function useSuperAdminAuth() {
  const context = useContext(SuperAdminAuthContext);
  if (context === undefined) {
    throw new Error('useSuperAdminAuth must be used within a SuperAdminAuthProvider');
  }
  return context;
}

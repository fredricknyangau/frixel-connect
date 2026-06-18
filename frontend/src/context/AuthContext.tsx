import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { UserRole } from '../types/auth';
import { saveToken, clearToken, getToken, isTokenExpired, decodeToken, saveRefreshToken, clearRefreshToken } from '../lib/auth';

interface AuthUser {
  user_id: string;
  role: UserRole;
  tenant_id: string | null;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  isLoading: boolean;
  refreshUser: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const initAuth = () => {
    const token = getToken();
    if (token && !isTokenExpired(token)) {
      const decoded = decodeToken(token);
      if (decoded) {
        setUser({
          user_id: decoded.sub,
          role: decoded.role,
          tenant_id: decoded.tenant_id,
        });
      }
    } else if (token) {
      clearToken();
      clearRefreshToken();
      setUser(null);
    } else {
      setUser(null);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    initAuth();
  }, []);

  const login = (accessToken: string, refreshToken: string) => {
    saveToken(accessToken);
    saveRefreshToken(refreshToken);
    const decoded = decodeToken(accessToken);
    if (decoded) {
      setUser({
        user_id: decoded.sub,
        role: decoded.role,
        tenant_id: decoded.tenant_id,
      });
    }
  };

  const logout = () => {
    clearToken();
    clearRefreshToken();
    setUser(null);
    window.location.href = '/login';
  };

  const refreshUser = () => {
    const token = getToken();
    if (token) {
      const decoded = decodeToken(token);
      if (decoded) {
        setUser({
          user_id: decoded.sub,
          role: decoded.role,
          tenant_id: decoded.tenant_id,
        });
      }
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        login,
        logout,
        isLoading,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}

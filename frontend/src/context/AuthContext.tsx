import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { UserRole } from '../types/auth';
import { saveToken, clearToken, getToken, isTokenExpired, decodeToken } from '../lib/auth';

interface AuthUser {
  user_id: string;
  role: UserRole;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * AuthProvider wraps the application and provides auth state.
 * 
 * Backend analogy: this is the frontend equivalent of the
 * `get_current_user` dependency in FastAPI — it runs once at the
 * app level and every component that needs auth info reads from it.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // On mount: check localStorage for token
    const initAuth = () => {
      const token = getToken();
      if (token && !isTokenExpired(token)) {
        const decoded = decodeToken(token);
        if (decoded) {
          setUser({
            user_id: decoded.sub,
            role: decoded.role,
          });
        }
      } else if (token) {
        // Token exists but is expired
        clearToken();
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = (token: string) => {
    saveToken(token);
    const decoded = decodeToken(token);
    if (decoded) {
      setUser({
        user_id: decoded.sub,
        role: decoded.role,
      });
    }
  };

  const logout = () => {
    clearToken();
    setUser(null);
    // Redirect to login page
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        login,
        logout,
        isLoading,
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

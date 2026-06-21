import { ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useSuperAdminAuth } from '../../context/SuperAdminAuthContext';

interface SuperAdminRouteProps {
  children?: ReactNode;
}

/**
 * SuperAdminRoute
 * Enforces authentication and TOTP verification completion for super admin pages.
 *
 * If the user is not authenticated or hasn't completed the multi-step login flow,
 * they are redirected to /super-admin/login.
 */
export default function SuperAdminRoute({ children }: SuperAdminRouteProps) {
  const { isAuthenticated, loginStep, isLoading } = useSuperAdminAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-950 text-slate-200">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
          <p className="text-sm font-medium tracking-wide">Securing session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || loginStep !== 'done') {
    return <Navigate to="/super-admin/login" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}

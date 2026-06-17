
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthContext } from '../../context/AuthContext';
import { UserRole } from '../../types/auth';

interface ProtectedRouteProps {
  allowedRoles?: UserRole[];
}

export default function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, user, isLoading } = useAuthContext();

  if (isLoading) {
    return <div className="flex h-screen w-full items-center justify-center">Loading...</div>;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Redirect to their correct portal home
    if (user.role === 'admin') return <Navigate to="/admin/dashboard" replace />;
    if (user.role === 'reseller') return <Navigate to="/reseller/dashboard" replace />;
    if (user.role === 'customer') return <Navigate to="/customer/dashboard" replace />;
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
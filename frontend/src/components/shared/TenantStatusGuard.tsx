import React from 'react';
import { useAuthContext } from '../../context/AuthContext';
import { api } from '../../lib/api';
import { decodeToken, getToken } from '../../lib/auth';
import { useQuery } from '@tanstack/react-query';
import { Tenant } from '../../types/tenants';
import TenantSuspendedPage from './TenantSuspendedPage';

/**
 * TenantStatusGuard
 * Wraps the entire application.
 * Reads the tenant status from the decoded token (for resellers/customers)
 * and performs live checks against GET /tenants/me (for admins).
 *
 * Why is this lock app-wide?
 * A suspended tenant's reseller and customer accounts must be locked out,
 * since their billing relationship with the system flows through the tenant.
 */
export default function TenantStatusGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthContext();
  const isAdmin = user?.role === 'admin';

  // Admins fetch live status to detect cron suspensions immediately
  const { data: tenant } = useQuery<Tenant>({
    queryKey: ['tenant_me'],
    queryFn: async () => {
      const response = await api.get<Tenant>('/tenants/me');
      return response.data;
    },
    enabled: isAuthenticated && isAdmin,
    refetchOnWindowFocus: true,
    staleTime: 15000, // 15s cache fresh time
  });

  const token = getToken();
  const decoded = token ? decodeToken(token) : null;
  const tokenStatus = decoded?.tenant_status;

  const isSuspended =
    (isAdmin && tenant && (tenant.status === 'suspended' || tenant.billing_status === 'suspended')) ||
    (tokenStatus === 'suspended');

  if (isAuthenticated && isSuspended) {
    return <TenantSuspendedPage />;
  }

  return <>{children}</>;
}

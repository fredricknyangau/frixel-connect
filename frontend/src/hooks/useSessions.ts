import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { Session } from '../types/sessions';

export function useAdminSessions() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.sessions.admin(tenantId),
    queryFn: async () => {
      const response = await api.get<Session[]>('/admin/sessions');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCustomerSessions() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.sessions.customer(tenantId),
    queryFn: async () => {
      const response = await api.get<Session[]>('/sessions/me');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

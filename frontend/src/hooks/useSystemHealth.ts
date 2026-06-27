import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { SystemHealth } from '../types/system-health';
import { AuditLogEntry } from '../types/audit';
import { AxiosError } from 'axios';

export const useSystemHealth = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<SystemHealth, AxiosError<{ detail: string }>>({
    queryKey: queryKeys.stats.systemHealth(tenantId),
    queryFn: async () => {
      const response = await api.get<SystemHealth>('/admin/system-health');
      return response.data;
    },
    enabled: !!tenantId,
    staleTime: 30000,
    refetchInterval: 30000,
  });
};

interface StuckPayment {
  id: string;
  customer_id: string;
  status: string;
  mpesa_receipt_number?: string | null;
  amount_kes: number;
  created_at: string;
}

export const useStuckPayments = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<StuckPayment[], AxiosError<{ detail: string }>>({
    queryKey: queryKeys.stats.stuckPayments(tenantId),
    queryFn: async () => {
      const response = await api.get<StuckPayment[]>('/admin/payments/stuck');
      return response.data;
    },
    enabled: !!tenantId,
    refetchInterval: 60000,
  });
};

export const useRetryProvisioning = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<{ message: string }, AxiosError<{ detail: string }>, string>({
    mutationFn: async (paymentId) => {
      const response = await api.post(`/admin/payments/${paymentId}/retry-provision`);
      return response.data;
    },
    onSuccess: () => {
      if (!tenantId) return;
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.stuckPayments(tenantId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.systemHealth(tenantId) });
    },
  });
};

export interface AuditLogResponse {
  items: AuditLogEntry[];
  total: number;
}

export const useAuditLog = (action?: string, limit = 50, offset = 0) => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';
  const actionKey = action ?? 'All';

  return useQuery<AuditLogResponse, AxiosError<{ detail: string }>>({
    queryKey: queryKeys.stats.auditLog(tenantId, actionKey, limit, offset),
    queryFn: async () => {
      const params: Record<string, string | number> = { limit, offset };
      if (action && action !== 'All') params.action = action;
      const response = await api.get<AuditLogResponse>('/admin/audit-log', { params });
      return response.data;
    },
    enabled: !!tenantId,
  });
};

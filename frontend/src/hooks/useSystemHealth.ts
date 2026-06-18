import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { SystemHealth } from '../types/system-health';
import { AuditLogEntry } from '../types/audit';
import { AxiosError } from 'axios';

export const useSystemHealth = () => {
  return useQuery<SystemHealth, AxiosError<{ detail: string }>>({
    queryKey: ['system_health'],
    queryFn: async () => {
      const response = await api.get<SystemHealth>('/admin/system-health');
      return response.data;
    },
    staleTime: 30000, // 30s
    refetchInterval: 30000,
  });
};

export const useStuckPayments = () => {
  return useQuery<any[], AxiosError<{ detail: string }>>({
    queryKey: ['stuck_payments'],
    queryFn: async () => {
      const response = await api.get<any[]>('/admin/payments/stuck');
      return response.data;
    },
    refetchInterval: 60000,
  });
};

export const useRetryProvisioning = () => {
  const queryClient = useQueryClient();
  return useMutation<
    any,
    AxiosError<{ detail: string }>,
    string
  >({
    mutationFn: async (paymentId) => {
      const response = await api.post(`/admin/payments/${paymentId}/retry-provision`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stuck_payments'] });
      queryClient.invalidateQueries({ queryKey: ['system_health'] });
    },
  });
};

export interface AuditLogResponse {
  items: AuditLogEntry[];
  total: number;
}

export const useAuditLog = (action?: string, limit = 50, offset = 0) => {
  return useQuery<AuditLogResponse, AxiosError<{ detail: string }>>({
    queryKey: ['audit_log', action, limit, offset],
    queryFn: async () => {
      const params: Record<string, any> = { limit, offset };
      if (action && action !== 'All') params.action = action;
      const response = await api.get<AuditLogResponse>('/admin/audit-log', { params });
      return response.data;
    },
  });
};

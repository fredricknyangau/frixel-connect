import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { Voucher } from '../types/vouchers';

export function useAdminVouchers() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.vouchers.admin(tenantId),
    queryFn: async () => {
      const response = await api.get<Voucher[]>('/reseller/vouchers');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useResellerVouchers() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.vouchers.reseller(tenantId),
    queryFn: async () => {
      const response = await api.get<Voucher[]>('/reseller/vouchers');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCustomerVouchers() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.vouchers.customer(tenantId),
    queryFn: async () => {
      const response = await api.get<Voucher[]>('/vouchers/me');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useRevokeVoucher() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await api.post(`/vouchers/${id}/revoke`);
      return response.data;
    },
    onSuccess: () => {
      if (!tenantId) return;
      queryClient.invalidateQueries({ queryKey: queryKeys.vouchers.admin(tenantId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.vouchers.reseller(tenantId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.vouchers.customer(tenantId) });
    },
  });
}

export function useRetryVoucher() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await api.post(`/vouchers/${id}/retry`);
      return response.data;
    },
    onSuccess: () => {
      if (!tenantId) return;
      queryClient.invalidateQueries({ queryKey: queryKeys.vouchers.admin(tenantId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.vouchers.reseller(tenantId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.vouchers.customer(tenantId) });
    },
  });
}

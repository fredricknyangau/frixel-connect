import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { Payment } from '../types/payments';

export function useAdminPayments() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.payments.admin(tenantId),
    queryFn: async () => {
      const response = await api.get<Payment[]>('/admin/payments');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useResellerPayments() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.payments.reseller(tenantId),
    queryFn: async () => {
      const response = await api.get<Payment[]>('/reseller/payments');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCustomerPayments() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.payments.customer(tenantId),
    queryFn: async () => {
      const response = await api.get<Payment[]>('/payments/me');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export interface STKPushRequest {
  package_id: string;
  phone: string;
}

export function useInitiateSTKPush() {
  return useMutation({
    mutationFn: async (data: STKPushRequest) => {
      const response = await api.post<Payment>('/payments/stk', data);
      return response.data;
    },
  });
}

export function usePaymentStatus(paymentId: string, enabled: boolean = true) {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.payments.status(tenantId, paymentId),
    queryFn: async () => {
      const response = await api.get(`/payments/${paymentId}/status`);
      return response.data;
    },
    enabled: enabled && !!paymentId && !!tenantId,
    refetchInterval: (query) => {
      if (query.state.data?.status === 'confirmed' || query.state.data?.status === 'failed') {
        return false;
      }
      return 3000;
    },
  });
}

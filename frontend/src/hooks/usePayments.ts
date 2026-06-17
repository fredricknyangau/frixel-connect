import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Payment } from '../types/payments';

export function useAdminPayments() {
  return useQuery({
    queryKey: ['adminPayments'],
    queryFn: async () => {
      const response = await api.get<Payment[]>('/admin/payments');
      return response.data;
    },
  });
}

export function useResellerPayments() {
  return useQuery({
    queryKey: ['resellerPayments'],
    queryFn: async () => {
      const response = await api.get<Payment[]>('/reseller/payments');
      return response.data;
    },
  });
}

export function useCustomerPayments() {
  return useQuery({
    queryKey: ['customerPayments'],
    queryFn: async () => {
      const response = await api.get<Payment[]>('/payments/me');
      return response.data;
    },
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
  return useQuery({
    queryKey: ['paymentStatus', paymentId],
    queryFn: async () => {
      const response = await api.get(`/payments/${paymentId}/status`);
      return response.data;
    },
    enabled: enabled && !!paymentId,
    refetchInterval: (query) => {
      // Stop polling if status is confirmed or failed
      if (query.state.data?.status === 'confirmed' || query.state.data?.status === 'failed') {
        return false;
      }
      return 3000; // Poll every 3 seconds
    },
  });
}

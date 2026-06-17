import { useQuery } from '@tanstack/react-query';
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

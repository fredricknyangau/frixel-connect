import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Voucher } from '../types/vouchers';

export function useAdminVouchers() {
  return useQuery({
    queryKey: ['adminVouchers'],
    queryFn: async () => {
      const response = await api.get<Voucher[]>('/reseller/vouchers');
      return response.data;
    },
  });
}

export function useResellerVouchers() {
  return useQuery({
    queryKey: ['resellerVouchers'],
    queryFn: async () => {
      const response = await api.get<Voucher[]>('/reseller/vouchers');
      return response.data;
    },
  });
}

export function useCustomerVouchers() {
  return useQuery({
    queryKey: ['customerVouchers'],
    queryFn: async () => {
      const response = await api.get<Voucher[]>('/vouchers/me');
      return response.data;
    },
  });
}

export function useRevokeVoucher() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const response = await api.post(`/vouchers/${id}/revoke`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminVouchers'] });
      queryClient.invalidateQueries({ queryKey: ['resellerVouchers'] });
      queryClient.invalidateQueries({ queryKey: ['customerVouchers'] });
      // Might also want to invalidate payments if they show voucher status
    },
  });
}
